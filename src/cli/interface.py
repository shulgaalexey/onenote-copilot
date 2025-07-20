"""
Interactive CLI interface for OneNote Copilot.

Provides a Rich-based chat interface with streaming responses,
command handling, and beautiful terminal output.
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Any, Optional

from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt

from ..agents.onenote_agent import OneNoteAgent
from ..auth.microsoft_auth import AuthenticationError
from ..config.logging import log_performance, logged
from ..config.settings import get_settings
from ..models.responses import StreamingChunk
from ..tools.onenote_search import OneNoteSearchError
from .formatting import CLIFormatter, create_progress_spinner

logger = logging.getLogger(__name__)


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
            '/content': self._show_page_content,
            '/index': self._index_content,
            '/semantic': self._semantic_search,
            '/stats': self._show_semantic_stats,
            '/reset-index': self._reset_semantic_index,
            '/status': self._show_rate_limit_status,
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
        with self.console.status("[bold blue]🔧 Initializing OneNote Copilot...", spinner="dots"):
            try:
                await self.agent.initialize()
                self.console.print("[green]✅ OneNote Copilot ready![/green]")
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
        command_parts = command.strip().split(None, 1)  # Split into command and parameters
        command_name = command_parts[0].lower()
        command_args = command_parts[1] if len(command_parts) > 1 else ""

        # Handle commands with arguments
        if command_name == '/content':
            return await self._show_page_content(command_args)
        elif command_name == '/index':
            return await self._index_content(command_args)
        elif command_name == '/semantic':
            return await self._semantic_search(command_args)
        elif command_name in self.commands:
            return await self.commands[command_name]()
        else:
            self.console.print(f"[red]❌ Unknown command: {command_name}[/red]")
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
                # Add debug information
                self.console.print("[dim]DEBUG: Calling agent.list_notebooks()...[/dim]")
                notebooks = await self.agent.list_notebooks()
                self.console.print(f"[dim]DEBUG: Received {len(notebooks)} notebooks[/dim]")

            if notebooks:
                table = self.formatter.format_notebooks(notebooks)
                self.console.print(table)
            else:
                self.console.print("[yellow]📓 No notebooks found.[/yellow]")

            return True

        except Exception as e:
            self.console.print(f"[red]ERROR: Failed to get notebooks: {e}[/red]")
            import traceback
            self.console.print(f"[dim]Traceback: {traceback.format_exc()}[/dim]")
            return True

    async def _show_recent_pages(self) -> bool:
        """Show recently modified pages."""
        try:
            with self.console.status("[bold blue]Getting recent pages...", spinner="dots"):
                # Add debug information
                self.console.print("[dim]DEBUG: Calling agent.get_recent_pages(10)...[/dim]")
                recent_pages = await self.agent.get_recent_pages(10)
                self.console.print(f"[dim]DEBUG: Received {len(recent_pages)} pages[/dim]")

            if recent_pages:
                table = self.formatter.format_recent_pages(recent_pages)
                self.console.print(table)
            else:
                self.console.print("[yellow]📄 No recent pages found.[/yellow]")

            return True

        except Exception as e:
            self.console.print(f"[red]ERROR: Failed to get recent pages: {e}[/red]")
            import traceback
            self.console.print(f"[dim]Traceback: {traceback.format_exc()}[/dim]")
            return True

    @logged
    async def _show_page_content(self, title: str = "") -> bool:
        """
        Show the content of a OneNote page by title.

        Args:
            title: Title of the page to display content for

        Returns:
            True to continue chat loop
        """
        try:
            # Check if title is provided
            if not title.strip():
                self.console.print("[yellow]📝 Usage: /content <page_title>[/yellow]")
                self.console.print("[dim]Example: /content Meeting Notes[/dim]")
                return True

            title = title.strip()

            with self.console.status(f"[bold blue]Getting content for '{title}'...", spinner="dots"):
                # Add debug information
                self.console.print(f"[dim]DEBUG: Searching for page with title: {title}[/dim]")
                page = await self.agent.get_page_content_by_title(title)
                self.console.print(f"[dim]DEBUG: Page found: {page is not None}[/dim]")

            if page:
                # Format and display the page content
                content_panel = self.formatter.format_page_content(page)
                self.console.print(content_panel)
            else:
                self.console.print(f"[yellow]📄 No page found with title: '{title}'[/yellow]")
                self.console.print("[dim]💡 Try using a partial title or check the exact spelling[/dim]")

            return True

        except Exception as e:
            self.console.print(f"[red]ERROR: Failed to get page content: {e}[/red]")
            import traceback
            self.console.print(f"[dim]Traceback: {traceback.format_exc()}[/dim]")
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

    async def _process_user_query(self, query: str) -> None:
        """Process a user query through the agent."""
        try:
            response = await self.agent.process_query(query)
            # Add to history
            self._add_to_history("user", query)
            self._add_to_history("assistant", response)
        except Exception as e:
            self._display_error(f"Failed to process query: {e}")

    async def _handle_streaming_response(self, query: str) -> None:
        """Handle streaming response from agent."""
        try:
            async for chunk in self.agent.process_query(query):
                if chunk.type == "text":
                    self.console.print(chunk.content, end="")
        except Exception as e:
            self._display_error("Streaming error", e)

    def _display_error(self, message: str, exception: Exception = None) -> None:
        """Display error message to user."""
        if exception:
            full_message = f"{message}: {exception}"
        else:
            full_message = message

        error_panel = self.formatter.format_error(full_message)
        self.console.print(error_panel)

    def _add_to_history(self, role: str, content: str) -> None:
        """Add message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now()
        })

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

    def _is_command(self, text: str) -> bool:
        """Check if text is a valid command."""
        if not text.startswith('/'):
            return False

        command = text.split()[0]
        return command in self.commands

    @logged
    async def _index_content(self, args: str = "") -> bool:
        """
        Index OneNote content for semantic search.

        Args:
            args: Optional arguments (e.g., 'recent' for recent pages only)

        Returns:
            True to continue chat loop
        """
        try:
            # Check if semantic search is available
            if not hasattr(self.agent, 'semantic_search_engine') or not self.agent.semantic_search_engine:
                self.console.print("[yellow]📚 Semantic search is not available in this configuration.[/yellow]")
                return True

            # Parse arguments
            index_recent_only = args.strip().lower() == 'recent'

            with self.console.status("[bold blue]Indexing OneNote content...", spinner="dots"):
                if index_recent_only:
                    # Index only recent pages
                    self.console.print("[dim]Getting recent pages for indexing...[/dim]")
                    recent_pages = await self.agent.get_recent_pages(limit=20)

                    if recent_pages:
                        indexer = self.agent.semantic_search_engine.content_chunker.__class__(self.settings)
                        result = await self.agent.semantic_search_engine.index_pages(recent_pages)

                        self.console.print(f"[green]✅ Indexed {result.get('successful', 0)} recent pages[/green]")
                        if result.get('failed', 0) > 0:
                            self.console.print(f"[yellow]⚠️ Failed to index {result['failed']} pages[/yellow]")
                    else:
                        self.console.print("[yellow]📄 No recent pages found to index.[/yellow]")
                else:
                    # Full content indexing
                    self.console.print("[dim]Getting all pages for full indexing...[/dim]")

                    # Get all pages with a reasonable limit to avoid overwhelming the system
                    all_pages = await self.agent.search_tool.get_all_pages(limit=100)

                    if all_pages:
                        self.console.print(f"[dim]Found {len(all_pages)} pages. Starting indexing process...[/dim]")

                        # Update the status message for full indexing (no nested status)
                        self.console.print("[bold green]Indexing all pages (this may take a while)...[/bold green]")
                        result = await self.agent.semantic_search_engine.index_pages(all_pages)

                        successful = result.get('successful', 0)
                        failed = result.get('failed', 0)
                        total_chunks = result.get('total_chunks', 0)

                        self.console.print(f"[green]✅ Full indexing completed![/green]")
                        self.console.print(f"[green]   • Successfully indexed: {successful} pages[/green]")
                        if total_chunks > 0:
                            self.console.print(f"[green]   • Total content chunks: {total_chunks}[/green]")
                        if failed > 0:
                            self.console.print(f"[yellow]   • Failed to index: {failed} pages[/yellow]")

                        self.console.print(f"[dim]Your OneNote content is now ready for semantic search![/dim]")
                    else:
                        self.console.print("[yellow]📄 No pages found to index.[/yellow]")

            return True

        except Exception as e:
            self.console.print(f"[red]❌ Error indexing content: {e}[/red]")
            return True

    @logged
    async def _semantic_search(self, query: str = "") -> bool:
        """
        Perform semantic search on OneNote content.

        Args:
            query: Search query

        Returns:
            True to continue chat loop
        """
        try:
            if not query.strip():
                self.console.print("[yellow]🔍 Usage: /semantic <search_query>[/yellow]")
                self.console.print("[dim]Example: /semantic my thoughts on coding[/dim]")
                return True

            # Check if semantic search is available
            if not hasattr(self.agent, 'semantic_search_engine') or not self.agent.semantic_search_engine:
                self.console.print("[yellow]📚 Semantic search is not available. Try regular search instead.[/yellow]")
                return True

            with self.console.status(f"[bold blue]Searching semantically for '{query}'...", spinner="dots"):
                # Perform semantic search
                search_results = await self.agent.semantic_search_engine.search_with_fallback(query, limit=5)

            if search_results:
                self.console.print(f"[green]🔍 Found {len(search_results)} semantic search results:[/green]\n")

                for i, result in enumerate(search_results, 1):
                    # Format each result
                    score_color = "green" if result.similarity_score > 0.8 else "yellow" if result.similarity_score > 0.6 else "white"

                    self.console.print(f"[bold]{i}. {result.chunk.page_title}[/bold]")
                    self.console.print(f"   [dim]Score: [{score_color}]{result.similarity_score:.3f}[/{score_color}] | Type: {result.search_type}[/dim]")

                    # Show content preview
                    content_preview = result.chunk.content[:200] + "..." if len(result.chunk.content) > 200 else result.chunk.content
                    self.console.print(f"   {content_preview}\n")
            else:
                self.console.print(f"[yellow]🔍 No semantic search results found for '{query}'[/yellow]")
                self.console.print("[dim]💡 Try different keywords or check if content is indexed[/dim]")

            return True

        except Exception as e:
            self.console.print(f"[red]❌ Error performing semantic search: {e}[/red]")
            return True

    async def _show_semantic_stats(self) -> bool:
        """Show semantic search statistics."""
        try:
            # Check if semantic search is available
            if not hasattr(self.agent, 'semantic_search_engine') or not self.agent.semantic_search_engine:
                self.console.print("[yellow]📚 Semantic search is not available.[/yellow]")
                return True

            with self.console.status("[bold blue]Getting semantic search statistics...", spinner="dots"):
                stats = self.agent.semantic_search_engine.get_search_stats()

            # Display stats in a formatted way
            self.console.print("[bold blue]📊 Semantic Search Statistics[/bold blue]\n")

            # Search stats
            self.console.print(f"🔍 Total searches: {stats.get('total_searches', 0)}")
            self.console.print(f"🔀 Hybrid searches: {stats.get('hybrid_searches', 0)}")

            # Embedding stats
            embedding_stats = stats.get('embedding_stats', {})
            self.console.print(f"🤖 API calls: {embedding_stats.get('api_calls', 0)}")
            self.console.print(f"🎯 Cache hit rate: {embedding_stats.get('cache_hit_rate', 0):.1f}%")

            # Settings
            settings = stats.get('settings', {})
            self.console.print(f"⚙️ Semantic threshold: {settings.get('semantic_threshold', 0)}")
            self.console.print(f"⚖️ Hybrid weight: {settings.get('hybrid_weight', 0)}")
            self.console.print(f"📏 Chunk size: {settings.get('chunk_size', 0)}")

            return True

        except Exception as e:
            self.console.print(f"[red]❌ Error getting semantic search stats: {e}[/red]")
            return True

    async def _show_rate_limit_status(self) -> bool:
        """Show current API rate limit status."""
        try:
            # Get rate limit status from search tool
            if not hasattr(self.agent, 'search_tool') or not self.agent.search_tool:
                self.console.print("[yellow]📊 Rate limit information is not available.[/yellow]")
                return True

            status = self.agent.search_tool.get_rate_limit_status()

            # Display status in a formatted way
            self.console.print("[bold blue]📊 API Rate Limit Status[/bold blue]\n")

            # Current usage
            self.console.print(f"📞 API Requests Made: {status['requests_made']}/{status['requests_limit']}")
            self.console.print(f"📈 Usage: {status['percentage_used']:.1f}%")

            # Time window
            self.console.print(f"⏱️ Window Elapsed: {status['window_elapsed_minutes']:.1f} minutes")
            self.console.print(f"⏳ Window Remaining: {status['window_remaining_minutes']:.1f} minutes")

            # Status indicators
            if status['is_approaching_limit']:
                self.console.print("[yellow]⚠️ Approaching rate limit - consider waiting or using more specific searches[/yellow]")
            else:
                self.console.print("[green]✅ Rate limit usage is normal[/green]")

            # Tips
            self.console.print("\n[dim]💡 Tips to reduce API usage:[/dim]")
            self.console.print("[dim]  • Use more specific search terms[/dim]")
            self.console.print("[dim]  • Use /semantic for indexed content searches[/dim]")
            self.console.print("[dim]  • Wait for rate limit window to reset if needed[/dim]")

            return True

        except Exception as e:
            self.console.print(f"[red]❌ Error getting rate limit status: {e}[/red]")
            return True

    async def _reset_semantic_index(self) -> bool:
        """Reset the semantic search index."""
        try:
            # Check if semantic search is available
            if not hasattr(self.agent, 'semantic_search_engine') or not self.agent.semantic_search_engine:
                self.console.print("[yellow]📚 Semantic search is not available.[/yellow]")
                return True

            # Confirm action
            self.console.print("[yellow]⚠️ This will delete all indexed content. Are you sure? (y/N)[/yellow]")
            response = input().strip().lower()

            if response in ['y', 'yes']:
                with self.console.status("[bold red]Resetting semantic search index...", spinner="dots"):
                    await self.agent.semantic_search_engine.reset_index()

                self.console.print("[green]✅ Semantic search index reset successfully[/green]")
            else:
                self.console.print("[dim]Reset cancelled[/dim]")

            return True

        except Exception as e:
            self.console.print(f"[red]❌ Error resetting semantic search index: {e}[/red]")
            return True


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
