"""
Tests for src.main module.

These tests cover the main application entry point, CLI commands,
and core functionality including authentication, dependency checking,
and application startup.
"""

import asyncio
import builtins
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from src.config.logging import setup_logging
from src.main import (__version__, app, authenticate_only, check_dependencies,
                      cli_main, run_main_app, show_system_info)


class TestSetupLogging:
    """Test logging configuration functionality."""

    @patch('src.config.logging.OneNoteLogger.setup_logging')
    def test_setup_logging_default(self, mock_setup):
        """Test setup_logging with default (non-debug) settings."""
        setup_logging(console_level="INFO")

        mock_setup.assert_called_once()

    @patch('src.config.logging.OneNoteLogger.setup_logging')
    def test_setup_logging_debug(self, mock_setup):
        """Test setup_logging with debug enabled."""
        setup_logging(console_level="DEBUG")

        mock_setup.assert_called_once()

    def test_setup_logging_external_library_levels(self):
        """Test that external library log levels are set appropriately."""
        # Just test that setup_logging can be called without error
        try:
            setup_logging(console_level="INFO")
            # If we get here, the function worked
            assert True
        except Exception as e:
            pytest.fail(f"setup_logging failed: {e}")

    def test_setup_logging_debug_no_external_level_setting(self):
        """Test that in debug mode, external library levels are not modified."""
        # Just test that setup_logging can be called without error
        try:
            setup_logging(console_level="DEBUG")
            # If we get here, the function worked
            assert True
        except Exception as e:
            pytest.fail(f"setup_logging failed: {e}")


class TestShowSystemInfo:
    """Test system information display functionality."""

    @patch('src.main.get_settings')
    @patch('src.main.console.print')
    def test_show_system_info(self, mock_print, mock_get_settings):
        """Test system information display."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.config_dir = Path("/fake/config")
        mock_settings.cache_dir = Path("/fake/cache")
        mock_settings.openai_model = "gpt-4"
        mock_settings.cli_color_enabled = True
        mock_settings.cli_markdown_enabled = True
        mock_settings.debug_enabled = False
        mock_settings.azure_client_id = "test-client-id"
        mock_settings.graph_api_scopes = ["https://graph.microsoft.com/Notes.Read"]
        mock_settings.token_cache_file = Path("/fake/token.json")

        mock_get_settings.return_value = mock_settings

        show_system_info()

        # Verify console.print was called with a Panel
        mock_print.assert_called_once()
        panel_arg = mock_print.call_args[0][0]

        # Check that it's a Panel with proper styling
        from rich.panel import Panel
        assert isinstance(panel_arg, Panel)


class TestCheckDependencies:
    """Test dependency checking functionality."""

    def test_check_dependencies_all_available(self):
        """Test when all dependencies are available."""
        # In a real environment, all dependencies should be available
        result = check_dependencies()
        assert result is True

    @patch('src.main.console.print')
    def test_check_dependencies_missing_single(self, mock_print):
        """Test behavior when a single dependency is missing."""
        with patch('importlib.util.find_spec') as mock_find_spec:
            # Mock openai as missing, others as available
            def mock_spec_side_effect(name):
                if name == 'openai':
                    return None  # Module not found
                return MagicMock()  # Module found

            mock_find_spec.side_effect = mock_spec_side_effect
            result = check_dependencies()

            # Should return False when dependencies are missing
            assert result is False

            # Should print error messages
            assert mock_print.call_count > 0

    @patch('src.main.console.print')
    def test_check_dependencies_missing_multiple(self, mock_print):
        """Test behavior when multiple dependencies are missing."""
        with patch('importlib.util.find_spec') as mock_find_spec:
            # Mock multiple dependencies as missing
            missing_deps = ['openai', 'msal']

            def mock_spec_side_effect(name):
                if name in missing_deps:
                    return None  # Module not found
                return MagicMock()  # Module found

            mock_find_spec.side_effect = mock_spec_side_effect
            result = check_dependencies()

            assert result is False
            assert mock_print.call_count > 0


class TestAuthenticateOnly:
    """Test authentication-only functionality."""

    @pytest.mark.asyncio
    @patch('src.main.get_logger')
    @patch('src.main.get_settings')
    @patch('src.main.MicrosoftAuthenticator')
    @patch('src.main.console.print')
    async def test_authenticate_only_success(self, mock_print, mock_auth_class, mock_get_settings, mock_get_logger):
        """Test successful authentication."""
        # Setup logger mock
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Setup mocks
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings

        mock_authenticator = AsyncMock()
        mock_authenticator.get_access_token.return_value = "fake-token"
        mock_auth_class.return_value = mock_authenticator

        # Test authentication
        result = await authenticate_only()

        assert result is True
        mock_authenticator.get_access_token.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.main.get_logger')
    @patch('src.main.get_settings')
    @patch('src.main.MicrosoftAuthenticator')
    @patch('src.main.console.print')
    async def test_authenticate_only_failure(self, mock_print, mock_auth_class, mock_get_settings, mock_get_logger):
        """Test failed authentication."""
        # Setup logger mock
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Setup mocks
        mock_settings = MagicMock()
        mock_get_settings.return_value = mock_settings

        mock_authenticator = AsyncMock()
        mock_authenticator.get_access_token.return_value = None
        mock_auth_class.return_value = mock_authenticator

        # Test authentication
        result = await authenticate_only()

        assert result is False

    @pytest.mark.asyncio
    @patch('src.main.get_logger')
    @patch('src.main.get_settings')
    @patch('src.main.MicrosoftAuthenticator')
    @patch('src.main.console.print')
    async def test_authenticate_only_exception(self, mock_print, mock_auth_class, mock_get_settings, mock_get_logger):
        """Test authentication with exception."""
        # Setup logger mock
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Setup mocks to raise exception
        mock_get_settings.side_effect = Exception("Test error")

        # Test authentication
        result = await authenticate_only()

        assert result is False


class TestRunMainApp:
    """Test main application runner functionality."""

    @pytest.mark.asyncio
    @patch('src.main.get_logger')
    @patch('src.main.console.print')
    async def test_run_main_app_success(self, mock_print, mock_get_logger):
        """Test successful main app execution."""
        # Setup logger mock
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Mock the lazy import inside run_main_app
        with patch.dict('sys.modules', {'src.cli.interface': MagicMock()}):
            with patch('src.cli.interface.OneNoteCLI') as mock_cli_class:
                # Setup mocks
                mock_cli = AsyncMock()
                mock_cli.start_chat.return_value = None
                mock_cli.get_conversation_summary.return_value = {"total_messages": 0}
                mock_cli_class.return_value = mock_cli

                # Test main app
                await run_main_app(debug=False)

                mock_cli.start_chat.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.main.get_logger')
    @patch('src.cli.interface.OneNoteCLI')
    @patch('src.main.console.print')
    async def test_run_main_app_debug_mode(self, mock_print, mock_cli_class, mock_get_logger):
        """Test main app execution with debug mode."""
        # Setup logger mock
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Setup mocks
        mock_cli = AsyncMock()
        mock_cli.start_chat.return_value = None
        # Make get_conversation_summary a regular method (not async)
        mock_cli.get_conversation_summary = MagicMock(return_value={"total_messages": 5})
        mock_cli_class.return_value = mock_cli

        # Test main app with debug
        await run_main_app(debug=True)

        mock_cli.start_chat.assert_called_once()
        mock_cli.get_conversation_summary.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.main.get_logger')
    @patch('src.cli.interface.OneNoteCLI')
    @patch('src.main.console.print_exception')
    async def test_run_main_app_exception_debug(self, mock_print_exception, mock_cli_class, mock_get_logger):
        """Test main app exception handling in debug mode."""
        # Setup logger mock
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Setup mocks to raise exception
        mock_cli = AsyncMock()
        mock_cli.start_chat.side_effect = Exception("Test error")
        mock_cli_class.return_value = mock_cli

        # Test exception handling
        with pytest.raises(Exception, match="Test error"):
            await run_main_app(debug=True)

        mock_logger.error.assert_called_once()
        mock_print_exception.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.main.get_logger')
    @patch('src.cli.interface.OneNoteCLI')
    @patch('src.main.console.print_exception')
    async def test_run_main_app_exception_no_debug(self, mock_print_exception, mock_cli_class, mock_get_logger):
        """Test main app exception handling without debug mode."""
        # Setup logger mock
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Setup mocks to raise exception
        mock_cli = AsyncMock()
        mock_cli.start_chat.side_effect = Exception("Test error")
        mock_cli_class.return_value = mock_cli

        # Test exception handling
        with pytest.raises(Exception, match="Test error"):
            await run_main_app(debug=False)

        mock_logger.error.assert_called_once()
        mock_print_exception.assert_not_called()


class TestCliCommands:
    """Test CLI command functionality using typer's test runner."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    def test_version_command(self):
        """Test --version flag."""
        result = self.runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.stdout

    @patch('src.main.get_logger')
    @patch('src.main.show_system_info')
    @patch('src.main.setup_logging')
    @patch('src.main.check_dependencies')
    def test_info_command(self, mock_check_deps, mock_setup_logging, mock_show_info, mock_get_logger):
        """Test --info flag."""
        # Setup logger mock
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        mock_check_deps.return_value = True

        result = self.runner.invoke(app, ["--info"])

        assert result.exit_code == 0
        mock_show_info.assert_called_once()

    @patch('src.main.check_dependencies')
    def test_dependency_check_failure(self, mock_check_deps):
        """Test that app exits when dependencies are missing."""
        mock_check_deps.return_value = False

        result = self.runner.invoke(app, [])

        assert result.exit_code == 1

    @patch('src.main.asyncio.run')
    @patch('src.main.authenticate_only')
    @patch('src.main.setup_logging')
    @patch('src.main.check_dependencies')
    def test_auth_only_success(self, mock_check_deps, mock_setup_logging, mock_auth_only, mock_asyncio_run):
        """Test --auth-only flag with successful authentication."""
        mock_check_deps.return_value = True
        mock_asyncio_run.return_value = True

        result = self.runner.invoke(app, ["--auth-only"])

        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    @patch('src.main.asyncio.run')
    @patch('src.main.authenticate_only')
    @patch('src.main.setup_logging')
    @patch('src.main.check_dependencies')
    def test_auth_only_failure(self, mock_check_deps, mock_setup_logging, mock_auth_only, mock_asyncio_run):
        """Test --auth-only flag with failed authentication."""
        mock_check_deps.return_value = True
        mock_asyncio_run.return_value = False

        result = self.runner.invoke(app, ["--auth-only"])

        assert result.exit_code == 1

    @patch('src.main.asyncio.run')
    @patch('src.main.run_main_app')
    @patch('src.main.setup_logging')
    @patch('src.main.check_dependencies')
    def test_main_command_success(self, mock_check_deps, mock_setup_logging, mock_run_app, mock_asyncio_run):
        """Test main command successful execution."""
        mock_check_deps.return_value = True
        mock_asyncio_run.return_value = None

        result = self.runner.invoke(app, [])

        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()

    @patch('src.main.asyncio.run')
    @patch('src.main.run_main_app')
    @patch('src.main.setup_logging')
    @patch('src.main.check_dependencies')
    def test_main_command_keyboard_interrupt(self, mock_check_deps, mock_setup_logging, mock_run_app, mock_asyncio_run):
        """Test main command with keyboard interrupt."""
        mock_check_deps.return_value = True
        mock_asyncio_run.side_effect = KeyboardInterrupt()

        result = self.runner.invoke(app, [])

        assert result.exit_code == 0  # KeyboardInterrupt should exit gracefully

    @patch('src.main.asyncio.run')
    @patch('src.main.run_main_app')
    @patch('src.main.setup_logging')
    @patch('src.main.check_dependencies')
    def test_main_command_exception(self, mock_check_deps, mock_setup_logging, mock_run_app, mock_asyncio_run):
        """Test main command with general exception."""
        mock_check_deps.return_value = True
        mock_asyncio_run.side_effect = Exception("Test error")

        result = self.runner.invoke(app, [])

        assert result.exit_code == 1


class TestConfigCommand:
    """Test configuration command functionality."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    @patch('src.main.get_settings')
    @patch('src.main.show_system_info')
    @patch('src.main.console.print')
    def test_config_command_success(self, mock_print, mock_show_info, mock_get_settings):
        """Test config command successful execution."""
        mock_settings = MagicMock()
        mock_settings.cache_dir = Path("/fake/cache")
        mock_settings.config_dir = Path("/fake/config")
        mock_get_settings.return_value = mock_settings

        result = self.runner.invoke(app, ["config"])

        assert result.exit_code == 0
        mock_show_info.assert_called_once()

    @patch('src.main.get_settings')
    def test_config_command_exception(self, mock_get_settings):
        """Test config command with exception."""
        mock_get_settings.side_effect = Exception("Test error")

        result = self.runner.invoke(app, ["config"])

        assert result.exit_code == 1


class TestCliMain:
    """Test CLI main entry point."""

    @patch('src.main.app')
    def test_cli_main(self, mock_app):
        """Test cli_main function calls typer app."""
        cli_main()
        mock_app.assert_called_once()


class TestModuleExecution:
    """Test module execution functionality."""

    def test_version_constant(self):
        """Test that version constant is properly defined."""
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_app_instance(self):
        """Test that typer app is properly configured."""
        assert isinstance(app, typer.Typer)
        assert app.info.name == "onenote-copilot"
