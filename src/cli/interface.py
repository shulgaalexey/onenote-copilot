"""
Interactive CLI interface for OneNote Copilot.

Provides a Rich-based chat interface with streaming responses,
command handling, and beautiful terminal output.
"""

import asyncio
import sys
from datetime import datetime
from typing import Any, Optional

from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt

from ..agents.onenote_agent import OneNoteAgent
from ..auth.microsoft_auth import AuthenticationError
from ..config.settings import get_settings
from ..models.responses import StreamingChunk
from ..tools.onenote_search import OneNoteSearchError
from .formatting import CLIFormatter, create_progress_spinner


class OneNoteCLI:
    """
    Interactive CLI for OneNote Copilot.

    Provides a beautiful, responsive chat interface for natural language
    OneNote search and interaction using Rich library components.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the OneNote CLI.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()

        # Initialize console and formatter
        self.console = Console(
            color_system="auto" if self.settings.cli_color_enabled else None
        )
        self.formatter = CLIFormatter(
            console=self.console,
            enable_color=self.settings.cli_color_enabled,
            enable_markdown=self.settings.cli_markdown_enabled
        )

        # Initialize agent
        self.agent = OneNoteAgent(self.settings)

        # CLI state
        self.running = True
        self.conversation_history = []

        # Commands mapping
        self.commands = {
            '/help': self._show_help,
            '/notebooks': self._list_notebooks,
            '/recent': self._show_recent_pages,
            '/starters': self._show_conversation_starters,
            '/clear': self._clear_history,
            '/quit': self._quit_chat,
            '/exit': self._quit_chat
        }

    async def start_chat(self) -> None:
        """Start the interactive chat session."""
        try:
            # Initialize agent
            await self._initialize_agent()

            # Show welcome message
            if self.settings.cli_welcome_enabled:
                self._show_welcome()

            # Main chat loop
            while self.running:
                try:
                    # Get user input
                    user_input = await self._get_user_input()

                    if not user_input.strip():
                        continue

                    # Handle commands
                    if user_input.startswith('/'):
                        if await self._handle_command(user_input):
                            continue
                        else:
                            break

                    # Process user message
                    await self._process_user_message(user_input)

                except KeyboardInterrupt:
                    self.console.print("\n\n[yellow]💡 Use '/quit' to exit gracefully or Ctrl+C again to force quit.[/yellow]")
                    try:
                        # Give user a chance to quit gracefully
                        await asyncio.sleep(2)
                    except KeyboardInterrupt:
                        break
                except EOFError:
                    break
                except Exception as e:
                    self.console.print(self.formatter.format_error(f"Unexpected error: {e}"))
                    continue

            self._show_goodbye()

        except Exception as e:
            self.console.print(self.formatter.format_error(f"Failed to start OneNote Copilot: {e}"))
            sys.exit(1)

    async def _initialize_agent(self) -> None:
        """Initialize the OneNote agent with progress indicator."""
        with self.console.status("[bold blue]Initializing OneNote Copilot...", spinner="dots"):
            try:
                await self.agent.initialize()
                self.console.print("[green]✅ OneNote Copilot initialized successfully![/green]")
            except AuthenticationError:
                self.console.print("[yellow]🔐 Authentication required - browser will open for login.[/yellow]")
                await self.agent.initialize()
                self.console.print("[green]✅ Authentication successful![/green]")
            except Exception as e:
                raise Exception(f"Initialization failed: {e}")

    def _show_welcome(self) -> None:
        """Display welcome message."""
        welcome_panel = self.formatter.format_welcome_message()
        self.console.print(welcome_panel)
        self.console.print()  # Add spacing

    async def _get_user_input(self) -> str:
        """
        Get user input with timestamp and formatting.

        Returns:
            User input string
        """
        timestamp = datetime.now().strftime("%H:%M")
        prompt_text = f"[dim]{timestamp}[/dim] [bold cyan]You:[/bold cyan] "

        # Use Rich's prompt for better formatting
        return Prompt.ask(prompt_text, console=self.console)

    async def _process_user_message(self, message: str) -> None:
        """
        Process user message and display streaming response.

        Args:
            message: User message to process
        """
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now()
        })

        # Show user message
        timestamp = datetime.now().strftime("%H:%M")
        self.console.print(f"\n[dim]{timestamp}[/dim] [bold cyan]You:[/bold cyan] {message}")

        # Process and stream response
        response_parts = []

        with Live(
            self.formatter.create_loading_panel("🤔 Thinking about your question..."),
            console=self.console,
            refresh_per_second=10
        ) as live:

            try:
                async for chunk in self.agent.process_query(message):
                    if chunk.type == "text":
                        response_parts.append(chunk.content)

                        # Update live display with accumulated response
                        live.update(self.formatter.format_partial_response(response_parts))

                        if chunk.is_final:
                            break

                    elif chunk.type == "status":
                        # Update status in loading panel
                        live.update(self.formatter.create_loading_panel(chunk.content))

                    elif chunk.type == "sources":
                        # Handle sources if needed
                        sources_data = chunk.metadata.get("sources", [])
                        if sources_data:
                            # Could display sources in a separate panel
                            pass

                    elif chunk.type == "error":
                        # Display error
                        live.update(self.formatter.format_error(chunk.content, "Search Error"))
                        break

                # Add response to conversation history
                if response_parts:
                    full_response = "".join(response_parts)
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": full_response,
                        "timestamp": datetime.now()
                    })

            except AuthenticationError:
                live.update(self.formatter.format_error(
                    "Authentication expired. Please restart the application to re-authenticate.",
                    "Authentication Error"
                ))
            except OneNoteSearchError as e:
                live.update(self.formatter.format_error(str(e), "OneNote Search Error"))
            except Exception as e:
                live.update(self.formatter.format_error(f"Unexpected error: {e}", "System Error"))

        self.console.print()  # Add spacing after response

    async def _handle_command(self, command: str) -> bool:
        """
        Handle CLI commands.

        Args:
            command: Command string starting with '/'

        Returns:
            True to continue chat loop, False to exit
        """
        command = command.strip().lower()

        if command in self.commands:
            return await self.commands[command]()
        else:
            self.console.print(f"[red]❌ Unknown command: {command}[/red]")
            self.console.print("💡 Type [cyan]/help[/cyan] for available commands.")
            return True

    async def _show_help(self) -> bool:
        """Show help information."""
        help_panel = self.formatter.format_help()
        self.console.print(help_panel)
        return True

    async def _list_notebooks(self) -> bool:
        """List OneNote notebooks."""
        try:
            with self.console.status("[bold blue]Getting your OneNote notebooks...", spinner="dots"):
                notebooks = await self.agent.search_tool.get_notebooks()

            if notebooks:
                table = self.formatter.format_notebooks(notebooks)
                self.console.print(table)
            else:
                self.console.print("[yellow]📓 No notebooks found.[/yellow]")

            return True

        except Exception as e:
            error_panel = self.formatter.format_error(f"Failed to get notebooks: {e}")
            self.console.print(error_panel)
            return True

    async def _show_recent_pages(self) -> bool:
        """Show recently modified pages."""
        try:
            with self.console.status("[bold blue]Getting recent pages...", spinner="dots"):
                recent_pages = await self.agent.search_tool.get_recent_pages(10)

            if recent_pages:
                table = self.formatter.format_recent_pages(recent_pages)
                self.console.print(table)
            else:
                self.console.print("[yellow]📄 No recent pages found.[/yellow]")

            return True

        except Exception as e:
            error_panel = self.formatter.format_error(f"Failed to get recent pages: {e}")
            self.console.print(error_panel)
            return True

    async def _show_conversation_starters(self) -> bool:
        """Show conversation starter examples."""
        starters = self.agent.get_conversation_starters()
        starters_panel = self.formatter.format_conversation_starters(starters)
        self.console.print(starters_panel)
        return True

    async def _clear_history(self) -> bool:
        """Clear conversation history."""
        self.conversation_history.clear()
        self.console.clear()

        if self.settings.cli_welcome_enabled:
            self._show_welcome()

        self.console.print("[green]✅ Conversation history cleared![/green]")
        return True

    async def _quit_chat(self) -> bool:
        """Quit the chat application."""
        self.running = False
        return False

    def _show_goodbye(self) -> None:
        """Display goodbye message."""
        goodbye_text = """
👋 Thank you for using OneNote Copilot!

Your OneNote content is always just a question away. Come back anytime to explore your notes with natural language.

**Feedback & Support:**
- Found this helpful? Great!
- Having issues? Check your OneNote permissions and internet connection
- Want new features? Consider contributing to the project

Stay organized! 📚✨
        """

        if self.settings.cli_markdown_enabled:
            from rich.markdown import Markdown
            content = Markdown(goodbye_text.strip())
        else:
            from rich.text import Text
            content = Text(goodbye_text.strip())

        from rich.panel import Panel
        goodbye_panel = Panel(
            content,
            title="[bold blue]Goodbye![/bold blue]",
            border_style="blue",
            padding=(1, 2)
        )

        self.console.print(goodbye_panel)

    def get_conversation_summary(self) -> dict:
        """
        Get a summary of the current conversation.

        Returns:
            Dictionary with conversation statistics
        """
        user_messages = [msg for msg in self.conversation_history if msg["role"] == "user"]
        assistant_messages = [msg for msg in self.conversation_history if msg["role"] == "assistant"]

        return {
            "total_messages": len(self.conversation_history),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "session_start": self.conversation_history[0]["timestamp"] if self.conversation_history else None,
            "last_message": self.conversation_history[-1]["timestamp"] if self.conversation_history else None
        }


async def run_cli() -> None:
    """
    Run the OneNote Copilot CLI application.

    This is the main entry point for the CLI application.
    """
    try:
        cli = OneNoteCLI()
        await cli.start_chat()
    except KeyboardInterrupt:
        print("\n👋 OneNote Copilot interrupted. Goodbye!")
    except Exception as e:
        print(f"❌ OneNote Copilot failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    """Run CLI when module is executed directly."""
    asyncio.run(run_cli())
