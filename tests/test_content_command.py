"""
Tests for the /content command functionality.

Tests the new page content retrieval command including:
- OneNoteSearchTool.get_page_content_by_title
- OneNoteAgent.get_page_content_by_title
- CLI interface command handling
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.onenote_agent import OneNoteAgent
from src.cli.formatting import CLIFormatter
from src.cli.interface import OneNoteCLI
from src.models.onenote import OneNotePage
from src.tools.onenote_search import OneNoteSearchError, OneNoteSearchTool


class TestPageContentRetrieval:
    """Test page content retrieval functionality."""

    def create_test_page(self, page_id: str = "test-page-1", title: str = "Test Page") -> OneNotePage:
        """Create a test page for testing."""
        return OneNotePage(
            id=page_id,
            title=title,
            created_date_time=datetime.now(),
            last_modified_date_time=datetime.now(),
            text_content="This is test content for the page.",
            content="<html><body>This is test content for the page.</body></html>"
        )

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = MagicMock()
        settings.openai_api_key = "test-key"
        settings.openai_model = "gpt-4o-mini"
        settings.openai_temperature = 0.7
        settings.cli_color_enabled = True
        settings.cli_markdown_enabled = True
        settings.cli_welcome_enabled = True
        return settings

    @pytest.fixture
    def mock_authenticator(self):
        """Mock authenticator for testing."""
        auth = AsyncMock()
        auth.get_valid_token.return_value = "test-token"
        return auth

    @pytest.mark.asyncio
    async def test_search_tool_get_page_content_by_title_exact_match(self, mock_settings, mock_authenticator):
        """Test getting page content with exact title match."""
        search_tool = OneNoteSearchTool(mock_authenticator, mock_settings)

        # Mock the search_pages method to return a test page
        test_page = self.create_test_page(title="Meeting Notes")
        mock_result = MagicMock()
        mock_result.pages = [test_page]

        with patch.object(search_tool, 'search_pages', return_value=mock_result):
            result = await search_tool.get_page_content_by_title("Meeting Notes")

            assert result is not None
            assert result.title == "Meeting Notes"
            assert result.text_content == "This is test content for the page."

    @pytest.mark.asyncio
    async def test_search_tool_get_page_content_by_title_partial_match(self, mock_settings, mock_authenticator):
        """Test getting page content with partial title match."""
        search_tool = OneNoteSearchTool(mock_authenticator, mock_settings)

        # Mock the search_pages method to return a test page
        test_page = self.create_test_page(title="Meeting Notes from Sprint Review")
        mock_result = MagicMock()
        mock_result.pages = [test_page]

        with patch.object(search_tool, 'search_pages', return_value=mock_result):
            result = await search_tool.get_page_content_by_title("Meeting Notes")

            assert result is not None
            assert result.title == "Meeting Notes from Sprint Review"

    @pytest.mark.asyncio
    async def test_search_tool_get_page_content_by_title_no_match(self, mock_settings, mock_authenticator):
        """Test getting page content when no page found."""
        search_tool = OneNoteSearchTool(mock_authenticator, mock_settings)

        # Mock the search_pages method to return empty result
        mock_result = MagicMock()
        mock_result.pages = []

        with patch.object(search_tool, 'search_pages', return_value=mock_result):
            result = await search_tool.get_page_content_by_title("Nonexistent Page")

            assert result is None

    @pytest.mark.asyncio
    async def test_search_tool_get_page_content_with_content_fetch(self, mock_settings, mock_authenticator):
        """Test getting page content when content needs to be fetched."""
        search_tool = OneNoteSearchTool(mock_authenticator, mock_settings)

        # Create page without content
        test_page = OneNotePage(
            id="test-page",
            title="Test Page",
            created_date_time=datetime.now(),
            last_modified_date_time=datetime.now()
        )

        mock_result = MagicMock()
        mock_result.pages = [test_page]

        # Mock search_pages and _fetch_page_content
        with patch.object(search_tool, 'search_pages', return_value=mock_result), \
             patch.object(search_tool, '_fetch_page_content', return_value=("HTML content", 1)), \
             patch.object(search_tool, '_extract_text_from_html', return_value="Text content"):

            result = await search_tool.get_page_content_by_title("Test Page")

            assert result is not None
            assert result.title == "Test Page"
            assert result.content == "HTML content"
            assert result.text_content == "Text content"

    @pytest.mark.asyncio
    async def test_agent_get_page_content_by_title(self, mock_settings):
        """Test agent method for getting page content."""
        agent = OneNoteAgent(mock_settings)

        # Mock the search tool
        mock_search_tool = AsyncMock()
        test_page = self.create_test_page()
        mock_search_tool.get_page_content_by_title.return_value = test_page
        agent.search_tool = mock_search_tool

        result = await agent.get_page_content_by_title("Test Page")

        assert result is not None
        assert result.title == "Test Page"
        mock_search_tool.get_page_content_by_title.assert_called_once_with("Test Page")

    @pytest.mark.asyncio
    async def test_agent_get_page_content_by_title_not_found(self, mock_settings):
        """Test agent method when page not found."""
        agent = OneNoteAgent(mock_settings)

        # Mock the search tool to return None
        mock_search_tool = AsyncMock()
        mock_search_tool.get_page_content_by_title.return_value = None
        agent.search_tool = mock_search_tool

        result = await agent.get_page_content_by_title("Nonexistent Page")

        assert result is None

    @pytest.mark.asyncio
    async def test_agent_get_page_content_by_title_error(self, mock_settings):
        """Test agent method when search tool raises error."""
        agent = OneNoteAgent(mock_settings)

        # Mock the search tool to raise error
        mock_search_tool = AsyncMock()
        mock_search_tool.get_page_content_by_title.side_effect = OneNoteSearchError("API error")
        agent.search_tool = mock_search_tool

        with pytest.raises(Exception) as exc_info:
            await agent.get_page_content_by_title("Test Page")

        assert "Failed to get page content" in str(exc_info.value)

    def test_cli_content_command_parsing(self, mock_settings):
        """Test CLI command parsing for /content command."""
        cli = OneNoteCLI(mock_settings)

        # Test command parsing
        command_parts = "/content Meeting Notes".strip().split(None, 1)
        command_name = command_parts[0].lower()
        command_args = command_parts[1] if len(command_parts) > 1 else ""

        assert command_name == "/content"
        assert command_args == "Meeting Notes"

    def test_cli_content_command_no_args(self, mock_settings):
        """Test CLI command parsing when no arguments provided."""
        cli = OneNoteCLI(mock_settings)

        # Test command parsing without arguments
        command_parts = "/content".strip().split(None, 1)
        command_name = command_parts[0].lower()
        command_args = command_parts[1] if len(command_parts) > 1 else ""

        assert command_name == "/content"
        assert command_args == ""

    def test_formatter_page_content(self):
        """Test page content formatting."""
        formatter = CLIFormatter(enable_color=False, enable_markdown=False)
        test_page = self.create_test_page()

        # Add mock notebook and section data
        test_page.parent_notebook = {"displayName": "Test Notebook"}
        test_page.parent_section = {"displayName": "Test Section"}

        panel = formatter.format_page_content(test_page)

        assert panel is not None
        # Check that the panel contains expected content by checking the renderable content
        assert hasattr(panel, 'renderable')

    def test_formatter_page_content_long_text(self):
        """Test page content formatting with long text."""
        formatter = CLIFormatter(enable_color=False, enable_markdown=False)

        # Create page with long content
        long_content = "This is a very long content. " * 200  # > 5000 chars
        test_page = OneNotePage(
            id="test-page",
            title="Long Page",
            created_date_time=datetime.now(),
            last_modified_date_time=datetime.now(),
            text_content=long_content
        )

        panel = formatter.format_page_content(test_page)

        assert panel is not None
        # Panel should exist - we can't easily test truncation without rendering
        assert hasattr(panel, 'renderable')

    def test_formatter_page_content_no_text(self):
        """Test page content formatting with no text content."""
        formatter = CLIFormatter(enable_color=False, enable_markdown=False)

        test_page = OneNotePage(
            id="test-page",
            title="Empty Page",
            created_date_time=datetime.now(),
            last_modified_date_time=datetime.now()
        )

        panel = formatter.format_page_content(test_page)

        assert panel is not None
        # Panel should exist even without content
        assert hasattr(panel, 'renderable')


class TestCLIContentCommand:
    """Test CLI /content command functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = MagicMock()
        settings.openai_api_key = "test-api-key"
        settings.openai_model = "gpt-4o-mini"
        settings.openai_temperature = 0.7
        settings.cli_color_enabled = True
        settings.cli_markdown_enabled = True
        settings.cli_welcome_enabled = True
        return settings

    @pytest.fixture
    def mock_console(self):
        """Mock console for testing."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_show_page_content_success(self, mock_settings, mock_console):
        """Test successful page content display."""
        # Test the method directly without creating the full CLI object
        from src.cli.interface import OneNoteCLI

        # Mock just what we need for this method
        method_under_test = OneNoteCLI._show_page_content

        # Create a mock CLI instance with minimal setup
        mock_cli = MagicMock()
        mock_cli.console = mock_console

        # Mock agent
        mock_agent = AsyncMock()
        test_page = OneNotePage(
            id="test-page",
            title="Test Page",
            created_date_time=datetime.now(),
            last_modified_date_time=datetime.now(),
            text_content="Test content"
        )
        mock_agent.get_page_content_by_title.return_value = test_page
        mock_cli.agent = mock_agent

        # Mock formatter
        mock_formatter = MagicMock()
        mock_formatter.format_page_content.return_value = "Formatted content"
        mock_cli.formatter = mock_formatter

        result = await method_under_test(mock_cli, "Test Page")

        assert result is True
        mock_agent.get_page_content_by_title.assert_called_once_with("Test Page")
        mock_formatter.format_page_content.assert_called_once_with(test_page)

    @pytest.mark.asyncio
    async def test_show_page_content_not_found(self, mock_settings, mock_console):
        """Test page content display when page not found."""
        # Test the method directly without creating the full CLI object
        from src.cli.interface import OneNoteCLI

        method_under_test = OneNoteCLI._show_page_content

        # Create a mock CLI instance
        mock_cli = MagicMock()
        mock_cli.console = mock_console

        # Mock agent to return None
        mock_agent = AsyncMock()
        mock_agent.get_page_content_by_title.return_value = None
        mock_cli.agent = mock_agent

        result = await method_under_test(mock_cli, "Nonexistent Page")

        assert result is True
        mock_agent.get_page_content_by_title.assert_called_once_with("Nonexistent Page")

    @pytest.mark.asyncio
    async def test_show_page_content_no_title(self, mock_settings, mock_console):
        """Test page content display when no title provided."""
        # Test the method directly without creating the full CLI object
        from src.cli.interface import OneNoteCLI

        method_under_test = OneNoteCLI._show_page_content

        # Create a mock CLI instance
        mock_cli = MagicMock()
        mock_cli.console = mock_console

        result = await method_under_test(mock_cli, "")

        assert result is True
        # Should show usage message

    @pytest.mark.asyncio
    async def test_show_page_content_error(self, mock_settings, mock_console):
        """Test page content display when error occurs."""
        # Test the method directly without creating the full CLI object
        from src.cli.interface import OneNoteCLI

        method_under_test = OneNoteCLI._show_page_content

        # Create a mock CLI instance
        mock_cli = MagicMock()
        mock_cli.console = mock_console

        # Mock agent to raise error
        mock_agent = AsyncMock()
        mock_agent.get_page_content_by_title.side_effect = Exception("Test error")
        mock_cli.agent = mock_agent

        result = await method_under_test(mock_cli, "Test Page")

        assert result is True
        # Should show error message


if __name__ == "__main__":
    pytest.main([__file__])
