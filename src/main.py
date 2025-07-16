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
from rich.logging import RichHandler
from rich.panel import Panel
from rich.traceback import install

from .auth.microsoft_auth import MicrosoftAuthenticator
from .cli.interface import OneNoteCLI
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


def setup_logging(debug: bool = False) -> None:
    """
    Set up logging with Rich handler.

    Args:
        debug: Enable debug level logging
    """
    level = logging.DEBUG if debug else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                show_path=debug,
                show_time=debug
            )
        ]
    )

    # Set specific logger levels
    if not debug:
        # Reduce noise from external libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("msal").setLevel(logging.WARNING)


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
    try:
        settings = get_settings()
        authenticator = MicrosoftAuthenticator(settings)

        console.print("[bold blue]🔐 Starting Microsoft authentication...[/bold blue]")
        console.print("📖 This will open your web browser for secure login.")
        console.print()

        with console.status("[bold blue]Waiting for authentication...", spinner="dots"):
            token = await authenticator.get_access_token()

        if token:
            console.print("[green]✅ Authentication successful![/green]")
            console.print(f"🎫 Token cached to: {settings.token_cache_file}")
            return True
        else:
            console.print("[red]❌ Authentication failed.[/red]")
            return False

    except Exception as e:
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

    # Setup logging
    setup_logging(debug)

    # Handle info flag
    if show_info:
        show_system_info()
        return

    # If no command was invoked, run the main chat interface
    if ctx.invoked_subcommand is None:
        # Check dependencies
        if not check_dependencies():
            raise typer.Exit(1)

        # Handle auth-only mode
        if auth_only:
            success = asyncio.run(authenticate_only())
            if not success:
                raise typer.Exit(1)
            return

        # Start the main application
        try:
            console.print("[bold blue]🚀 Starting OneNote Copilot...[/bold blue]")
            console.print()

            # Run the CLI interface
            asyncio.run(run_main_app(debug))

        except KeyboardInterrupt:
            console.print("\n[yellow]👋 OneNote Copilot interrupted. Goodbye![/yellow]")
        except Exception as e:
            if debug:
                console.print_exception()
            else:
                console.print(f"[red]❌ Failed to start OneNote Copilot: {e}[/red]")
                console.print("[dim]💡 Use --debug flag for detailed error information[/dim]")
            raise typer.Exit(1)


async def run_main_app(debug: bool = False) -> None:
    """
    Run the main OneNote Copilot application.

    Args:
        debug: Enable debug mode
    """
    try:
        # Initialize and run CLI
        cli = OneNoteCLI()
        await cli.start_chat()

        # Show conversation summary if debug enabled
        if debug:
            summary = cli.get_conversation_summary()
            if summary["total_messages"] > 0:
                console.print(f"\n[dim]📊 Session Summary: {summary['total_messages']} messages exchanged[/dim]")

    except Exception as e:
        logging.error(f"Application error: {e}")
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


def cli_main() -> None:
    """
    Entry point for CLI execution.

    This function is called when the package is run as a module or script.
    """
    app()


if __name__ == "__main__":
    cli_main()
