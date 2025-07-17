"""
Integration test for the /content command functionality.

Tests the complete flow from CLI command to content display
to ensure all components work together correctly.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cli.interface import OneNoteCLI
from src.models.onenote import OneNotePage


class TestContentCommandIntegration:
    """Integration tests for the /content command functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = MagicMock()
        settings.openai_api_key = "test-api-key"
        settings.openai_model = "gpt-4o-mini"
        settings.openai_temperature = 0.7
        settings.cli_color_enabled = True
        settings.cli_markdown_enabled = True
        settings.cli_welcome_enabled = True
        return settings

    @pytest.fixture
    def sample_page(self):
        """Create a sample OneNote page for testing."""
        return OneNotePage(
            id="test-page-123",
            title="Python Development Guidelines",
            created_date_time=datetime(2025, 7, 15, 10, 30),
            last_modified_date_time=datetime(2025, 7, 16, 14, 45),
            text_content="This page contains Python development best practices.\n\n1. Use type hints\n2. Write comprehensive tests\n3. Follow PEP 8 style guide\n4. Use virtual environments",
            content="<html><body>Python content</body></html>",
            parent_notebook={"displayName": "Development Notes"},
            parent_section={"displayName": "Programming Languages"}
        )

    @pytest.mark.asyncio
    async def test_content_command_end_to_end_success(self, mock_settings, sample_page):
        """Test complete /content command flow successfully finding and displaying a page."""

        # Mock the CLI with minimal initialization
        with patch('src.cli.interface.OneNoteAgent'):
            cli = OneNoteCLI(mock_settings)

            # Mock console and formatter
            cli.console = MagicMock()
            cli.formatter = MagicMock()
            cli.formatter.format_page_content.return_value = "Formatted page content"

            # Mock agent to return our sample page
            cli.agent = AsyncMock()
            cli.agent.get_page_content_by_title.return_value = sample_page

            # Test the command parsing and execution
            result = await cli._handle_command("/content Python Development")

            # Verify the command was handled correctly
            assert result is True
            cli.agent.get_page_content_by_title.assert_called_once_with("Python Development")
            cli.formatter.format_page_content.assert_called_once_with(sample_page)
            cli.console.print.assert_called()

    @pytest.mark.asyncio
    async def test_content_command_end_to_end_not_found(self, mock_settings):
        """Test complete /content command flow when page is not found."""

        # Mock the CLI with minimal initialization
        with patch('src.cli.interface.OneNoteAgent'):
            cli = OneNoteCLI(mock_settings)

            # Mock console
            cli.console = MagicMock()

            # Mock agent to return None (page not found)
            cli.agent = AsyncMock()
            cli.agent.get_page_content_by_title.return_value = None

            # Test the command parsing and execution
            result = await cli._handle_command("/content Nonexistent Page")

            # Verify the command was handled correctly
            assert result is True
            cli.agent.get_page_content_by_title.assert_called_once_with("Nonexistent Page")
            cli.console.print.assert_called()  # Should show "not found" message

    @pytest.mark.asyncio
    async def test_content_command_no_title_provided(self, mock_settings):
        """Test /content command when no title is provided."""

        # Mock the CLI with minimal initialization
        with patch('src.cli.interface.OneNoteAgent'):
            cli = OneNoteCLI(mock_settings)

            # Mock console
            cli.console = MagicMock()

            # Test the command parsing and execution
            result = await cli._handle_command("/content")

            # Verify the command was handled correctly
            assert result is True
            cli.console.print.assert_called()  # Should show usage message

    @pytest.mark.asyncio
    async def test_content_command_with_extra_spaces(self, mock_settings, sample_page):
        """Test /content command with extra spaces in title."""

        # Mock the CLI with minimal initialization
        with patch('src.cli.interface.OneNoteAgent'):
            cli = OneNoteCLI(mock_settings)

            # Mock console and formatter
            cli.console = MagicMock()
            cli.formatter = MagicMock()
            cli.formatter.format_page_content.return_value = "Formatted content"

            # Mock agent to return our sample page
            cli.agent = AsyncMock()
            cli.agent.get_page_content_by_title.return_value = sample_page

            # Test the command with extra spaces
            result = await cli._handle_command("/content   Python   Development   ")

            # Verify the command was handled correctly and spaces were stripped
            assert result is True
            cli.agent.get_page_content_by_title.assert_called_once_with("Python   Development")

    @pytest.mark.asyncio
    async def test_content_command_case_insensitive(self, mock_settings, sample_page):
        """Test that /content command parsing is case insensitive."""

        # Mock the CLI with minimal initialization
        with patch('src.cli.interface.OneNoteAgent'):
            cli = OneNoteCLI(mock_settings)

            # Mock console and formatter
            cli.console = MagicMock()
            cli.formatter = MagicMock()
            cli.formatter.format_page_content.return_value = "Formatted content"

            # Mock agent to return our sample page
            cli.agent = AsyncMock()
            cli.agent.get_page_content_by_title.return_value = sample_page

            # Test the command with different cases
            result = await cli._handle_command("/CONTENT Python Development")

            # Verify the command was handled correctly
            assert result is True
            cli.agent.get_page_content_by_title.assert_called_once_with("Python Development")

    def test_command_parsing_logic(self):
        """Test the command parsing logic for various inputs."""

        # Test cases for command parsing
        test_cases = [
            ("/content Meeting Notes", "/content", "Meeting Notes"),
            ("/content", "/content", ""),
            ("/Content Python Development", "/content", "Python Development"),
            ("/CONTENT   Test   Page   ", "/content", "Test   Page"),
        ]

        for command_input, expected_command, expected_args in test_cases:
            command_parts = command_input.strip().split(None, 1)
            command_name = command_parts[0].lower()
            command_args = command_parts[1] if len(command_parts) > 1 else ""

            assert command_name == expected_command
            assert command_args.strip() == expected_args.strip()

    @pytest.mark.asyncio
    async def test_content_command_error_handling(self, mock_settings):
        """Test /content command error handling."""

        # Mock the CLI with minimal initialization
        with patch('src.cli.interface.OneNoteAgent'):
            cli = OneNoteCLI(mock_settings)

            # Mock console
            cli.console = MagicMock()

            # Mock agent to raise an exception
            cli.agent = AsyncMock()
            cli.agent.get_page_content_by_title.side_effect = Exception("API Error")

            # Test the command parsing and execution
            result = await cli._handle_command("/content Test Page")

            # Verify the command was handled correctly and error was caught
            assert result is True
            cli.agent.get_page_content_by_title.assert_called_once_with("Test Page")
            cli.console.print.assert_called()  # Should show error message


if __name__ == "__main__":
    pytest.main([__file__])
