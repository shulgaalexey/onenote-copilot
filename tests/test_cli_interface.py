"""
Tests for OneNote CLI interface.

Comprehensive unit tests for the CLI interface including command handling,
conversation flow, and error handling.
"""

import asyncio
from io import StringIO
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.agents.onenote_agent import OneNoteAgent
from src.auth.microsoft_auth import AuthenticationError
from src.cli.interface import OneNoteCLI
from src.models.responses import StreamingChunk


class TestOneNoteCLI:
    """Test OneNote CLI interface."""

    @pytest.fixture(autouse=True)
    def mock_agent(self):
        """Mock OneNoteAgent for all tests."""
        with patch('src.cli.interface.OneNoteAgent') as mock_agent_class:
            mock_agent = AsyncMock()
            mock_agent.initialize = AsyncMock(return_value=None)
            mock_agent.process_query = AsyncMock(return_value="Mock response")
            mock_agent.list_notebooks = AsyncMock(return_value=[])
            mock_agent.get_recent_pages = AsyncMock(return_value=[])
            # This should be a regular Mock since it's synchronous
            mock_agent.get_conversation_starters = Mock(return_value=[
                "Search for meeting notes",
                "Find project documentation",
                "What are my recent ideas?"
            ])
            mock_agent_class.return_value = mock_agent
            self.mock_agent = mock_agent
            yield mock_agent

    def test_cli_initialization(self):
        """Test CLI initialization with defaults."""
        cli = OneNoteCLI()

        assert cli.console is not None
        assert cli.formatter is not None
        assert cli.agent is not None
        assert cli.running is True
        assert cli.conversation_history == []
        assert len(cli.commands) > 0

    def test_cli_initialization_with_custom_settings(self):
        """Test CLI initialization with custom settings."""
        mock_settings = Mock()
        mock_settings.cli_color_enabled = True
        mock_settings.cli_markdown_enabled = True
        mock_settings.cli_welcome_enabled = True

        cli = OneNoteCLI(settings=mock_settings)

        assert cli.settings is mock_settings
        assert cli.console is not None
        assert cli.formatter is not None

    def test_cli_commands_mapping(self):
        """Test that all expected commands are mapped."""
        cli = OneNoteCLI()

        expected_commands = [
            '/help', '/notebooks', '/recent', '/starters',
            '/clear', '/quit', '/exit'
        ]

        for command in expected_commands:
            assert command in cli.commands
            assert callable(cli.commands[command])

    @pytest.mark.asyncio
    async def test_initialize_agent_success(self):
        """Test successful agent initialization."""
        cli = OneNoteCLI()

        with patch.object(cli.agent, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True

            await cli._initialize_agent()

            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_agent_authentication_error(self):
        """Test agent initialization with authentication error."""
        cli = OneNoteCLI()

        with patch.object(cli.agent, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = AuthenticationError("Authentication failed")

            with pytest.raises(AuthenticationError):
                await cli._initialize_agent()

    def test_show_welcome_message(self):
        """Test welcome message display."""
        with patch('rich.console.Console.print') as mock_print:
            cli = OneNoteCLI()
            cli._show_welcome()

            # Verify that print was called with welcome content
            mock_print.assert_called()
            call_args = mock_print.call_args_list
            assert len(call_args) > 0

    @pytest.mark.asyncio
    async def test_show_help_command(self):
        """Test /help command."""
        with patch('rich.console.Console.print') as mock_print:
            cli = OneNoteCLI()
            await cli._show_help()

            mock_print.assert_called()
            # Help command should display help content
            assert mock_print.call_count >= 1

    @pytest.mark.asyncio
    async def test_list_notebooks_command(self):
        """Test /notebooks command."""
        mock_notebooks = [
            {"displayName": "Work", "id": "1-notebook1"},
            {"displayName": "Personal", "id": "1-notebook2"}
        ]

        cli = OneNoteCLI()

        with patch.object(cli.agent, 'list_notebooks', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_notebooks

            with patch('rich.console.Console.print') as mock_print:
                await cli._list_notebooks()

                mock_list.assert_called_once()
                mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_show_recent_pages_command(self):
        """Test /recent command."""
        from src.models.onenote import OneNotePage

        mock_pages = [
            OneNotePage(
                id="1-page1",
                title="Recent Page 1",
                createdDateTime="2025-01-01T10:00:00Z",
                lastModifiedDateTime="2025-01-02T15:30:00Z"
            ),
            OneNotePage(
                id="1-page2",
                title="Recent Page 2",
                createdDateTime="2025-01-01T10:00:00Z",
                lastModifiedDateTime="2025-01-03T15:30:00Z"
            )
        ]

        cli = OneNoteCLI()

        with patch.object(cli.agent, 'get_recent_pages', new_callable=AsyncMock) as mock_recent:
            mock_recent.return_value = mock_pages

            with patch('rich.console.Console.print') as mock_print:
                await cli._show_recent_pages()

                mock_recent.assert_called_once()
                mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_show_conversation_starters(self):
        """Test /starters command."""
        cli = OneNoteCLI()

        # Test that the method executes without error
        result = await cli._show_conversation_starters()

        # Verify it returns True (success)
        assert result is True

        # Verify the agent method was called
        cli.agent.get_conversation_starters.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_history_command(self):
        """Test /clear command."""
        cli = OneNoteCLI()
        cli.conversation_history = ["message1", "message2", "message3"]

        with patch('rich.console.Console.clear') as mock_clear:
            with patch('rich.console.Console.print') as mock_print:
                await cli._clear_history()

                mock_clear.assert_called_once()
                assert cli.conversation_history == []

    @pytest.mark.asyncio
    async def test_quit_command(self):
        """Test /quit and /exit commands."""
        cli = OneNoteCLI()
        assert cli.running is True

        with patch('rich.console.Console.print') as mock_print:
            await cli._quit_chat()

            assert cli.running is False

    def test_is_command_recognition(self):
        """Test command recognition."""
        cli = OneNoteCLI()

        # Test valid commands
        assert cli._is_command("/help")
        assert cli._is_command("/quit")
        assert cli._is_command("/notebooks")

        # Test invalid inputs
        assert not cli._is_command("regular text")
        assert not cli._is_command("/ invalid")
        assert not cli._is_command("/unknown")

    @pytest.mark.asyncio
    async def test_handle_command_execution(self):
        """Test command execution."""
        cli = OneNoteCLI()

        with patch('rich.console.Console.print') as mock_print:
            # Test help command
            await cli._handle_command("/help")
            mock_print.assert_called()

            # Test unknown command
            mock_print.reset_mock()
            await cli._handle_command("/unknown")
            mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_process_user_query(self):
        """Test processing user queries."""
        mock_response = Mock()
        mock_response.answer = "This is the answer to your question."
        mock_response.sources = []

        cli = OneNoteCLI()

        with patch.object(cli.agent, 'process_query', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = mock_response

            with patch('rich.console.Console.print') as mock_print:
                await cli._process_user_query("What is in my notes?")

                mock_process.assert_called_once_with("What is in my notes?")

    @pytest.mark.asyncio
    async def test_process_user_query_with_error(self):
        """Test processing user queries with errors."""
        cli = OneNoteCLI()

        with patch.object(cli.agent, 'process_query', new_callable=AsyncMock) as mock_process:
            mock_process.side_effect = Exception("Test error")

            with patch('rich.console.Console.print') as mock_print:
                await cli._process_user_query("test query")

                mock_process.assert_called_once()
                mock_print.assert_called()
                # Just verify that an error panel was printed
                assert mock_print.call_count >= 1

    @pytest.mark.asyncio
    async def test_get_user_input(self):
        """Test user input handling."""
        with patch('rich.prompt.Prompt.ask', return_value="test input") as mock_prompt:
            cli = OneNoteCLI()
            result = await cli._get_user_input()

            assert result == "test input"
            mock_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_input_empty(self):
        """Test handling of empty user input."""
        with patch('rich.prompt.Prompt.ask', return_value="") as mock_prompt:
            cli = OneNoteCLI()
            result = await cli._get_user_input()

            assert result == ""
            mock_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_input_with_keyboard_interrupt(self):
        """Test handling of keyboard interrupt during input."""
        with patch('rich.prompt.Prompt.ask', side_effect=KeyboardInterrupt) as mock_prompt:
            cli = OneNoteCLI()

            with pytest.raises(KeyboardInterrupt):
                await cli._get_user_input()

    @pytest.mark.asyncio
    async def test_streaming_response_handling(self):
        """Test handling of streaming responses."""
        chunks = [
            StreamingChunk.status_chunk("Searching OneNote..."),
            StreamingChunk.text_chunk("Found relevant information"),
            StreamingChunk.text_chunk(" about your query.", is_final=True)
        ]

        async def mock_stream():
            for chunk in chunks:
                yield chunk

        cli = OneNoteCLI()

        with patch.object(cli.agent, 'process_query', new_callable=AsyncMock) as mock_stream_method:
            mock_stream_method.return_value = mock_stream()

            with patch('rich.console.Console.print') as mock_print:
                with patch('rich.live.Live') as mock_live_class:
                    mock_live = Mock()
                    mock_live_class.return_value.__enter__.return_value = mock_live

                    await cli._handle_streaming_response("test query")

                    mock_stream_method.assert_called_once()

    def test_conversation_history_management(self):
        """Test conversation history management."""
        cli = OneNoteCLI()

        # Test adding to history
        cli._add_to_history("user", "Hello")
        cli._add_to_history("assistant", "Hi there!")

        assert len(cli.conversation_history) == 2
        assert cli.conversation_history[0]["role"] == "user"
        assert cli.conversation_history[0]["content"] == "Hello"
        assert cli.conversation_history[1]["role"] == "assistant"
        assert cli.conversation_history[1]["content"] == "Hi there!"

    def test_error_formatting_and_display(self):
        """Test error formatting and display."""
        with patch('rich.console.Console.print') as mock_print:
            cli = OneNoteCLI()

            # Test various error types
            cli._display_error("Simple error message")
            mock_print.assert_called()

            # Test with exception
            mock_print.reset_mock()
            try:
                raise ValueError("Test exception")
            except Exception as e:
                cli._display_error("Error occurred", e)

            mock_print.assert_called()

    @pytest.mark.asyncio
    async def test_full_chat_session_flow(self):
        """Test a complete chat session flow."""
        inputs = ["Hello", "/help", "Search for meeting notes", "/quit"]
        input_iter = iter(inputs)

        def mock_input(*args, **kwargs):
            try:
                return next(input_iter)
            except StopIteration:
                return "/quit"

        mock_response = Mock()
        mock_response.answer = "Found meeting notes."
        mock_response.sources = []

        cli = OneNoteCLI()

        with patch('rich.prompt.Prompt.ask', side_effect=mock_input):
            with patch.object(cli.agent, 'initialize', new_callable=AsyncMock):
                with patch.object(cli.agent, 'process_query', new_callable=AsyncMock) as mock_process:
                    mock_process.return_value = mock_response

                    with patch('rich.console.Console.print'):
                        await cli.start_chat()

                        # Verify that the agent was used
                        assert not cli.running  # Should have quit
                        mock_process.assert_called()


class TestCLIHelpers:
    """Test CLI helper functions."""

    def test_cli_settings_integration(self):
        """Test integration with settings."""
        mock_settings = Mock()
        mock_settings.cli_color_enabled = False
        mock_settings.cli_markdown_enabled = False
        mock_settings.cli_welcome_enabled = False
        # Add realistic OpenAI settings
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-3.5-turbo"
        mock_settings.openai_temperature = 0.7
        mock_settings.openai_timeout = 30

        with patch('src.agents.onenote_agent.OneNoteAgent'):
            cli = OneNoteCLI(settings=mock_settings)

            assert cli.settings is mock_settings
            # Verify settings are used correctly
            assert cli.console.color_system is None  # Should be None when colors disabled
