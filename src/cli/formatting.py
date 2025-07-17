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


def create_progress_spinner(description: str = "Processing...") -> Progress:
    """Create a progress spinner for long-running operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    )


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
- **`/content <title>`** - Display full content of a page by title
- **`/starters`** - Show example conversation starters
- **`/clear`** - Clear conversation history
- **`/quit`** or **`/exit`** - Exit the application

## Semantic Search Commands
- **`/index`** - Index all OneNote content for semantic search (full indexing)
- **`/index recent`** - Index only recent OneNote pages for semantic search
- **`/semantic <query>`** - Perform semantic search on indexed content
- **`/stats`** - Show semantic search statistics and configuration
- **`/reset-index`** - Reset the semantic search index (warning: deletes all indexed data)

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

    def format_page_details(self, page: OneNotePage) -> Panel:
        """
        Format detailed information about a single page.

        Args:
            page: OneNote page to format

        Returns:
            Rich Panel with page details
        """
        details = f"""**Title:** {page.title}
**Created:** {page.created_date_time.strftime('%Y-%m-%d %H:%M')}
**Modified:** {page.last_modified_date_time.strftime('%Y-%m-%d %H:%M')}
**Content Preview:** {page.short_content[:200]}..."""

        if self.enable_markdown:
            content = Markdown(details)
        else:
            content = Text(details)

        return Panel(
            content,
            title="[bold blue]Page Details[/bold blue]",
            border_style="blue",
            padding=(1, 2)
        )

    def format_page_content(self, page: OneNotePage) -> Panel:
        """
        Format the full content of a OneNote page.

        Args:
            page: OneNote page to format

        Returns:
            Rich Panel with full page content
        """
        # Create header with metadata
        header = f"""**📄 {page.title}**

**📅 Created:** {page.created_date_time.strftime('%Y-%m-%d %H:%M')}
**📝 Modified:** {page.last_modified_date_time.strftime('%Y-%m-%d %H:%M')}
**📚 Notebook:** {page.get_notebook_name()}
**📁 Section:** {page.get_section_name()}

---

"""

        # Add content
        if page.text_content:
            content_text = page.text_content.strip()
            # Limit content length for display
            if len(content_text) > 5000:
                content_text = content_text[:5000] + "\n\n... [Content truncated - showing first 5000 characters] ..."
        else:
            content_text = "*No content available*"

        full_content = header + content_text

        if self.enable_markdown:
            content = Markdown(full_content)
        else:
            content = Text(full_content)

        return Panel(
            content,
            title=f"[bold green]📄 Page Content[/bold green]",
            border_style="green",
            padding=(1, 2)
        )

    def format_warning(self, warning: str, title: str = "Warning") -> Panel:
        """
        Format a warning message.

        Args:
            warning: Warning message text
            title: Warning title

        Returns:
            Rich Panel with warning message
        """
        return Panel(
            Text(warning),
            title=f"[bold {self.colors['warning']}]{title}[/bold {self.colors['warning']}]",
            border_style=self.colors["warning"],
            padding=(1, 2)
        )

    def format_info(self, info: str, title: str = "Info") -> Panel:
        """
        Format an info message.

        Args:
            info: Info message text
            title: Info title

        Returns:
            Rich Panel with info message
        """
        return Panel(
            Text(info),
            title=f"[bold {self.colors['info']}]{title}[/bold {self.colors['info']}]",
            border_style=self.colors["info"],
            padding=(1, 2)
        )

    def create_progress(self, description: str = "Processing...") -> Progress:
        """
        Create a Rich progress instance.

        Args:
            description: Description for the progress indicator

        Returns:
            Rich Progress instance
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        )

    def format_pages_table(self, pages: List[OneNotePage]) -> Table:
        """
        Format a list of pages as a table.

        Args:
            pages: List of OneNote pages

        Returns:
            Rich Table with page information
        """
        table = Table(
            title="OneNote Pages",
            show_header=True,
            header_style="bold blue"
        )

        table.add_column("Title", style="cyan", no_wrap=False)
        table.add_column("Modified", style="yellow", width=20)
        table.add_column("Notebook", style="green", width=15)

        for page in pages[:10]:  # Limit to 10 pages
            notebook_name = page.get_notebook_name() or "Unknown"
            modified = page.last_modified_date_time.strftime('%Y-%m-%d %H:%M')
            table.add_row(page.title, modified, notebook_name)

        return table

    def format_notebooks_list(self, notebooks: List[Dict[str, Any]]) -> Table:
        """
        Format a list of notebooks as a table.

        Args:
            notebooks: List of notebook data

        Returns:
            Rich Table with notebook information
        """
        table = Table(
            title="OneNote Notebooks",
            show_header=True,
            header_style="bold blue"
        )

        table.add_column("Name", style="cyan", no_wrap=False)
        table.add_column("Sections", style="yellow", width=10)
        table.add_column("Created", style="green", width=20)

        for notebook in notebooks[:10]:  # Limit to 10 notebooks
            name = notebook.get('displayName', 'Unknown')
            sections = str(len(notebook.get('sections', [])))
            created = notebook.get('createdDateTime', 'Unknown')
            if created != 'Unknown':
                try:
                    created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    created = created_dt.strftime('%Y-%m-%d')
                except:
                    created = 'Unknown'
            table.add_row(name, sections, created)

        return table

    def format_streaming_chunk(self, chunk_text: str) -> Text:
        """
        Format a streaming text chunk.

        Args:
            chunk_text: Text chunk to format

        Returns:
            Rich Text instance
        """
        return Text(chunk_text, style=self.colors["primary"])

    def format_typing_indicator(self, message: str = "Thinking...") -> Text:
        """
        Format a typing indicator.

        Args:
            message: Typing indicator message

        Returns:
            Rich Text instance with animated dots
        """
        return Text(f"🤔 {message}", style=self.colors["muted"])

    def truncate_text(self, text: str, max_length: int = 100) -> str:
        """
        Truncate text to specified length.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."

    def format_datetime(self, dt: datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
        """
        Format a datetime object.

        Args:
            dt: Datetime to format
            format_str: Format string

        Returns:
            Formatted datetime string
        """
        return dt.strftime(format_str)
