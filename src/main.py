"""
OneNote Copilot - Main Application Entry Point

A powerful CLI tool that brings AI-powered natural language search to your OneNote content.
Built with LangGraph for intelligent conversation flow and Rich for beautiful terminal output.

Usage:
    python -m src.main                    # Start interactive chat
    python -m src.main --auth-only        # Only authenticate, don't start chat
    python -m src.main --version          # Show version information
    python -m src.main --debug           # Enable debug logging
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.traceback import install

from .auth.microsoft_auth import MicrosoftAuthenticator
from .cli.interface import OneNoteCLI
from .commands.index_content import (cmd_index_all_content,
                                     cmd_index_recent_content, cmd_show_status)
from .config.logging import get_logger, setup_logging
from .config.settings import get_settings

# Configure Rich traceback handling
install(show_locals=True)

# Typer app
app = typer.Typer(
    name="onenote-copilot",
    help="🤖 AI-powered natural language search for your OneNote content",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=False
)

# Console for output
console = Console()

# Version info
__version__ = "1.0.0"


def show_system_info() -> None:
    """Display system and environment information."""
    settings = get_settings()

    info_text = f"""
**OneNote Copilot v{__version__}**

**System Information:**
- Python: {sys.version.split()[0]}
- Platform: {sys.platform}
- Settings file: {settings.config_dir / "settings.toml"}
- Cache directory: {settings.cache_dir}

**Configuration:**
- OpenAI Model: {settings.openai_model}
- CLI Colors: {"Enabled" if settings.cli_color_enabled else "Disabled"}
- CLI Markdown: {"Enabled" if settings.cli_markdown_enabled else "Disabled"}
- Debug Mode: {"Enabled" if settings.debug_enabled else "Disabled"}

**Microsoft Graph API:**
- Client ID: {settings.azure_client_id}
- Scopes: {', '.join(settings.graph_api_scopes)}
- Cache: {settings.token_cache_file}
    """

    from rich.markdown import Markdown
    panel = Panel(
        Markdown(info_text.strip()),
        title="[bold blue]System Information[/bold blue]",
        border_style="blue",
        padding=(1, 2)
    )

    console.print(panel)


async def authenticate_only() -> bool:
    """
    Perform authentication without starting the chat interface.

    Returns:
        True if authentication successful, False otherwise
    """
    logger = get_logger(__name__)

    try:
        settings = get_settings()
        logger.info("🔑 Initializing Microsoft authenticator...")
        authenticator = MicrosoftAuthenticator(settings)

        console.print("[bold blue]🔐 Starting Microsoft authentication...[/bold blue]")
        console.print("📖 This will open your web browser for secure login.")
        console.print()

        with console.status("[bold blue]Waiting for authentication...", spinner="dots"):
            logger.info("🌐 Requesting access token...")
            token = await authenticator.get_access_token()

        if token:
            logger.info("✅ Authentication successful, token cached")
            console.print("[green]✅ Authentication successful![/green]")
            console.print(f"🎫 Token cached to: {settings.token_cache_file}")
            return True
        else:
            logger.warning("❌ Authentication failed - no token received")
            console.print("[red]❌ Authentication failed.[/red]")
            return False

    except Exception as e:
        logger.error(f"❌ Authentication error: {e}", exc_info=True)
        console.print(f"[red]❌ Authentication error: {e}[/red]")
        return False


def check_dependencies() -> bool:
    """
    Check that all required dependencies are available.

    Returns:
        True if all dependencies are available, False otherwise
    """
    missing_deps = []

    # Check critical dependencies
    try:
        import openai
    except ImportError:
        missing_deps.append("openai")

    try:
        import msal
    except ImportError:
        missing_deps.append("msal")

    try:
        import httpx
    except ImportError:
        missing_deps.append("httpx")

    try:
        import rich
    except ImportError:
        missing_deps.append("rich")

    try:
        import langgraph
    except ImportError:
        missing_deps.append("langgraph")

    try:
        import langchain_openai
    except ImportError:
        missing_deps.append("langchain-openai")

    if missing_deps:
        console.print("[red]❌ Missing required dependencies:[/red]")
        for dep in missing_deps:
            console.print(f"   - {dep}")
        console.print()
        console.print("[yellow]💡 Install dependencies with:[/yellow]")
        console.print(f"   [cyan]pip install {' '.join(missing_deps)}[/cyan]")
        console.print("   [cyan]# OR[/cyan]")
        console.print("   [cyan]pip install -r requirements.txt[/cyan]")
        return False

    return True


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    auth_only: bool = typer.Option(
        False,
        "--auth-only",
        help="🔐 Only perform authentication, don't start chat interface"
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="🐛 Enable debug logging"
    ),
    show_info: bool = typer.Option(
        False,
        "--info",
        help="ℹ️  Show system information and exit"
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="📋 Show version information and exit"
    )
) -> None:
    """
    🤖 Start OneNote Copilot - AI-powered natural language search for OneNote.

    OneNote Copilot brings the power of AI to your OneNote content, allowing you to
    search and interact with your notes using natural language. Ask questions like:

    • "Show me notes about project planning from last month"
    • "Find my meeting notes with Sarah"
    • "What did I write about vacation ideas?"

    **First Time Setup:**
    1. Make sure you have a Microsoft account with OneNote content
    2. Run this command to authenticate: `onenote-copilot --auth-only`
    3. Start chatting: `onenote-copilot`

    **Examples:**
    - Start interactive chat: `onenote-copilot`
    - Authenticate only: `onenote-copilot --auth-only`
    - Debug mode: `onenote-copilot --debug`
    - System info: `onenote-copilot --info`
    """

    # Handle version flag
    if version:
        console.print(f"[bold blue]OneNote Copilot v{__version__}[/bold blue]")
        return

    # Setup comprehensive logging system early
    settings = get_settings()
    console_level = "DEBUG" if debug else settings.log_level
    setup_logging(
        console=console,
        clear_log_file=settings.log_clear_on_startup,
        console_level=console_level,
        file_level="DEBUG"  # Always capture debug in files
    )

    # Get logger for main module
    logger = get_logger(__name__)
    logger.info(f"OneNote Copilot v{__version__} starting...")

    # Handle info flag
    if show_info:
        show_system_info()
        return

    # If no command was invoked, run the main chat interface
    if ctx.invoked_subcommand is None:
        # Check dependencies
        logger.info("🔍 Checking dependencies...")
        if not check_dependencies():
            logger.error("❌ Dependency check failed")
            raise typer.Exit(1)
        logger.info("✅ All dependencies available")

        # Handle auth-only mode
        if auth_only:
            logger.info("🔐 Running authentication-only mode...")
            success = asyncio.run(authenticate_only())
            if not success:
                logger.error("❌ Authentication failed")
                raise typer.Exit(1)
            logger.info("✅ Authentication completed successfully")
            return

        # Start the main application
        try:
            console.print("[bold blue]Starting OneNote Copilot...[/bold blue]")
            console.print()

            # Run the CLI interface
            logger.info("🎯 Starting main application interface...")
            asyncio.run(run_main_app(debug))

        except KeyboardInterrupt:
            logger.info("👋 Application interrupted by user")
            console.print("\n[yellow]👋 OneNote Copilot interrupted. Goodbye![/yellow]")
        except Exception as e:
            logger.error(f"❌ Application failed to start: {e}", exc_info=debug)
            if debug:
                console.print_exception()
            else:
                console.print(f"[red]X Failed to start OneNote Copilot: {e}[/red]")
                console.print("[dim]💡 Use --debug flag for detailed error information[/dim]")
            raise typer.Exit(1)


async def run_main_app(debug: bool = False) -> None:
    """
    Run the main OneNote Copilot application.

    Args:
        debug: Enable debug mode
    """
    logger = get_logger(__name__)

    try:
        logger.info("🎬 Initializing OneNote CLI interface...")

        # Initialize and run CLI
        cli = OneNoteCLI()
        logger.info("💬 Starting chat interface...")
        await cli.start_chat()

        # Show conversation summary if debug enabled
        if debug:
            summary = cli.get_conversation_summary()
            if summary["total_messages"] > 0:
                logger.info(f"📊 Session Summary: {summary['total_messages']} messages exchanged")
                console.print(f"\n[dim]📊 Session Summary: {summary['total_messages']} messages exchanged[/dim]")

    except Exception as e:
        logger.error(f"❌ Application error: {e}", exc_info=debug)
        if debug:
            console.print_exception()
        raise


@app.command()
def config() -> None:
    """
    🔧 Show current configuration and help with setup.

    Display configuration file location, current settings, and help
    with common setup issues.
    """
    try:
        settings = get_settings()
        show_system_info()

        console.print()
        console.print("[bold yellow]🔧 Configuration Help:[/bold yellow]")

        help_text = """
**Environment Variables:**
You can override settings using environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `AZURE_CLIENT_ID`: Azure app client ID (optional, uses default)
- `ONENOTE_DEBUG`: Enable debug mode (true/false)

**Common Issues:**
1. **Authentication failing**: Try `onenote-copilot --auth-only` first
2. **No search results**: Check OneNote permissions in your Microsoft account
3. **Slow responses**: Check your internet connection and OpenAI API status

**Cache Locations:**
- Token cache: {cache_dir}/msal_token_cache.json
- Settings: {config_dir}/settings.toml

**Getting Help:**
- Use `--debug` flag for detailed error information
- Check that you have OneNote content in your Microsoft account
- Ensure your OpenAI API key has sufficient credits
        """

        from rich.markdown import Markdown
        formatted_help = help_text.format(
            cache_dir=settings.cache_dir,
            config_dir=settings.config_dir
        )

        console.print(Markdown(formatted_help.strip()))

    except Exception as e:
        console.print(f"[red]❌ Error loading configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def index(
    initial: bool = typer.Option(
        False,
        "--initial",
        help="🚀 Perform initial indexing of all OneNote content"
    ),
    sync: bool = typer.Option(
        False,
        "--sync",
        help="🔄 Sync recent changes (last 30 days)"
    ),
    recent_days: int = typer.Option(
        30,
        "--recent-days",
        help="📅 Number of recent days to sync (default: 30)"
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="🔢 Limit number of pages to process (for testing)"
    ),
    status: bool = typer.Option(
        False,
        "--status",
        help="📊 Show current indexing status and statistics"
    )
) -> None:
    """
    🔍 Index OneNote content for semantic search.

    This command processes your OneNote content and creates vector embeddings
    for semantic search capabilities. Choose from different indexing modes:

    **Initial Indexing** (--initial):
    Process all accessible OneNote content. Use this for first-time setup
    or when you want to rebuild the entire search index.

    **Sync Mode** (--sync):
    Process recent changes only. Faster option for regular updates.

    **Status Check** (--status):
    Display current indexing statistics without processing content.

    **Examples:**
    - First-time setup: `onenote-copilot index --initial`
    - Regular updates: `onenote-copilot index --sync`
    - Custom timeframe: `onenote-copilot index --sync --recent-days 7`
    - Check status: `onenote-copilot index --status`
    - Test with limit: `onenote-copilot index --initial --limit 10`
    """
    try:
        if status:
            # Show indexing status
            asyncio.run(cmd_show_status())
        elif initial:
            # Perform initial indexing
            console.print("[yellow]🚀 Starting initial content indexing...[/yellow]")
            asyncio.run(cmd_index_all_content(limit))
        elif sync:
            # Perform sync indexing
            console.print(f"[yellow]🔄 Syncing recent content ({recent_days} days)...[/yellow]")
            asyncio.run(cmd_index_recent_content(recent_days))
        else:
            # Default to showing status if no specific action requested
            console.print("[blue]ℹ️  No action specified. Showing current status:[/blue]")
            asyncio.run(cmd_show_status())
            console.print("\n[dim]💡 Use --initial for first-time indexing or --sync for updates[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️  Indexing cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Indexing command failed: {e}")
        console.print(f"[red]X Indexing failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def logout(
    clear_logs: bool = typer.Option(
        False,
        "--clear-logs",
        help="🗑️ Also clear application logs"
    ),
    keep_vector_db: bool = typer.Option(
        False,
        "--keep-vector-db",
        help="💾 Keep vector database (don't clear indexed content)"
    ),
    keep_cache: bool = typer.Option(
        False,
        "--keep-cache",
        help="💾 Keep embedding cache"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="🚨 Force logout without confirmation"
    ),
    status_only: bool = typer.Option(
        False,
        "--status",
        help="📊 Show logout status without performing logout"
    )
) -> None:
    """
    🔓 Logout current user and clear all user data.

    This command performs a complete logout by:
    - Clearing authentication tokens and session data
    - Removing vector database with indexed OneNote content
    - Clearing embedding cache to free up space
    - Removing temporary files and caches

    This allows another user to login with a clean slate.

    **Data Cleared by Default:**
    - Authentication tokens and MSAL cache
    - Vector database (all indexed OneNote content)
    - Embedding cache (stored embeddings)
    - Temporary files and caches

    **Optional Data Clearing:**
    - Application logs (use --clear-logs)

    **Preserve Data:**
    - Use --keep-vector-db to preserve indexed content
    - Use --keep-cache to preserve embedding cache

    **Examples:**
    - Full logout: `onenote-copilot logout`
    - Check what will be cleared: `onenote-copilot logout --status`
    - Logout but keep indexed content: `onenote-copilot logout --keep-vector-db`
    - Force logout without confirmation: `onenote-copilot logout --force`
    - Logout and clear logs: `onenote-copilot logout --clear-logs`
    """
    # Initialize logging first
    settings = get_settings()
    setup_logging(
        console=console,
        clear_log_file=False,  # Don't clear logs for command-only execution
        console_level=settings.log_level,
        file_level="DEBUG"
    )

    # Import LogoutService after logging is initialized
    from .commands.logout import LogoutService

    try:
        logout_service = LogoutService()

        if status_only:
            # Show logout status
            console.print("[blue]📊 Checking user data status...[/blue]")
            status = asyncio.run(logout_service.get_logout_status())

            from rich.table import Table
            table = Table(title="User Data Status", border_style="blue")
            table.add_column("Data Type", style="bold")
            table.add_column("Status", style="cyan")
            table.add_column("Details", style="dim")

            # Authentication status
            auth_status = "✅ Active" if status["authentication"]["token_cache_exists"] else "❌ None"
            auth_details = f"{status['authentication']['cache_file_size']} bytes" if status["authentication"]["token_cache_exists"] else "No cache file"
            table.add_row("Authentication", auth_status, auth_details)

            # Vector database status
            db_status = "✅ Exists" if status["vector_database"]["exists"] else "❌ None"
            db_details = f"{status['vector_database']['total_embeddings']} embeddings, {status['vector_database']['storage_size_mb']:.1f} MB" if status["vector_database"]["exists"] else "No database"
            table.add_row("Vector Database", db_status, db_details)

            # Cache status
            cache_status = "✅ Exists" if status["embedding_cache"]["exists"] else "❌ None"
            cache_details = f"{status['embedding_cache']['cache_entries']} entries" if status["embedding_cache"]["exists"] else "No cache"
            table.add_row("Embedding Cache", cache_status, cache_details)

            # Temporary files
            temp_status = "✅ Found" if status["temporary_files"]["count"] > 0 else "❌ None"
            temp_details = f"{status['temporary_files']['count']} files, {status['temporary_files']['total_size_mb']:.1f} MB" if status["temporary_files"]["count"] > 0 else "No temp files"
            table.add_row("Temporary Files", temp_status, temp_details)

            console.print(table)
            console.print("\n[dim]💡 Use 'onenote-copilot logout' to clear user data for new login[/dim]")
            return

        # Show what will be cleared
        console.print("[yellow]🔓 Preparing to logout current user...[/yellow]")

        operations = []
        if not keep_vector_db:
            operations.append("Vector database (indexed OneNote content)")
        if not keep_cache:
            operations.append("Embedding cache")
        operations.extend([
            "Authentication tokens and session data",
            "Temporary files and caches"
        ])
        if clear_logs:
            operations.append("Application logs")

        console.print("\n[bold]The following data will be cleared:[/bold]")
        for op in operations:
            console.print(f"  • {op}")

        if not force:
            console.print(f"\n[yellow]⚠️  This action cannot be undone![/yellow]")
            confirm = typer.confirm("Do you want to continue?")
            if not confirm:
                console.print("[blue]ℹ️  Logout cancelled by user[/blue]")
                return

        # Perform logout
        console.print(f"\n[yellow]🔄 Logging out user and clearing data...[/yellow]")

        success = asyncio.run(logout_service.logout_user(
            clear_logs=clear_logs,
            clear_vector_db=not keep_vector_db,
            clear_embedding_cache=not keep_cache
        ))

        if success:
            console.print(f"\n[green]✅ User logout completed successfully![/green]")
            console.print(f"[dim]💡 Another user can now login with: onenote-copilot --auth-only[/dim]")
        else:
            console.print(f"\n[yellow]⚠️  Logout completed with some warnings[/yellow]")
            console.print(f"[dim]Check logs for details about any failed operations[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️  Logout cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Logout command failed: {e}")
        console.print(f"[red]❌ Logout failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def fix_auth(
    force_clear: bool = typer.Option(
        False,
        "--force-clear",
        help="🧹 Force clear all authentication state and cache files"
    ),
    show_guidance: bool = typer.Option(
        True,
        "--guidance/--no-guidance",
        help="📋 Show troubleshooting guidance (default: True)"
    )
) -> None:
    """
    🔧 Fix authentication issues like 'server_error' after user logout.

    This command helps resolve common authentication problems:
    - OAuth2 server_error from Microsoft
    - Session conflicts between users
    - Stale authentication cache issues
    - Browser authentication cookie conflicts

    **What this command does:**
    - Analyzes current authentication state
    - Clears problematic cache files and state
    - Provides specific guidance for the detected issues
    - Offers browser-specific troubleshooting steps

    **Common scenarios:**
    - Use after getting "Authentication Failed - server_error" in browser
    - Use when switching between different Microsoft accounts
    - Use when authentication works in incognito but not regular browser
    - Use when previous user logout didn't fully clear session

    **Examples:**
    - Analyze and fix: `onenote-copilot fix-auth`
    - Force clear everything: `onenote-copilot fix-auth --force-clear`
    - Fix without guidance: `onenote-copilot fix-auth --no-guidance`
    """
    # Initialize logging
    settings = get_settings()
    setup_logging(
        console=console,
        clear_log_file=False,
        console_level=settings.log_level,
        file_level="DEBUG"
    )

    logger = get_logger(__name__)

    try:
        console.print("[blue]🔧 Authentication Troubleshooting Tool[/blue]")
        console.print("[dim]Analyzing authentication state and resolving issues...[/dim]\n")

        # Initialize authenticator
        authenticator = MicrosoftAuthenticator()

        if force_clear:
            console.print("[yellow]🧹 Force clearing all authentication state...[/yellow]")
            success = authenticator.force_clear_all_auth_state()

            if success:
                console.print("[green]✅ Force clear completed successfully[/green]")
            else:
                console.print("[yellow]⚠️  Force clear completed with some warnings[/yellow]")
        else:
            # Analyze current state
            console.print("[blue]📊 Analyzing authentication state...[/blue]")

            # Check for common issues
            cache_file = settings.token_cache_path
            cache_exists = cache_file.exists()

            if cache_exists:
                cache_size = cache_file.stat().st_size
                console.print(f"[yellow]⚠️  Found authentication cache: {cache_file} ({cache_size} bytes)[/yellow]")
                console.print("[dim]This might contain stale session data causing conflicts[/dim]")

                # Offer to clear it
                if typer.confirm("Clear the authentication cache?"):
                    authenticator.force_clear_all_auth_state()
                    console.print("[green]✅ Authentication cache cleared[/green]")
            else:
                console.print("[green]✅ No stale authentication cache found[/green]")

        if show_guidance:
            console.print("\n" + "="*60)
            console.print("[bold blue]📋 Authentication Troubleshooting Guidance[/bold blue]")
            console.print("="*60)

            console.print("\n[bold yellow]🚨 For 'server_error' issues:[/bold yellow]")
            console.print("1. [cyan]Clear browser data[/cyan] for *.microsoftonline.com and *.live.com")
            console.print("2. [cyan]Try incognito/private browsing[/cyan] mode for authentication")
            console.print("3. [cyan]Restart your browser[/cyan] completely")
            console.print("4. [cyan]Wait 5-10 minutes[/cyan] for Microsoft's session cleanup")

            console.print("\n[bold yellow]🌐 Browser-specific steps:[/bold yellow]")
            console.print("[dim]Chrome/Edge:[/dim] Settings → Privacy → Clear browsing data → Cookies and site data")
            console.print("[dim]Firefox:[/dim] Settings → Privacy → Clear Data → Cookies and Site Data")
            console.print("[dim]Safari:[/dim] Develop → Empty Caches, Safari → Clear History")

            console.print("\n[bold yellow]🔄 If problems persist:[/bold yellow]")
            console.print("1. [cyan]Use different browser[/cyan] or [cyan]incognito mode[/cyan]")
            console.print("2. [cyan]Check network/firewall[/cyan] - corporate networks may block OAuth2")
            console.print("3. [cyan]Verify port 8080[/cyan] is available: `netstat -an | findstr :8080`")
            console.print("4. [cyan]Try again later[/cyan] - Microsoft OAuth2 servers may be temporarily unavailable")

            console.print("\n[bold green]✅ Next steps:[/bold green]")
            console.print("After applying fixes above, try: [cyan]onenote-copilot --auth-only[/cyan]")

        console.print(f"\n[green]🎯 Authentication troubleshooting completed![/green]")
        console.print(f"[dim]If issues persist, check the full troubleshooting guide: docs/AUTH_TROUBLESHOOTING.md[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️  Authentication troubleshooting cancelled[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Auth troubleshooting failed: {e}")
        console.print(f"[red]❌ Authentication troubleshooting failed: {e}[/red]")
        raise typer.Exit(1)


def cli_main() -> None:
    """
    Entry point for CLI execution.

    This function is called when the package is run as a module or script.
    """
    app()


if __name__ == "__main__":
    cli_main()
