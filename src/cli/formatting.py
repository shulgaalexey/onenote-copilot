"""
Rich-based formatting utilities for OneNote Copilot CLI.

Provides beautiful terminal output formatting, markdown rendering,
and consistent styling throughout the application.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from ..models.onenote import OneNotePage, SearchResult
from ..models.responses import OneNoteCommandResponse, OneNoteSearchResponse


class CLIFormatter:
    """
    Rich-based formatter for OneNote Copilot CLI output.

    Provides consistent, beautiful formatting for all CLI output including
    search results, page content, error messages, and status updates.
    """

    def __init__(self, console: Optional[Console] = None, enable_color: bool = True, enable_markdown: bool = True):
        """
        Initialize the CLI formatter.

        Args:
            console: Optional Rich console instance
            enable_color: Whether to enable colored output
            enable_markdown: Whether to enable markdown rendering
        """
        self.console = console or Console(color_system="auto" if enable_color else None)
        self.enable_color = enable_color
        self.enable_markdown = enable_markdown

        # Color scheme
        self.colors = {
            "primary": "bright_blue",
            "secondary": "cyan",
            "success": "green",
            "warning": "yellow",
            "error": "red",
            "info": "blue",
            "muted": "dim",
            "accent": "magenta"
        }

    def format_welcome_message(self) -> Panel:
        """
        Create a welcome message panel.

        Returns:
            Rich Panel with welcome message
        """
        welcome_text = """
# 🧠 OneNote Copilot

Welcome to your intelligent OneNote assistant! I can help you search and understand your OneNote content using natural language.

**Getting Started:**
- Type your questions naturally (e.g., "What did I write about project planning?")
- Use `/help` to see all available commands
- Use `/starters` to see example queries

**Powered by:** LangGraph • Microsoft Graph API • OpenAI

Let's explore your OneNote content together!
        """

        if self.enable_markdown:
            content = Markdown(welcome_text.strip())
        else:
            content = Text(welcome_text.strip())

        return Panel(
            content,
            title="[bold blue]Welcome[/bold blue]",
            border_style="blue",
            padding=(1, 2)
        )

    def format_search_response(self, response: OneNoteSearchResponse) -> Panel:
        """
        Format a search response for display.

        Args:
            response: OneNote search response to format

        Returns:
            Rich Panel with formatted response
        """
        # Main answer
        if self.enable_markdown:
            answer_content = Markdown(response.answer)
        else:
            answer_content = Text(response.answer)

        # Add confidence indicator
        confidence_text = self._format_confidence(response.confidence)

        # Format sources if available
        sources_content = None
        if response.sources:
            sources_content = self._format_sources(response.sources)

        # Combine content
        if sources_content:
            content_parts = [answer_content, Text("\n"), sources_content]
            if confidence_text:
                content_parts.extend([Text("\n"), confidence_text])
        else:
            content_parts = [answer_content]
            if confidence_text:
                content_parts.extend([Text("\n"), confidence_text])

        # Create renderables list
        renderables = []
        for part in content_parts:
            renderables.append(part)

        return Panel(
            Columns(renderables, equal=False, expand=False),
            title=f"[bold {self.colors['primary']}]🔍 Search Results[/bold {self.colors['primary']}]",
            border_style=self.colors["primary"],
            padding=(1, 2)
        )

    def format_sources(self, pages: List[OneNotePage]) -> Table:
        """
        Format source pages as a table.

        Args:
            pages: List of OneNote pages to format

        Returns:
            Rich Table with source information
        """
        table = Table(
            title="📄 Source Pages",
            show_header=True,
            header_style=f"bold {self.colors['primary']}",
            border_style=self.colors["primary"]
        )

        table.add_column("#", style=self.colors["muted"], width=3)
        table.add_column("Title", style="bold")
        table.add_column("Notebook", style=self.colors["secondary"])
        table.add_column("Section", style=self.colors["info"])
        table.add_column("Modified", style=self.colors["muted"])

        for i, page in enumerate(pages, 1):
            modified_date = page.last_modified_date_time.strftime("%Y-%m-%d")

            table.add_row(
                str(i),
                page.title,
                page.get_notebook_name(),
                page.get_section_name(),
                modified_date
            )

        return table

    def _format_sources(self, pages: List[OneNotePage]) -> Text:
        """Format sources as text with styling."""
        if not pages:
            return Text("No sources found.", style=self.colors["muted"])

        sources_text = Text()
        sources_text.append("📚 Sources:\n", style=f"bold {self.colors['accent']}")

        for i, page in enumerate(pages, 1):
            notebook = page.get_notebook_name()
            section = page.get_section_name()
            date_str = page.last_modified_date_time.strftime("%Y-%m-%d")

            sources_text.append(f"{i}. ", style=self.colors["muted"])
            sources_text.append(f"{page.title}", style="bold")
            sources_text.append(f" ({notebook} > {section})", style=self.colors["secondary"])
            sources_text.append(f" - {date_str}", style=self.colors["muted"])

            if i < len(pages):
                sources_text.append("\n")

        return sources_text

    def _format_confidence(self, confidence: float) -> Optional[Text]:
        """Format confidence score with appropriate styling."""
        if confidence <= 0.0:
            return None

        confidence_text = Text()

        # Choose color based on confidence level
        if confidence >= 0.8:
            color = self.colors["success"]
            icon = "✅"
        elif confidence >= 0.5:
            color = self.colors["warning"]
            icon = "⚠️"
        else:
            color = self.colors["error"]
            icon = "❓"

        confidence_percentage = int(confidence * 100)
        confidence_text.append(f"{icon} Confidence: {confidence_percentage}%", style=f"italic {color}")

        return confidence_text

    def format_command_response(self, response: OneNoteCommandResponse) -> Panel:
        """
        Format a command response for display.

        Args:
            response: Command response to format

        Returns:
            Rich Panel with formatted response
        """
        if response.success:
            if self.enable_markdown:
                content = Markdown(response.message)
            else:
                content = Text(response.message)

            title_style = f"bold {self.colors['success']}"
            border_style = self.colors["success"]
            title = f"✅ {response.command}"
        else:
            error_text = Text()
            error_text.append(response.message, style=self.colors["error"])

            if response.error:
                error_text.append(f"\n\nError: {response.error}", style=f"italic {self.colors['muted']}")

            content = error_text
            title_style = f"bold {self.colors['error']}"
            border_style = self.colors["error"]
            title = f"❌ {response.command}"

        return Panel(
            content,
            title=f"[{title_style}]{title}[/{title_style}]",
            border_style=border_style,
            padding=(1, 2)
        )

    def format_recent_pages(self, pages: List[OneNotePage]) -> Table:
        """
        Format recent pages as a table.

        Args:
            pages: List of recent OneNote pages

        Returns:
            Rich Table with recent pages
        """
        table = Table(
            title="🕒 Recent Pages",
            show_header=True,
            header_style=f"bold {self.colors['primary']}",
            border_style=self.colors["primary"]
        )

        table.add_column("Title", style="bold")
        table.add_column("Notebook", style=self.colors["secondary"])
        table.add_column("Section", style=self.colors["info"])
        table.add_column("Modified", style=self.colors["muted"])
        table.add_column("Preview", style=self.colors["muted"], max_width=40)

        for page in pages:
            modified_date = page.last_modified_date_time.strftime("%Y-%m-%d %H:%M")
            preview = page.short_content[:50] + "..." if len(page.short_content) > 50 else page.short_content

            table.add_row(
                page.title,
                page.get_notebook_name(),
                page.get_section_name(),
                modified_date,
                preview
            )

        return table

    def format_notebooks(self, notebooks: List[Dict[str, Any]]) -> Table:
        """
        Format notebooks list as a table.

        Args:
            notebooks: List of notebook data

        Returns:
            Rich Table with notebooks
        """
        table = Table(
            title="📓 Your Notebooks",
            show_header=True,
            header_style=f"bold {self.colors['primary']}",
            border_style=self.colors["primary"]
        )

        table.add_column("Name", style="bold")
        table.add_column("Created", style=self.colors["muted"])
        table.add_column("Modified", style=self.colors["muted"])
        table.add_column("Default", style=self.colors["accent"], justify="center")

        for notebook in notebooks:
            name = notebook.get("displayName", "Unnamed Notebook")
            created = notebook.get("createdDateTime", "")
            modified = notebook.get("lastModifiedDateTime", "")
            is_default = notebook.get("isDefault", False)

            # Format dates
            if created:
                created = created[:10]  # YYYY-MM-DD
            if modified:
                modified = modified[:10]  # YYYY-MM-DD

            default_indicator = "⭐" if is_default else ""

            table.add_row(name, created, modified, default_indicator)

        return table

    def format_error(self, error: str, title: str = "Error") -> Panel:
        """
        Format an error message.

        Args:
            error: Error message
            title: Error title

        Returns:
            Rich Panel with error message
        """
        error_text = Text(error, style=self.colors["error"])

        return Panel(
            error_text,
            title=f"[bold {self.colors['error']}]❌ {title}[/bold {self.colors['error']}]",
            border_style=self.colors["error"],
            padding=(1, 2)
        )

    def format_status(self, message: str, spinner: bool = False) -> Text:
        """
        Format a status message.

        Args:
            message: Status message
            spinner: Whether to show a spinner

        Returns:
            Rich Text with status message
        """
        status_text = Text()

        if spinner:
            status_text.append("⏳ ", style=self.colors["info"])
        else:
            status_text.append("ℹ️ ", style=self.colors["info"])

        status_text.append(message, style=self.colors["info"])

        return status_text

    def format_help(self) -> Panel:
        """
        Format help information.

        Returns:
            Rich Panel with help content
        """
        help_text = """
# OneNote Copilot Commands

## Natural Language Queries
Just type your questions naturally! Examples:
- "What did I write about project planning?"
- "Show me my Python development notes"
- "Find notes from the marketing meeting"

## Utility Commands
- **`/help`** - Show this help message
- **`/notebooks`** - List all your OneNote notebooks
- **`/recent`** - Show recently modified pages
- **`/starters`** - Show example conversation starters
- **`/clear`** - Clear conversation history
- **`/quit`** or **`/exit`** - Exit the application

## Tips
- Be specific in your queries for better results
- I search across all your notebooks and sections
- Source information shows exactly where I found answers
- Try different keywords if you don't find what you're looking for

## Examples
```
What are my thoughts on machine learning?
Show me notes from last week's standup
Find pages about the quarterly review
Search for Python best practices
```
        """

        if self.enable_markdown:
            content = Markdown(help_text.strip())
        else:
            content = Text(help_text.strip())

        return Panel(
            content,
            title=f"[bold {self.colors['info']}]📖 Help[/bold {self.colors['info']}]",
            border_style=self.colors["info"],
            padding=(1, 2)
        )

    def format_conversation_starters(self, starters: List[str]) -> Panel:
        """
        Format conversation starters.

        Args:
            starters: List of conversation starter examples

        Returns:
            Rich Panel with conversation starters
        """
        starters_text = Text()
        starters_text.append("💡 Try these example queries:\n\n", style=f"bold {self.colors['accent']}")

        for i, starter in enumerate(starters[:8], 1):  # Show first 8
            starters_text.append(f"{i}. ", style=self.colors["muted"])
            starters_text.append(f'"{starter}"', style=self.colors["secondary"])

            if i < min(8, len(starters)):
                starters_text.append("\n")

        return Panel(
            starters_text,
            title=f"[bold {self.colors['accent']}]💬 Conversation Starters[/bold {self.colors['accent']}]",
            border_style=self.colors["accent"],
            padding=(1, 2)
        )

    def create_loading_panel(self, message: str = "Processing...") -> Panel:
        """
        Create a loading panel for Live display.

        Args:
            message: Loading message

        Returns:
            Rich Panel for loading display
        """
        loading_text = Text()
        loading_text.append("🤔 ", style=self.colors["info"])
        loading_text.append(message, style=f"italic {self.colors['info']}")

        return Panel(
            loading_text,
            title=f"[bold {self.colors['info']}]💭 Thinking[/bold {self.colors['info']}]",
            border_style=self.colors["info"],
            padding=(1, 2)
        )

    def format_partial_response(self, content_parts: List[str]) -> Panel:
        """
        Format a partial streaming response.

        Args:
            content_parts: List of response content parts

        Returns:
            Rich Panel with partial response
        """
        content = "".join(content_parts)

        if self.enable_markdown:
            formatted_content = Markdown(content)
        else:
            formatted_content = Text(content)

        return Panel(
            formatted_content,
            title=f"[bold {self.colors['primary']}]🧠 OneNote Copilot[/bold {self.colors['primary']}]",
            border_style=self.colors["primary"],
            padding=(1, 2)
        )


def create_progress_spinner(description: str = "Working...") -> Progress:
    """
    Create a Rich progress spinner.

    Args:
        description: Description text for the spinner

    Returns:
        Rich Progress instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    )
