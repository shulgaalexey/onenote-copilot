# Great example of a pretty looking chat CLI

```python
"""
Interactive CLI chat interface for Alex Persona AI Chatbot.

Provides a Rich-formatted command-line interface with streaming responses,
session management, and helpful commands.
"""


import asyncio
import sys
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from ..agents.alex_persona.agent import AlexPersonaAgent


class ChatCLI:
    """Interactive chat CLI for Alex Persona agent."""

    def __init__(self, agent: AlexPersonaAgent):
        """
        Initialize the chat CLI.

        Args:
            agent: Configured Alex Persona agent
        """
        self.agent = agent
        self.console = Console()
        self.running = True

        # CLI state
        self.session_started = False

        # Commands mapping
        self.commands = {
            '/help': self._show_help,
            '/reset': self._reset_session,
            '/history': self._show_history,
            '/session': self._show_session_info,
            '/starters': self._show_conversation_starters,
            '/quit': self._quit_chat,
            '/exit': self._quit_chat
        }

    async def start_chat(self) -> None:
        """Start the interactive chat session."""
        await self._initialize_agent()
        self._show_welcome_message()

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
                self.console.print("\n\n[yellow]Chat interrupted. Type '/quit' to exit gracefully.[/yellow]")
                continue
            except EOFError:
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                continue

        self._show_goodbye_message()

    async def _initialize_agent(self) -> None:
        """Initialize the Alex Persona agent."""
        with self.console.status("[bold blue]Initializing Alex Persona AI...", spinner="dots"):
            await self.agent.initialize()

        self.session_started = True

    def _show_welcome_message(self) -> None:
        """Display welcome message and instructions."""
        welcome_text = """
# Alex Persona AI Chatbot

Hello! I'm Alex Shulga, an AI version trained on my conversations and experiences.
I'm here to chat about platform engineering, AI systems, team leadership, and my
experience building developer platforms at Microsoft.

**Commands:**
- Type your questions naturally
- Use `/help` for all available commands
- Use `/starters` to see conversation ideas
- Use `/quit` to exit

Let's chat!
        """

        self.console.print(Panel(
            Markdown(welcome_text),
            title="🤖 Welcome",
            border_style="blue",
            padding=(1, 2)
        ))

    async def _get_user_input(self) -> str:
        """Get user input with rich formatting."""
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
        # Show user message
        timestamp = datetime.now().strftime("%H:%M")
        self.console.print(f"\n[dim]{timestamp}[/dim] [bold cyan]You:[/bold cyan] {message}")

        # Show Alex typing indicator and stream response
        response_text = ""

        with Live(
            Panel(
                Text("🤔 Alex is thinking...", style="italic dim"),
                title="💭 Response",
                border_style="green"
            ),
            console=self.console,
            refresh_per_second=10
        ) as live:

            try:
                async for token in self.agent.stream_response(message):
                    response_text += token

                    # Update live display with accumulated response
                    live.update(Panel(
                        Markdown(response_text),
                        title=f"[bold green]🧠 Alex[/bold green] [dim]{timestamp}[/dim]",
                        border_style="green",
                        padding=(1, 2)
                    ))

            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {e}"
                live.update(Panel(
                    Text(error_msg, style="red"),
                    title="❌ Error",
                    border_style="red"
                ))

        self.console.print()  # Add spacing

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
            self.console.print(f"[red]Unknown command: {command}[/red]")
            self.console.print("Type [cyan]/help[/cyan] for available commands.")
            return True

    async def _show_help(self) -> bool:
        """Show help information."""
        help_text = """
# Available Commands

**Chat Commands:**
- `/help` - Show this help message
- `/reset` - Start a new conversation session
- `/history` - Show recent conversation history
- `/session` - Show current session information
- `/starters` - Show conversation starter suggestions

**System Commands:**
- `/quit` or `/exit` - Exit the chat

**Usage Tips:**
- Ask about platform engineering, AI systems, or team leadership
- Mention specific technologies like RAG, Azure, or Microsoft for targeted responses
- Ask for specific examples or metrics from my experience
- Feel free to ask follow-up questions for deeper insights
        """

        self.console.print(Panel(
            Markdown(help_text),
            title="📖 Help",
            border_style="blue",
            padding=(1, 2)
        ))
        return True

    async def _reset_session(self) -> bool:
        """Reset the conversation session."""
        self.agent.reset_conversation()
        self.console.print("[green]✅ Conversation reset. Starting fresh![/green]")
        return True

    async def _show_history(self) -> bool:
        """Show conversation history."""
        session_info = self.agent.get_session_info()

        if session_info.get("total_messages", 0) == 0:
            self.console.print("[yellow]No conversation history yet.[/yellow]")
            return True

        # Create history table
        table = Table(title="📚 Conversation History")
        table.add_column("Time", style="dim", width=8)
        table.add_column("Role", width=10)
        table.add_column("Message", width=60)

        # Get recent history from memory
        history = self.agent.toolkit.memory_tool.get_conversation_context(limit=10)

        for msg in history[-5:]:  # Show last 5 messages
            role = "🧠 Alex" if msg["role"] == "assistant" else "👤 You"
            content = msg["content"]

            # Truncate long messages
            if len(content) > 80:
                content = content[:77] + "..."

            table.add_row("Recent", role, content)

        self.console.print(table)
        return True

    async def _show_session_info(self) -> bool:
        """Show current session information."""
        session_info = self.agent.get_session_info()

        info_text = f"""
# Session Information

**Session ID:** `{session_info.get('session_id', 'Unknown')}`
**Created:** {session_info.get('created_at', 'Unknown')}
**Duration:** {session_info.get('duration_minutes', 0):.1f} minutes
**Total Messages:** {session_info.get('total_messages', 0)}
**Your Messages:** {session_info.get('user_messages', 0)}
**Alex's Responses:** {session_info.get('assistant_messages', 0)}
        """

        self.console.print(Panel(
            Markdown(info_text),
            title="📊 Session Stats",
            border_style="blue",
            padding=(1, 2)
        ))
        return True

    async def _show_conversation_starters(self) -> bool:
        """Show conversation starter suggestions."""
        starters = self.agent.get_conversation_starters()

        starter_text = "# 💡 Conversation Starters\n\nHere are some topics I'd love to discuss:\n\n"

        for i, starter in enumerate(starters[:8], 1):
            starter_text += f"{i}. {starter}\n"

        starter_text += "\nJust copy and paste one of these, or ask about anything else you're curious about!"

        self.console.print(Panel(
            Markdown(starter_text),
            title="🚀 Ideas",
            border_style="green",
            padding=(1, 2)
        ))
        return True

    async def _quit_chat(self) -> bool:
        """Quit the chat session."""
        self.running = False
        return False

    def _show_goodbye_message(self) -> None:
        """Display goodbye message."""
        goodbye_text = """
# Thanks for chatting!

Your conversation has been saved and you can continue it later by running the chat again.

Feel free to reach out anytime to discuss platform engineering, AI systems, or anything else!

**- Alex** 🤖
        """

        self.console.print(Panel(
            Markdown(goodbye_text),
            title="👋 Goodbye",
            border_style="blue",
            padding=(1, 2)
        ))


async def run_chat_cli() -> None:
    """Run the chat CLI application."""
    try:
        # Create and initialize agent
        agent = AlexPersonaAgent()

        # Create and start CLI
        cli = ChatCLI(agent)
        await cli.start_chat()

    except KeyboardInterrupt:
        print("\nChat interrupted by user.")
    except Exception as e:
        print(f"Error running chat CLI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_chat_cli())
```
