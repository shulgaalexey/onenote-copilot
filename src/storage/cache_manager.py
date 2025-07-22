"""
Local OneNote cache manager.

Manages the local caching system for OneNote content including directory structure,
metadata storage, and basic cache operations.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config.settings import Settings, get_settings
from ..models.cache import (CachedPage, CachedPageMetadata, CacheMetadata,
                            CacheSearchResult, CacheStatistics, CleanupResult,
                            PageMatch)

logger = logging.getLogger(__name__)


class OneNoteCacheManager:
    """
    Manages the local OneNote content cache.

    Provides functionality for storing, retrieving, and managing cached OneNote
    content in a hierarchical directory structure that mirrors OneNote organization.
    """

    def __init__(self, settings: Optional[Settings] = None, cache_root: Optional[Path] = None):
        """
        Initialize the cache manager.

        Args:
            settings: Optional settings instance (uses global if None)
            cache_root: Optional custom cache root directory
        """
        self.settings = settings or get_settings()
        self.cache_root = cache_root or self.settings.onenote_cache_full_path

        logger.debug(f"Initializing OneNote cache manager with root: {self.cache_root}")

    def _get_user_cache_dir(self, user_id: str) -> Path:
        """
        Get the cache directory for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Path to user's cache directory
        """
        # Sanitize user_id for filesystem use
        safe_user_id = "".join(c for c in user_id if c.isalnum() or c in "._-@")
        return self.cache_root / "users" / safe_user_id

    def _get_notebook_dir(self, user_id: str, notebook_id: str) -> Path:
        """
        Get the directory for a specific notebook.

        Args:
            user_id: User identifier
            notebook_id: Notebook identifier

        Returns:
            Path to notebook directory
        """
        return self._get_user_cache_dir(user_id) / "notebooks" / notebook_id

    def _get_section_dir(self, user_id: str, notebook_id: str, section_id: str) -> Path:
        """
        Get the directory for a specific section.

        Args:
            user_id: User identifier
            notebook_id: Notebook identifier
            section_id: Section identifier

        Returns:
            Path to section directory
        """
        return self._get_notebook_dir(user_id, notebook_id) / "sections" / section_id

    def _get_page_dir(self, user_id: str, notebook_id: str, section_id: str, page_id: str) -> Path:
        """
        Get the directory for a specific page.

        Args:
            user_id: User identifier
            notebook_id: Notebook identifier
            section_id: Section identifier
            page_id: Page identifier

        Returns:
            Path to page directory
        """
        return self._get_section_dir(user_id, notebook_id, section_id) / "pages" / page_id

    async def initialize_user_cache(self, user_id: str) -> None:
        """
        Set up cache directory structure for a user.

        Args:
            user_id: User identifier to initialize cache for

        Raises:
            OSError: If directories cannot be created
        """
        try:
            logger.info(f"Initializing cache structure for user: {user_id}")

            user_cache_dir = self._get_user_cache_dir(user_id)

            # Create main directory structure
            directories = [
                user_cache_dir,
                user_cache_dir / "notebooks",
                user_cache_dir / "global",
            ]

            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created directory: {directory}")

            # Create cache metadata if it doesn't exist
            metadata_file = user_cache_dir / "cache_metadata.json"
            if not metadata_file.exists():
                cache_metadata = CacheMetadata(
                    user_id=user_id,
                    cache_root_path=str(self.cache_root)
                )
                await self._save_cache_metadata(user_id, cache_metadata)
                logger.info(f"Created initial cache metadata for user: {user_id}")

            # Create sync status file
            sync_status_file = user_cache_dir / "sync_status.json"
            if not sync_status_file.exists():
                sync_status = {
                    "last_sync_attempt": None,
                    "sync_in_progress": False,
                    "sync_pid": None,
                    "created_at": datetime.utcnow().isoformat()
                }
                with open(sync_status_file, 'w', encoding='utf-8') as f:
                    json.dump(sync_status, f, indent=2)
                logger.debug(f"Created sync status file: {sync_status_file}")

            logger.info(f"Cache initialization completed for user: {user_id}")

        except Exception as e:
            logger.error(f"Failed to initialize cache for user {user_id}: {e}")
            raise

    async def store_page_content(self, user_id: str, page: CachedPage) -> None:
        """
        Store page content, metadata, and assets locally.

        Args:
            user_id: User identifier
            page: Cached page to store

        Raises:
            OSError: If files cannot be written
        """
        try:
            # Get notebook and section IDs from metadata
            notebook_id = page.metadata.parent_notebook.get("id")
            section_id = page.metadata.parent_section.get("id")

            if not notebook_id or not section_id:
                raise ValueError(f"Missing parent IDs for page {page.metadata.id}")

            # Create page directory
            page_dir = self._get_page_dir(user_id, notebook_id, section_id, page.metadata.id)
            page_dir.mkdir(parents=True, exist_ok=True)

            # Create attachments directory
            attachments_dir = page_dir / "attachments"
            attachments_dir.mkdir(exist_ok=True)
            (attachments_dir / "images").mkdir(exist_ok=True)
            (attachments_dir / "files").mkdir(exist_ok=True)

            # Save metadata
            metadata_file = page_dir / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(page.metadata.model_dump(), f, indent=2, default=str)

            # Save markdown content
            if page.markdown_content:
                markdown_file = page_dir / "content.md"
                with open(markdown_file, 'w', encoding='utf-8') as f:
                    f.write(page.markdown_content)

            # Save original HTML content if requested
            if page.content and self.settings.onenote_preserve_html:
                html_file = page_dir / "original.html"
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(page.content)

            # Update page paths in metadata
            page.metadata.local_content_path = str(page_dir / "content.md")
            page.metadata.local_html_path = str(page_dir / "original.html")
            page.metadata.last_synced = datetime.utcnow()

            logger.debug(f"Stored page content: {page.metadata.title} ({page.metadata.id})")

        except Exception as e:
            logger.error(f"Failed to store page {page.metadata.id}: {e}")
            raise

    async def get_cached_page(self, user_id: str, page_id: str) -> Optional[CachedPage]:
        """
        Retrieve a page from local cache.

        Args:
            user_id: User identifier
            page_id: Page identifier

        Returns:
            Cached page if found, None otherwise
        """
        try:
            # Find page by searching through cache structure
            user_cache_dir = self._get_user_cache_dir(user_id)

            # Search for the page in all notebooks/sections
            for notebook_dir in (user_cache_dir / "notebooks").glob("*"):
                if not notebook_dir.is_dir():
                    continue

                for section_dir in (notebook_dir / "sections").glob("*"):
                    if not section_dir.is_dir():
                        continue

                    page_dir = section_dir / "pages" / page_id
                    if page_dir.exists():
                        return await self._load_page_from_directory(page_dir)

            logger.debug(f"Page not found in cache: {page_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to retrieve page {page_id}: {e}")
            return None

    async def _load_page_from_directory(self, page_dir: Path) -> CachedPage:
        """
        Load a cached page from its directory.

        Args:
            page_dir: Path to page directory

        Returns:
            Loaded cached page

        Raises:
            FileNotFoundError: If required files are missing
            ValueError: If metadata is invalid
        """
        try:
            # Load metadata
            metadata_file = page_dir / "metadata.json"
            if not metadata_file.exists():
                raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
                metadata = CachedPageMetadata(**metadata_dict)

            # Load content files
            content = None
            markdown_content = None

            html_file = page_dir / "original.html"
            if html_file.exists():
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()

            markdown_file = page_dir / "content.md"
            if markdown_file.exists():
                with open(markdown_file, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()

            # Extract text content from markdown if available
            text_content = None
            if markdown_content:
                # Simple text extraction (remove markdown formatting)
                import re
                text_content = re.sub(r'[#*_`\[\]()~]', '', markdown_content)
                text_content = re.sub(r'\n+', ' ', text_content).strip()

            return CachedPage(
                metadata=metadata,
                content=content,
                markdown_content=markdown_content,
                text_content=text_content
            )

        except Exception as e:
            logger.error(f"Failed to load page from directory {page_dir}: {e}")
            raise

    async def search_cached_pages(self, user_id: str, query: str) -> List[CachedPage]:
        """
        Search cached pages using local full-text search.

        Args:
            user_id: User identifier
            query: Search query

        Returns:
            List of matching cached pages
        """
        try:
            logger.debug(f"Searching cached pages for user {user_id}: '{query}'")

            matches = []
            user_cache_dir = self._get_user_cache_dir(user_id)

            if not user_cache_dir.exists():
                logger.debug(f"User cache directory not found: {user_cache_dir}")
                return matches

            query_lower = query.lower()

            # Search through all pages
            for notebook_dir in (user_cache_dir / "notebooks").glob("*"):
                if not notebook_dir.is_dir():
                    continue

                for section_dir in (notebook_dir / "sections").glob("*"):
                    if not section_dir.is_dir():
                        continue

                    for page_dir in (section_dir / "pages").glob("*"):
                        if not page_dir.is_dir():
                            continue

                        try:
                            page = await self._load_page_from_directory(page_dir)

                            # Check if query matches title or content
                            if (query_lower in page.metadata.title.lower() or
                                (page.text_content and query_lower in page.text_content.lower()) or
                                (page.markdown_content and query_lower in page.markdown_content.lower())):
                                matches.append(page)

                        except Exception as e:
                            logger.warning(f"Failed to load page from {page_dir}: {e}")
                            continue

            # Sort by last modified date (most recent first)
            matches.sort(key=lambda p: p.metadata.last_modified_date_time, reverse=True)

            logger.debug(f"Found {len(matches)} matching pages")
            return matches

        except Exception as e:
            logger.error(f"Failed to search cached pages: {e}")
            return []

    async def get_pages_by_section(self, user_id: str, section_id: str) -> List[CachedPage]:
        """
        Get all cached pages from a specific section.

        Args:
            user_id: User identifier
            section_id: Section identifier

        Returns:
            List of cached pages in the section
        """
        try:
            logger.debug(f"Getting pages for user {user_id} in section {section_id}")

            pages = []
            user_cache_dir = self._get_user_cache_dir(user_id)

            if not user_cache_dir.exists():
                logger.debug(f"User cache directory not found: {user_cache_dir}")
                return pages

            # Search through all notebooks to find the section
            for notebook_dir in (user_cache_dir / "notebooks").glob("*"):
                if not notebook_dir.is_dir():
                    continue

                section_dir = notebook_dir / "sections" / section_id
                if not section_dir.exists():
                    continue

                # Found the section, load all pages
                pages_dir = section_dir / "pages"
                if not pages_dir.exists():
                    continue

                for page_dir in pages_dir.glob("*"):
                    if not page_dir.is_dir():
                        continue

                    try:
                        page = await self._load_page_from_directory(page_dir)
                        pages.append(page)
                        logger.debug(f"Loaded page {page.id} from section {section_id}")

                    except Exception as e:
                        logger.warning(f"Failed to load page from {page_dir}: {e}")
                        continue

                break  # Found the section, no need to search other notebooks

            logger.debug(f"Found {len(pages)} pages in section {section_id}")
            return pages

        except Exception as e:
            logger.error(f"Failed to get pages for section {section_id}: {e}")
            return []

    async def get_cache_statistics(self, user_id: str) -> CacheStatistics:
        """
        Get cache usage and sync statistics.

        Args:
            user_id: User identifier

        Returns:
            Cache statistics
        """
        try:
            user_cache_dir = self._get_user_cache_dir(user_id)

            stats = CacheStatistics(user_id=user_id)

            if not user_cache_dir.exists():
                return stats

            # Count notebooks, sections, and pages
            notebooks_dir = user_cache_dir / "notebooks"
            if notebooks_dir.exists():
                for notebook_dir in notebooks_dir.glob("*"):
                    if not notebook_dir.is_dir():
                        continue
                    stats.total_notebooks += 1

                    sections_dir = notebook_dir / "sections"
                    if sections_dir.exists():
                        for section_dir in sections_dir.glob("*"):
                            if not section_dir.is_dir():
                                continue
                            stats.total_sections += 1

                            pages_dir = section_dir / "pages"
                            if pages_dir.exists():
                                for page_dir in pages_dir.glob("*"):
                                    if page_dir.is_dir():
                                        stats.total_pages += 1

                                        # Count assets
                                        attachments_dir = page_dir / "attachments"
                                        if attachments_dir.exists():
                                            images_dir = attachments_dir / "images"
                                            if images_dir.exists():
                                                stats.total_images += len(list(images_dir.glob("*")))

                                            files_dir = attachments_dir / "files"
                                            if files_dir.exists():
                                                stats.total_files += len(list(files_dir.glob("*")))

            # Calculate storage size
            try:
                stats.total_size_bytes = self._calculate_directory_size(user_cache_dir)
            except Exception as e:
                logger.warning(f"Failed to calculate cache size: {e}")

            # Load last sync info from cache metadata
            try:
                cache_metadata = await self._load_cache_metadata(user_id)
                if cache_metadata:
                    stats.last_sync = cache_metadata.last_incremental_sync or cache_metadata.last_full_sync
            except Exception as e:
                logger.warning(f"Failed to load sync info: {e}")

            return stats

        except Exception as e:
            logger.error(f"Failed to get cache statistics: {e}")
            return CacheStatistics(user_id=user_id)

    def _calculate_directory_size(self, path: Path) -> int:
        """
        Calculate total size of directory and all subdirectories.

        Args:
            path: Path to calculate size for

        Returns:
            Total size in bytes
        """
        total_size = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to calculate size for {path}: {e}")
        return total_size

    async def cleanup_orphaned_assets(self, user_id: str) -> CleanupResult:
        """
        Remove assets no longer referenced by any pages.

        Args:
            user_id: User identifier

        Returns:
            Cleanup result with statistics
        """
        start_time = datetime.utcnow()
        result = CleanupResult()

        try:
            logger.info(f"Starting orphaned asset cleanup for user: {user_id}")

            user_cache_dir = self._get_user_cache_dir(user_id)
            if not user_cache_dir.exists():
                return result

            # Collect all asset references from pages
            referenced_assets = set()

            for notebook_dir in (user_cache_dir / "notebooks").glob("*"):
                if not notebook_dir.is_dir():
                    continue

                for section_dir in (notebook_dir / "sections").glob("*"):
                    if not section_dir.is_dir():
                        continue

                    for page_dir in (section_dir / "pages").glob("*"):
                        if not page_dir.is_dir():
                            continue

                        try:
                            metadata_file = page_dir / "metadata.json"
                            if metadata_file.exists():
                                with open(metadata_file, 'r', encoding='utf-8') as f:
                                    metadata = json.load(f)

                                # Collect asset paths from metadata
                                for attachment in metadata.get('attachments', []):
                                    if 'local_path' in attachment:
                                        referenced_assets.add(Path(attachment['local_path']))

                        except Exception as e:
                            logger.warning(f"Failed to process page {page_dir}: {e}")
                            continue

            # Find and remove orphaned assets
            for notebook_dir in (user_cache_dir / "notebooks").glob("*"):
                if not notebook_dir.is_dir():
                    continue

                for section_dir in (notebook_dir / "sections").glob("*"):
                    if not section_dir.is_dir():
                        continue

                    for page_dir in (section_dir / "pages").glob("*"):
                        if not page_dir.is_dir():
                            continue

                        attachments_dir = page_dir / "attachments"
                        if not attachments_dir.exists():
                            continue

                        # Check all asset files
                        for asset_file in attachments_dir.rglob("*"):
                            if asset_file.is_file() and asset_file not in referenced_assets:
                                try:
                                    file_size = asset_file.stat().st_size
                                    asset_file.unlink()
                                    result.orphaned_assets_removed += 1
                                    result.space_freed_bytes += file_size
                                    logger.debug(f"Removed orphaned asset: {asset_file}")
                                except Exception as e:
                                    logger.warning(f"Failed to remove orphaned asset {asset_file}: {e}")
                                    result.errors.append(f"Failed to remove {asset_file}: {e}")

            end_time = datetime.utcnow()
            result.cleanup_time_seconds = (end_time - start_time).total_seconds()

            logger.info(f"Cleanup completed: removed {result.orphaned_assets_removed} assets, "
                       f"freed {result.space_freed_mb:.1f}MB")

            return result

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned assets: {e}")
            result.errors.append(str(e))
            return result

    async def _save_cache_metadata(self, user_id: str, metadata: CacheMetadata) -> None:
        """
        Save cache metadata to disk.

        Args:
            user_id: User identifier
            metadata: Cache metadata to save
        """
        try:
            user_cache_dir = self._get_user_cache_dir(user_id)
            metadata_file = user_cache_dir / "cache_metadata.json"

            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata.model_dump(), f, indent=2, default=str)

            logger.debug(f"Saved cache metadata for user: {user_id}")

        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}")
            raise

    async def _load_cache_metadata(self, user_id: str) -> Optional[CacheMetadata]:
        """
        Load cache metadata from disk.

        Args:
            user_id: User identifier

        Returns:
            Cache metadata if found, None otherwise
        """
        try:
            user_cache_dir = self._get_user_cache_dir(user_id)
            metadata_file = user_cache_dir / "cache_metadata.json"

            if not metadata_file.exists():
                return None

            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_dict = json.load(f)
                return CacheMetadata(**metadata_dict)

        except Exception as e:
            logger.error(f"Failed to load cache metadata: {e}")
            return None

    async def update_cache_metadata(self, user_id: str, **updates) -> None:
        """
        Update specific fields in cache metadata.

        Args:
            user_id: User identifier
            **updates: Fields to update
        """
        try:
            metadata = await self._load_cache_metadata(user_id)
            if not metadata:
                # Create new metadata if doesn't exist
                metadata = CacheMetadata(
                    user_id=user_id,
                    cache_root_path=str(self.cache_root)
                )

            # Apply updates
            for key, value in updates.items():
                if hasattr(metadata, key):
                    setattr(metadata, key, value)

            await self._save_cache_metadata(user_id, metadata)

        except Exception as e:
            logger.error(f"Failed to update cache metadata: {e}")
            raise

    async def delete_user_cache(self, user_id: str) -> bool:
        """
        Delete all cached data for a user.

        Args:
            user_id: User identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            user_cache_dir = self._get_user_cache_dir(user_id)

            if user_cache_dir.exists():
                shutil.rmtree(user_cache_dir)
                logger.info(f"Deleted cache for user: {user_id}")
                return True
            else:
                logger.debug(f"Cache directory doesn't exist for user: {user_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to delete cache for user {user_id}: {e}")
            return False

    def cache_exists(self, user_id: str) -> bool:
        """
        Check if cache exists for a user.

        Args:
            user_id: User identifier

        Returns:
            True if cache exists, False otherwise
        """
        user_cache_dir = self._get_user_cache_dir(user_id)
        return user_cache_dir.exists() and (user_cache_dir / "cache_metadata.json").exists()
