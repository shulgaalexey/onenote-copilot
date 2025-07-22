"""
Cache management commands for OneNote Copilot.

This module provides command implementations for cache initialization,
synchronization, status checking, and rebuilding.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..auth.microsoft_auth import MicrosoftAuthenticator
from ..config.logging import get_logger
from ..config.settings import get_settings
from ..storage.cache_manager import OneNoteCacheManager
from ..storage.incremental_sync import IncrementalSyncManager, SyncStrategy
from ..storage.onenote_fetcher import OneNoteContentFetcher
from ..tools.onenote_search import OneNoteSearchTool

console = Console()
logger = get_logger(__name__)


async def cmd_init_cache() -> None:
    """
    Initialize the OneNote cache for the first time.

    This performs a full cache initialization:
    - Creates cache directory structure
    - Downloads all OneNote content
    - Converts content to searchable format
    - Creates search indexes
    """
    try:
        console.print("[bold blue]Initializing OneNote Cache System[/bold blue]")
        console.print("[dim]This will download and index all your OneNote content for faster search...[/dim]\n")

        # Initialize settings and authenticator
        settings = get_settings()
        authenticator = MicrosoftAuthenticator(settings)

        # Check authentication
        console.print("[yellow]Checking authentication...[/yellow]")

        # Try to get access token (this will load from cache if available)
        token = await authenticator.get_access_token()
        if not token:
            console.print("[red]Not authenticated. Please run 'onenote-copilot --auth-only' first.[/red]")
            return

        console.print("[green]Authentication verified[/green]")

        # Get user profile for cache initialization
        user_profile = await authenticator.get_user_profile()
        user_id = user_profile.get('userPrincipalName', 'default_user') if user_profile else 'default_user'

        # Initialize cache manager
        cache_manager = OneNoteCacheManager(settings)

        # Check if cache already exists
        if cache_manager.cache_exists(user_id):
            console.print(f"[yellow]  Cache already exists for user: {user_id}[/yellow]")
            console.print("[dim]Use 'onenote-copilot cache --rebuild' to rebuild existing cache[/dim]")
            return

        # Initialize cache directory
        console.print("[yellow]Creating cache directory structure...[/yellow]")
        await cache_manager.initialize_user_cache(user_id)
        console.print("[green]Cache directories created[/green]")

        # Initialize content fetcher
        onenote_search = OneNoteSearchTool(authenticator, settings)
        content_fetcher = OneNoteContentFetcher(cache_manager, onenote_search)

        # Get content overview first
        console.print("[yellow]Scanning OneNote content...[/yellow]")
        with console.status("[bold blue]Fetching notebooks...", spinner="dots"):
            notebooks = await content_fetcher._get_all_notebooks()

        if not notebooks:
            console.print("[yellow]  No content found to cache.[/yellow]")
            console.print("[dim]Make sure you have notebooks in your OneNote account.[/dim]")
            return

        # Show content overview
        console.print(f"[green]Found {len(notebooks)} notebook(s)[/green]")

        # Start cache initialization
        console.print("\n[bold yellow]Starting cache initialization...[/bold yellow]")

        # Use bulk indexer for comprehensive content caching
        from ..storage.bulk_indexer import BulkContentIndexer

        bulk_indexer = BulkContentIndexer(
            cache_root=settings.onenote_cache_full_path,
            content_fetcher=content_fetcher,
            max_concurrent_pages=5
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("Initializing cache...", total=None)

            progress.update(task, description=f"Caching content from {len(notebooks)} notebooks...")

            # Use bulk indexer for proper content caching
            indexing_result = await bulk_indexer.index_all_content(
                notebooks=None,  # Index all content
                force_reindex=True
            )

            progress.update(task, description="Cache initialization complete!")

            # Show results
            console.print("\n[green]Cache initialization completed successfully![/green]")
            console.print(f"[dim]• Pages cached: {indexing_result.total_pages}[/dim]")
            console.print(f"[dim]• Successfully processed: {indexing_result.successful_pages}[/dim]")

            if indexing_result.failed_pages > 0:
                console.print(f"[yellow]  {indexing_result.failed_pages} pages failed to process[/yellow]")

            duration = indexing_result.get_elapsed_time()
            if duration:
                duration_seconds = duration.total_seconds()
                console.print(f"[dim]• Duration: {duration_seconds:.1f} seconds[/dim]")
            else:
                console.print("[dim]• Duration: Not available[/dim]")
                if len(indexing_result.failed_page_ids) > 3:
                    console.print(f"[dim]  • ... and {len(indexing_result.failed_page_ids) - 3} more failures[/dim]")

        # Show next steps
        console.print("\n[bold green]Your OneNote cache is ready![/bold green]")
        console.print("[dim]You can now use fast local search with:[/dim]")
        console.print("[cyan]  onenote-copilot[/cyan]")

    except Exception as e:
        logger.error(f"Cache initialization failed: {e}")
        console.print(f"[red]Cache initialization failed: {e}[/red]")
        raise


async def cmd_cache_status() -> None:
    """
    Show current cache status and statistics.
    """
    try:
        console.print("[bold blue]OneNote Cache Status[/bold blue]\n")

        # Initialize components
        settings = get_settings()
        authenticator = MicrosoftAuthenticator(settings)
        cache_manager = OneNoteCacheManager(settings)

        # Get user info by trying to get token (loads from cache if available)
        user_id = 'default_user'
        token = await authenticator.get_access_token()
        if token:
            user_profile = await authenticator.get_user_profile()
            if user_profile:
                user_id = user_profile.get('userPrincipalName', 'default_user')

        # Check cache existence
        cache_exists = cache_manager.cache_exists(user_id)

        # Create status table
        table = Table(title="Cache Information", border_style="blue")
        table.add_column("Property", style="bold")
        table.add_column("Value", style="cyan")

        # Authentication status
        auth_status = "✅ Authenticated" if authenticator.is_authenticated() else "❌ Not authenticated"
        table.add_row("Authentication", auth_status)
        table.add_row("User ID", user_id)

        # Cache status
        if cache_exists:
            table.add_row("Cache Status", "✅ Initialized")

            # Get cache statistics
            try:
                stats = await cache_manager.get_cache_statistics(user_id)
                table.add_row("Cache Directory", str(settings.cache_dir))
                table.add_row("Total Pages", str(stats.total_pages))
                table.add_row("Total Notebooks", str(stats.total_notebooks))
                table.add_row("Total Sections", str(stats.total_sections))
                table.add_row("Cache Size", f"{stats.total_size_mb:.1f} MB")
                table.add_row("Last Updated", stats.last_sync_time.strftime("%Y-%m-%d %H:%M:%S") if stats.last_sync_time else "Never")

                # Show sync age
                if stats.last_sync_time:
                    age = datetime.utcnow() - stats.last_sync_time
                    if age.days > 0:
                        age_str = f"{age.days} days ago"
                    elif age.seconds > 3600:
                        age_str = f"{age.seconds // 3600} hours ago"
                    else:
                        age_str = f"{age.seconds // 60} minutes ago"
                    table.add_row("Cache Age", age_str)

            except Exception as e:
                table.add_row("Cache Statistics", f"❌ Error: {e}")
        else:
            table.add_row("Cache Status", "❌ Not initialized")
            table.add_row("Cache Directory", str(settings.cache_dir))
            table.add_row("Recommendation", "Run 'onenote-copilot cache --init' to initialize")

        console.print(table)

        # Show recommendations based on status
        if not authenticator.is_authenticated():
            console.print("\n[yellow]💡 Recommendations:[/yellow]")
            console.print("  • Run 'onenote-copilot --auth-only' to authenticate first")
        elif not cache_exists:
            console.print("\n[yellow]💡 Recommendations:[/yellow]")
            console.print("  • Run 'onenote-copilot cache --init' to initialize cache")
        else:
            try:
                stats = await cache_manager.get_cache_statistics(user_id)
                if stats.last_sync_time and (datetime.utcnow() - stats.last_sync_time).days > 7:
                    console.print("\n[yellow]💡 Recommendations:[/yellow]")
                    console.print("  • Cache is older than 7 days, consider running 'onenote-copilot cache --sync'")
                else:
                    console.print("\n[green]✅ Cache is up to date and ready for use![/green]")
            except Exception:
                pass  # Skip recommendations if stats unavailable

    except Exception as e:
        logger.error(f"Cache status check failed: {e}")
        console.print(f"[red]❌ Failed to check cache status: {e}[/red]")
        raise


async def cmd_sync_cache() -> None:
    """
    Manually sync latest changes from OneNote to local cache.
    """
    try:
        console.print("[bold blue]Syncing OneNote Cache[/bold blue]")
        console.print("[dim]Checking for recent changes in your OneNote content...[/dim]\n")

        # Initialize components
        settings = get_settings()
        authenticator = MicrosoftAuthenticator(settings)
        cache_manager = OneNoteCacheManager(settings)

        # Check authentication and get token
        token = await authenticator.get_access_token()
        if not token:
            console.print("[red]❌ Not authenticated. Please run 'onenote-copilot --auth-only' first.[/red]")
            return

        # Get user info
        user_profile = await authenticator.get_user_profile()
        user_id = user_profile.get('userPrincipalName', 'default_user') if user_profile else 'default_user'

        # Check if cache exists
        if not cache_manager.cache_exists(user_id):
            console.print("[yellow]  Cache not initialized.[/yellow]")
            console.print("[dim]Run 'onenote-copilot cache --init' to initialize cache first.[/dim]")
            return

        console.print("[green]✅ Cache found, starting sync...[/green]")

        # Initialize content fetcher and sync manager
        onenote_search = OneNoteSearchTool(authenticator, settings)
        content_fetcher = OneNoteContentFetcher(cache_manager, onenote_search)
        sync_manager = IncrementalSyncManager(
            cache_root=settings.onenote_cache_full_path,
            content_fetcher=content_fetcher,
            cache_manager=cache_manager,
            default_strategy=SyncStrategy.NEWER_WINS
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=False,
        ) as progress:
            # Detect changes
            task = progress.add_task("Detecting changes...", total=None)
            changes = await sync_manager.detect_changes(user_id=user_id)

            if not changes:
                progress.update(task, description="No changes detected")
                console.print("\n[green]✅ Cache is already up to date![/green]")
                console.print("[dim]No changes found since last sync.[/dim]")
                return

            # Plan and execute sync
            progress.update(task, description=f"Planning sync for {len(changes)} changes...")
            operations = await sync_manager.plan_sync_operations(changes)

            progress.update(task, description=f"Syncing {len(operations)} operations...")
            report = await sync_manager.execute_sync(operations)

            progress.update(task, description="Sync completed!")

        # Show results
        console.print("\n[green]🎉 Cache sync completed successfully![/green]")

        # Create results table
        results_table = Table(title="Sync Results", border_style="green")
        results_table.add_column("Operation", style="bold")
        results_table.add_column("Count", justify="right", style="cyan")

        results_table.add_row("Pages Created", str(report.pages_created))
        results_table.add_row("Pages Updated", str(report.pages_updated))
        results_table.add_row("Pages Deleted", str(report.pages_deleted))

        duration = report.get_duration()
        if duration:
            duration_seconds = duration.total_seconds()
            results_table.add_row("Duration", f"{duration_seconds:.1f}s")
        else:
            results_table.add_row("Duration", "Not available")

        if report.errors:
            results_table.add_row("Errors", str(len(report.errors)), style="yellow")

        console.print(results_table)

        # Show errors if any
        if report.errors:
            console.print(f"\n[yellow]  {len(report.errors)} errors encountered:[/yellow]")
            for error in report.errors[:3]:  # Show first 3 errors
                console.print(f"[dim]  • {error}[/dim]")
            if len(report.errors) > 3:
                console.print(f"[dim]  • ... and {len(report.errors) - 3} more[/dim]")

    except Exception as e:
        logger.error(f"Cache sync failed: {e}")
        console.print(f"[red]❌ Cache sync failed: {e}[/red]")
        raise


async def cmd_rebuild_cache() -> None:
    """
    Clear and rebuild the entire cache from scratch.
    """
    try:
        console.print("[bold yellow]Rebuilding OneNote Cache[/bold yellow]")
        console.print("[dim]This will clear existing cache and rebuild from scratch...[/dim]\n")

        # Initialize components
        settings = get_settings()
        authenticator = MicrosoftAuthenticator(settings)
        cache_manager = OneNoteCacheManager(settings)

        # Check authentication and get token
        token = await authenticator.get_access_token()
        if not token:
            console.print("[red]❌ Not authenticated. Please run 'onenote-copilot --auth-only' first.[/red]")
            return

        # Get user info
        user_profile = await authenticator.get_user_profile()
        user_id = user_profile.get('userPrincipalName', 'default_user') if user_profile else 'default_user'

        # Check if cache exists and warn user
        cache_exists = cache_manager.cache_exists(user_id)
        if cache_exists:
            console.print(f"[yellow]  Existing cache found for user: {user_id}[/yellow]")
            console.print("[dim]This will permanently delete all cached content.[/dim]")

            # Confirm with user
            from typer import confirm
            if not confirm("Do you want to continue?"):
                console.print("[blue]  Rebuild cancelled by user[/blue]")
                return

            # Delete existing cache
            console.print("[yellow]Clearing existing cache...[/yellow]")
            await cache_manager.delete_user_cache(user_id)
            console.print("[green]Existing cache cleared[/green]")

        # Now initialize new cache (same as init command)
        console.print("[yellow]Initializing new cache...[/yellow]")
        await cmd_init_cache()

    except Exception as e:
        logger.error(f"Cache rebuild failed: {e}")
        console.print(f"[red]❌ Cache rebuild failed: {e}[/red]")
        raise
