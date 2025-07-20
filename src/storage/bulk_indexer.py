"""
Bulk content indexing manager for OneNote cache system.

Provides comprehensive batch processing capabilities with progress tracking,
resume functionality, and efficient content synchronization.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..models.cache import CachedPage, SyncResult
from ..models.onenote import OneNotePage, OneNoteSection, OneNoteNotebook
from .onenote_fetcher import OneNoteContentFetcher
from .asset_downloader import AssetDownloadManager
from .markdown_converter import MarkdownConverter
from .local_search import LocalOneNoteSearch
from .directory_utils import get_content_path_for_page

logger = logging.getLogger(__name__)


class IndexingStatus(Enum):
    """Status of indexing operation."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class IndexingProgress:
    """Progress tracking for bulk indexing operations."""
    
    # Basic counters
    total_notebooks: int = 0
    total_sections: int = 0
    total_pages: int = 0
    
    # Progress counters
    processed_notebooks: int = 0
    processed_sections: int = 0
    processed_pages: int = 0
    
    # Success/failure tracking
    successful_pages: int = 0
    failed_pages: int = 0
    skipped_pages: int = 0
    
    # Performance metrics
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    
    # Size tracking
    total_content_size: int = 0
    processed_content_size: int = 0
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def get_completion_percentage(self) -> float:
        """Get completion percentage (0.0 to 100.0)."""
        if self.total_pages == 0:
            return 0.0
        return (self.processed_pages / self.total_pages) * 100.0
    
    def get_success_rate(self) -> float:
        """Get success rate percentage (0.0 to 100.0)."""
        if self.processed_pages == 0:
            return 0.0
        return (self.successful_pages / self.processed_pages) * 100.0
    
    def get_elapsed_time(self) -> Optional[timedelta]:
        """Get elapsed processing time."""
        if not self.start_time:
            return None
        end = self.end_time or datetime.utcnow()
        return end - self.start_time
    
    def estimate_remaining_time(self) -> Optional[timedelta]:
        """Estimate remaining processing time."""
        if not self.start_time or self.processed_pages == 0:
            return None
        
        elapsed = self.get_elapsed_time()
        if not elapsed:
            return None
            
        rate = self.processed_pages / elapsed.total_seconds()
        remaining_pages = self.total_pages - self.processed_pages
        
        if rate <= 0:
            return None
            
        remaining_seconds = remaining_pages / rate
        return timedelta(seconds=remaining_seconds)
    
    def get_processing_rate(self) -> float:
        """Get pages per second processing rate."""
        elapsed = self.get_elapsed_time()
        if not elapsed or elapsed.total_seconds() == 0:
            return 0.0
        return self.processed_pages / elapsed.total_seconds()


@dataclass
class IndexingCheckpoint:
    """Checkpoint for resuming interrupted indexing operations."""
    
    operation_id: str
    timestamp: datetime
    progress: IndexingProgress
    current_notebook_id: Optional[str] = None
    current_section_id: Optional[str] = None
    completed_page_ids: List[str] = field(default_factory=list)
    failed_page_ids: List[str] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)


class BulkContentIndexer:
    """
    Manager for bulk content indexing operations.
    
    Provides comprehensive batch processing with progress tracking,
    checkpoint/resume functionality, and efficient resource management.
    """

    def __init__(self, 
                 cache_root: Path,
                 content_fetcher: Optional[OneNoteContentFetcher] = None,
                 asset_downloader: Optional[AssetDownloadManager] = None,
                 markdown_converter: Optional[MarkdownConverter] = None,
                 local_search: Optional[LocalOneNoteSearch] = None,
                 max_concurrent_pages: int = 5,
                 checkpoint_interval: int = 100):
        """
        Initialize bulk content indexer.

        Args:
            cache_root: Root directory for cache storage
            content_fetcher: OneNote content fetcher (optional)
            asset_downloader: Asset download manager (optional)
            markdown_converter: Markdown converter (optional)
            local_search: Local search index (optional)
            max_concurrent_pages: Maximum concurrent page processing
            checkpoint_interval: Pages between checkpoint saves
        """
        self.cache_root = Path(cache_root)
        self.content_fetcher = content_fetcher
        self.asset_downloader = asset_downloader
        self.markdown_converter = markdown_converter
        self.local_search = local_search
        
        self.max_concurrent_pages = max_concurrent_pages
        self.checkpoint_interval = checkpoint_interval
        
        # Operation state
        self.current_operation_id: Optional[str] = None
        self.status = IndexingStatus.PENDING
        self.progress = IndexingProgress()
        self.checkpoint: Optional[IndexingCheckpoint] = None
        
        # Callbacks
        self.progress_callback: Optional[Callable[[IndexingProgress], None]] = None
        self.checkpoint_callback: Optional[Callable[[IndexingCheckpoint], None]] = None
        
        # Semaphore for concurrent processing
        self.processing_semaphore = asyncio.Semaphore(max_concurrent_pages)
        
        logger.info(f"Initialized bulk content indexer with cache root: {cache_root}")

    def set_progress_callback(self, callback: Callable[[IndexingProgress], None]) -> None:
        """Set callback for progress updates."""
        self.progress_callback = callback

    def set_checkpoint_callback(self, callback: Callable[[IndexingCheckpoint], None]) -> None:
        """Set callback for checkpoint saves."""
        self.checkpoint_callback = callback

    async def index_all_content(self, 
                               notebooks: Optional[List[OneNoteNotebook]] = None,
                               resume_from_checkpoint: bool = True,
                               force_reindex: bool = False) -> IndexingProgress:
        """
        Index all OneNote content with comprehensive processing.

        Args:
            notebooks: Specific notebooks to index (None for all)
            resume_from_checkpoint: Whether to resume from saved checkpoint
            force_reindex: Whether to force reindex existing content

        Returns:
            Final indexing progress
        """
        try:
            # Generate operation ID
            self.current_operation_id = f"bulk_index_{int(time.time())}"
            
            # Try to load checkpoint if resuming
            if resume_from_checkpoint and await self._load_checkpoint():
                logger.info(f"Resuming indexing from checkpoint: {self.checkpoint.timestamp}")
                notebooks = None  # Use checkpoint state
            else:
                # Initialize new operation
                self.progress = IndexingProgress()
                self.progress.start_time = datetime.utcnow()
                self.status = IndexingStatus.RUNNING
                
                # Get notebooks to process
                if not notebooks and self.content_fetcher:
                    notebooks = await self.content_fetcher.get_all_notebooks()
                elif not notebooks:
                    raise ValueError("No notebooks provided and no content fetcher available")

            # Count total items for progress tracking
            await self._calculate_totals(notebooks or [])
            
            logger.info(f"Starting bulk indexing: {self.progress.total_notebooks} notebooks, "
                       f"{self.progress.total_sections} sections, {self.progress.total_pages} pages")

            # Process notebooks
            for notebook in notebooks or []:
                if self.status != IndexingStatus.RUNNING:
                    break
                    
                await self._process_notebook(notebook, force_reindex)
                self.progress.processed_notebooks += 1
                await self._update_progress()

            # Finalize
            self.progress.end_time = datetime.utcnow()
            self.status = IndexingStatus.COMPLETED
            
            logger.info(f"Bulk indexing completed: {self.progress.successful_pages}/{self.progress.total_pages} "
                       f"pages processed successfully ({self.progress.get_success_rate():.1f}%)")
            
            return self.progress

        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            self.progress.errors.append(f"Indexing failed: {str(e)}")
            self.status = IndexingStatus.FAILED
            raise

    async def _calculate_totals(self, notebooks: List[OneNoteNotebook]) -> None:
        """Calculate total items for progress tracking."""
        try:
            self.progress.total_notebooks = len(notebooks)
            
            for notebook in notebooks:
                if not self.content_fetcher:
                    continue
                    
                sections = await self.content_fetcher.get_all_sections(notebook_id=notebook.id)
                self.progress.total_sections += len(sections)
                
                for section in sections:
                    pages = await self.content_fetcher.get_pages_from_section(section.id)
                    self.progress.total_pages += len(pages)
                    
        except Exception as e:
            logger.warning(f"Failed to calculate totals: {e}")
            # Set conservative estimates
            self.progress.total_notebooks = len(notebooks)
            self.progress.total_sections = len(notebooks) * 3  # Estimate
            self.progress.total_pages = len(notebooks) * 10   # Estimate

    async def _process_notebook(self, notebook: OneNoteNotebook, force_reindex: bool) -> None:
        """Process a single notebook with all sections and pages."""
        try:
            logger.info(f"Processing notebook: {notebook.display_name}")
            
            if not self.content_fetcher:
                return
                
            sections = await self.content_fetcher.get_all_sections(notebook_id=notebook.id)
            
            for section in sections:
                if self.status != IndexingStatus.RUNNING:
                    break
                    
                await self._process_section(notebook, section, force_reindex)
                self.progress.processed_sections += 1
                
        except Exception as e:
            error_msg = f"Failed to process notebook {notebook.display_name}: {e}"
            logger.error(error_msg)
            self.progress.errors.append(error_msg)

    async def _process_section(self, 
                             notebook: OneNoteNotebook, 
                             section: OneNoteSection, 
                             force_reindex: bool) -> None:
        """Process a single section with all pages."""
        try:
            logger.debug(f"Processing section: {section.display_name}")
            
            if not self.content_fetcher:
                return
                
            pages = await self.content_fetcher.get_pages_from_section(section.id)
            
            # Process pages with concurrency control
            semaphore_tasks = []
            for page in pages:
                if self.status != IndexingStatus.RUNNING:
                    break
                    
                task = self._process_page_with_semaphore(notebook, section, page, force_reindex)
                semaphore_tasks.append(task)
                
                # Process in batches to avoid memory issues
                if len(semaphore_tasks) >= self.max_concurrent_pages * 2:
                    await asyncio.gather(*semaphore_tasks)
                    semaphore_tasks = []
            
            # Process remaining tasks
            if semaphore_tasks:
                await asyncio.gather(*semaphore_tasks)
                
        except Exception as e:
            error_msg = f"Failed to process section {section.display_name}: {e}"
            logger.error(error_msg)
            self.progress.errors.append(error_msg)

    async def _process_page_with_semaphore(self, 
                                         notebook: OneNoteNotebook,
                                         section: OneNoteSection, 
                                         page: OneNotePage, 
                                         force_reindex: bool) -> None:
        """Process a single page with semaphore control."""
        async with self.processing_semaphore:
            await self._process_page(notebook, section, page, force_reindex)

    async def _process_page(self, 
                          notebook: OneNoteNotebook,
                          section: OneNoteSection, 
                          page: OneNotePage, 
                          force_reindex: bool) -> None:
        """Process a single page through the complete pipeline."""
        try:
            # Check if already processed (unless force reindex)
            if not force_reindex and self._is_page_current(page):
                self.progress.skipped_pages += 1
                self.progress.processed_pages += 1
                return
            
            logger.debug(f"Processing page: {page.title}")
            
            # Get page content if not available
            if not page.html_content and self.content_fetcher:
                page = await self.content_fetcher.get_page_content(page.id)
            
            # Process assets if available
            assets = []
            if self.asset_downloader and page.html_content:
                download_result = await self.asset_downloader.download_assets(
                    [page], progress_callback=None
                )
                assets = download_result.downloaded_assets
            
            # Convert to markdown if available
            markdown_content = ""
            if self.markdown_converter and page.html_content:
                conversion_result = self.markdown_converter.convert_to_markdown(
                    page.html_content, assets, [], page.title
                )
                if conversion_result.success:
                    markdown_content = conversion_result.markdown_content
            
            # Create cached page
            cached_page = CachedPage(
                id=page.id,
                title=page.title,
                html_content=page.html_content,
                markdown_content=markdown_content,
                created_date_time=page.created_date_time,
                last_modified_date_time=page.last_modified_date_time,
                notebook_id=notebook.id,
                notebook_name=notebook.display_name,
                section_id=section.id,
                section_name=section.display_name,
                content_url=page.content_url,
                assets=assets,
                links=[],  # Links would be resolved by link resolver
                cache_created_at=datetime.utcnow(),
                cache_updated_at=datetime.utcnow()
            )
            
            # Index in local search if available
            if self.local_search:
                await self.local_search.index_page(cached_page)
            
            # Save to cache storage
            await self._save_cached_page(cached_page)
            
            self.progress.successful_pages += 1
            self.progress.processed_content_size += len(page.html_content or "")
            
        except Exception as e:
            error_msg = f"Failed to process page {page.title}: {e}"
            logger.error(error_msg)
            self.progress.errors.append(error_msg)
            self.progress.failed_pages += 1
            
        finally:
            self.progress.processed_pages += 1
            
            # Update progress and checkpoint
            if self.progress.processed_pages % self.checkpoint_interval == 0:
                await self._save_checkpoint()
            
            await self._update_progress()

    def _is_page_current(self, page: OneNotePage) -> bool:
        """Check if page is already current in cache."""
        try:
            # Simple check - in production this would check file timestamps
            page_path = get_content_path_for_page(
                self.cache_root, 
                page.notebook_name or "Unknown",
                page.section_name or "Unknown", 
                page.title
            )
            
            markdown_path = page_path / "content.md"
            return markdown_path.exists()
            
        except Exception:
            return False

    async def _save_cached_page(self, cached_page: CachedPage) -> None:
        """Save cached page to storage."""
        try:
            page_dir = get_content_path_for_page(
                self.cache_root,
                cached_page.notebook_name,
                cached_page.section_name,
                cached_page.title
            )
            
            page_dir.mkdir(parents=True, exist_ok=True)
            
            # Save markdown content
            if cached_page.markdown_content:
                markdown_path = page_dir / "content.md"
                markdown_path.write_text(cached_page.markdown_content, encoding='utf-8')
            
            # Save HTML content
            if cached_page.html_content:
                html_path = page_dir / "content.html"
                html_path.write_text(cached_page.html_content, encoding='utf-8')
                
        except Exception as e:
            logger.error(f"Failed to save cached page {cached_page.title}: {e}")
            raise

    async def _update_progress(self) -> None:
        """Update progress and trigger callbacks."""
        self.progress.last_update = datetime.utcnow()
        
        if self.progress_callback:
            try:
                self.progress_callback(self.progress)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")

    async def _save_checkpoint(self) -> None:
        """Save operation checkpoint."""
        try:
            if not self.current_operation_id:
                return
                
            self.checkpoint = IndexingCheckpoint(
                operation_id=self.current_operation_id,
                timestamp=datetime.utcnow(),
                progress=self.progress,
                settings={}
            )
            
            if self.checkpoint_callback:
                self.checkpoint_callback(self.checkpoint)
                
            logger.debug(f"Saved checkpoint at {self.progress.processed_pages} pages")
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    async def _load_checkpoint(self) -> bool:
        """Load operation checkpoint."""
        # Implementation would load from storage
        # For now, return False (no checkpoint found)
        return False

    def pause_indexing(self) -> None:
        """Pause the current indexing operation."""
        if self.status == IndexingStatus.RUNNING:
            self.status = IndexingStatus.PAUSED
            logger.info("Indexing operation paused")

    def resume_indexing(self) -> None:
        """Resume the paused indexing operation."""
        if self.status == IndexingStatus.PAUSED:
            self.status = IndexingStatus.RUNNING
            logger.info("Indexing operation resumed")

    def cancel_indexing(self) -> None:
        """Cancel the current indexing operation."""
        if self.status in [IndexingStatus.RUNNING, IndexingStatus.PAUSED]:
            self.status = IndexingStatus.CANCELLED
            logger.info("Indexing operation cancelled")

    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive status report."""
        return {
            "operation_id": self.current_operation_id,
            "status": self.status.value,
            "progress": {
                "completion_percentage": self.progress.get_completion_percentage(),
                "success_rate": self.progress.get_success_rate(),
                "processing_rate": self.progress.get_processing_rate(),
                "elapsed_time": str(self.progress.get_elapsed_time()),
                "estimated_remaining": str(self.progress.estimate_remaining_time()),
                "processed_pages": self.progress.processed_pages,
                "total_pages": self.progress.total_pages,
                "successful_pages": self.progress.successful_pages,
                "failed_pages": self.progress.failed_pages,
                "skipped_pages": self.progress.skipped_pages
            },
            "errors": self.progress.errors[-10:],  # Last 10 errors
            "warnings": self.progress.warnings[-10:]  # Last 10 warnings
        }
