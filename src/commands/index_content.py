"""
Content indexing command for OneNote semantic search.

This module provides commands to index OneNote content into the vector database
for semantic search capabilities. It handles:
- Initial content indexing from all accessible OneNote pages
- Incremental updates for new/modified content
- Progress tracking and error handling
- Content validation and statistics
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn, TaskID,
                           TextColumn, TimeElapsedColumn)
from rich.table import Table
from rich.text import Text

from ..auth.microsoft_auth import MicrosoftAuthenticator
from ..config.logging import get_logger
from ..config.settings import get_settings
from ..models.onenote import OneNotePage
from ..search.embeddings import EmbeddingGenerator
from ..storage.content_indexer import ContentIndexer
from ..storage.vector_store import VectorStore
from ..tools.onenote_search import OneNoteSearchTool

console = Console()


def _get_logger():
    """Get logger with safe initialization."""
    try:
        return get_logger(__name__)
    except RuntimeError:
        import logging
        return logging.getLogger(__name__)


class IndexingStats:
    """Statistics for content indexing operations."""

    def __init__(self):
        self.total_pages = 0
        self.processed_pages = 0
        self.failed_pages = 0
        self.total_chunks = 0
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.errors: List[str] = []

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_pages == 0:
            return 0.0
        return (self.processed_pages / self.total_pages) * 100

    @property
    def duration(self) -> timedelta:
        """Calculate total duration."""
        end = self.end_time or datetime.now()
        return end - self.start_time

    def add_error(self, error: str) -> None:
        """Add an error to the stats."""
        self.errors.append(error)
        self.failed_pages += 1


class ContentIndexingService:
    """Service for indexing OneNote content into vector database."""

    def __init__(self):
        self.settings = get_settings()
        self.authenticator = MicrosoftAuthenticator()
        self.embedding_generator = EmbeddingGenerator()
        self.content_indexer = ContentIndexer()
        self.vector_store = VectorStore()
        self.onenote_search = OneNoteSearchTool()
        self.stats = IndexingStats()
        self._logger = None

    @property
    def logger(self):
        """Get logger with safe initialization."""
        if self._logger is None:
            self._logger = _get_logger()
        return self._logger

    async def initialize(self) -> bool:
        """Initialize all components required for indexing."""
        try:
            self.logger.info("Initializing content indexing service...")

            # Check authentication by trying to get a token (this will use cache if available)
            try:
                token = await self.authenticator.get_access_token()
                if not token:
                    console.print("[red]X Authentication required. Please run authentication first.[/red]")
                    return False
            except Exception as e:
                self.logger.warning(f"Authentication check failed: {e}")
                console.print("[red]X Authentication required. Please run authentication first.[/red]")
                return False

            # Components are initialized in __init__, no async initialization needed
            console.print("[green]OK Content indexing service initialized successfully[/green]")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize content indexing service: {e}")
            console.print(f"[red]X Initialization failed: {e}[/red]")
            return False

    async def get_all_pages(self, limit: Optional[int] = None) -> List[OneNotePage]:
        """Get all accessible OneNote pages."""
        try:
            self.logger.info("Fetching all OneNote pages...")

            # Use OneNote search tool to get all pages
            pages = await self.onenote_search.get_all_pages(limit)

            self.stats.total_pages = len(pages)
            console.print(f"[blue]Pages Found {len(pages)} pages to index[/blue]")

            return pages

        except Exception as e:
            self.logger.error(f"Failed to fetch OneNote pages: {e}")
            console.print(f"[red]X Failed to fetch pages: {e}[/red]")
            return []

    async def index_page(self, page: OneNotePage) -> bool:
        """Index a single OneNote page."""
        try:
            self.logger.debug(f"Indexing page: {page.title} ({page.id})")

            # Get page content using OneNote search tool
            token = await self.authenticator.get_access_token()
            content_result, status_code = await self.onenote_search._fetch_page_content(page.id, token)

            if not content_result or not content_result.strip():
                self.logger.warning(f"Empty content for page {page.id}")
                return False

            # Generate embeddings for page
            embeddings = await self.embedding_generator.embed_onenote_page(page, content_result)
            if not embeddings:
                self.logger.warning(f"No embeddings generated for page {page.id}")
                return False

            # Store embeddings in vector database
            await self.content_indexer.store_page_embeddings(page.id, embeddings)

            self.stats.processed_pages += 1
            self.stats.total_chunks += len(embeddings)

            return True

        except Exception as e:
            error_msg = f"Failed to index page {page.id}: {e}"
            self.logger.error(error_msg)
            self.stats.add_error(error_msg)
            return False

    async def index_all_content(self, limit: Optional[int] = None) -> IndexingStats:
        """Index all OneNote content."""
        console.print(Panel.fit("🚀 Starting OneNote Content Indexing", style="bold blue"))

        # Initialize service
        if not await self.initialize():
            return self.stats

        # Get all pages
        pages = await self.get_all_pages(limit)
        if not pages:
            console.print("[yellow]! No pages found to index[/yellow]")
            return self.stats

        # Index pages with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:

            task = progress.add_task("Indexing pages...", total=len(pages))

            for page in pages:
                progress.update(task, description=f"Indexing: {page.title[:30]}...")

                success = await self.index_page(page)
                if success:
                    progress.update(task, advance=1, description=f"OK {page.title[:30]}...")
                else:
                    progress.update(task, advance=1, description=f"X {page.title[:30]}...")

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.1)

        self.stats.end_time = datetime.now()
        return self.stats

    async def index_recent_content(self, days: int = 30) -> IndexingStats:
        """Index recent OneNote content."""
        console.print(Panel.fit(f"Indexing Recent Content ({days} days)", style="bold blue"))

        # For now, use the same logic as index_all_content
        # In the future, we could filter by modification date
        return await self.index_all_content(limit=100)  # Limit for recent content

    async def show_indexing_status(self) -> None:
        """Show current indexing status and statistics."""
        try:
            # Get vector store stats directly (no initialization needed)
            stats = await self.vector_store.get_storage_stats()

            # Create status table
            table = Table(title="Indexing Status", show_header=True, header_style="bold magenta")
            table.add_column("Metric", style="cyan", no_wrap=True)
            table.add_column("Value", style="white")

            table.add_row("Total Pages Indexed", str(stats.total_pages_indexed))
            table.add_row("Total Chunks", str(stats.total_chunks))
            table.add_row("Total Embeddings", str(stats.total_embeddings))
            table.add_row("Vector Dimensions", str(stats.embedding_dimensions))
            table.add_row("Storage Size (MB)", f"{stats.storage_size_mb:.2f}")
            table.add_row("Cache Hit Rate", f"{stats.cache_hit_rate:.1f}%")
            table.add_row("Last Indexed", str(stats.last_indexed) if stats.last_indexed else "Never")

            console.print(table)

        except Exception as e:
            self.logger.error(f"Failed to get indexing status: {e}")
            console.print(f"[red]X Failed to get status: {e}[/red]")


def show_indexing_results(stats: IndexingStats) -> None:
    """Display indexing results in a formatted table."""

    # Create results panel
    if stats.processed_pages > 0:
        title = f"OK Indexing Complete - {stats.processed_pages}/{stats.total_pages} pages processed"
        style = "bold green"
    else:
        title = "X Indexing Failed - No pages processed"
        style = "bold red"

    console.print(Panel.fit(title, style=style))

    # Create detailed results table
    table = Table(title="📈 Indexing Results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Total Pages Found", str(stats.total_pages))
    table.add_row("Successfully Processed", str(stats.processed_pages))
    table.add_row("Failed", str(stats.failed_pages))
    table.add_row("Success Rate", f"{stats.success_rate:.1f}%")
    table.add_row("Total Chunks Created", str(stats.total_chunks))
    table.add_row("Duration", str(stats.duration).split('.')[0])  # Remove microseconds

    console.print(table)

    # Show errors if any
    if stats.errors:
        console.print("\n[red]X Errors encountered:[/red]")
        for error in stats.errors[-5:]:  # Show last 5 errors
            console.print(f"  • {error}")
        if len(stats.errors) > 5:
            console.print(f"  ... and {len(stats.errors) - 5} more errors")


# CLI Commands
async def cmd_index_all_content(limit: Optional[int] = None) -> None:
    """Command to index all OneNote content."""
    service = ContentIndexingService()
    stats = await service.index_all_content(limit)
    show_indexing_results(stats)


async def cmd_index_recent_content(days: int = 30) -> None:
    """Command to index recent OneNote content."""
    service = ContentIndexingService()
    stats = await service.index_recent_content(days)
    show_indexing_results(stats)


async def cmd_show_status() -> None:
    """Command to show indexing status."""
    service = ContentIndexingService()
    await service.show_indexing_status()
