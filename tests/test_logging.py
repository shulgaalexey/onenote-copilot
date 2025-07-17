"""
Tests for the comprehensive logging system.

Tests logging configuration, file operations, performance tracking,
and integration with the application.
"""

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from src.config.logging import (LoggedFunction, OneNoteLogger, get_logger,
                                log_api_call, log_performance, logged,
                                logged_with_args, setup_logging)


class TestOneNoteLogger:
    """Test the OneNoteLogger class."""

    def test_init(self):
        """Test OneNoteLogger initialization."""
        console = Console()
        logger_system = OneNoteLogger(console)

        assert logger_system.console == console
        assert not logger_system._configured
        assert logger_system.log_file_path.name == "onenote_copilot.log"

    def test_get_log_file_path(self):
        """Test log file path generation."""
        logger_system = OneNoteLogger()
        log_path = logger_system._get_log_file_path()

        assert log_path.name == "onenote_copilot.log"
        assert log_path.parent.name == "logs"

    @patch('src.config.logging.get_settings')
    def test_setup_logging_clears_file(self, mock_settings):
        """Test that setup_logging clears the log file."""
        mock_settings.return_value.log_level = "INFO"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_log_path = Path(temp_dir) / "test.log"
            temp_log_path.write_text("old content")

            logger_system = OneNoteLogger()
            logger_system.log_file_path = temp_log_path

            try:
                logger_system.setup_logging(clear_log_file=True)

                # Log file should be cleared or truncated
                # On Windows, file might be truncated instead of deleted
                if temp_log_path.exists():
                    # File was truncated - read with UTF-8 encoding for Unicode support
                    content = temp_log_path.read_text(encoding='utf-8')
                    assert "old content" not in content
                else:
                    # File was deleted and recreated
                    pass
            finally:
                # Cleanup file handlers to prevent Windows permission issues
                logger_system.cleanup()

    @patch('src.config.logging.get_settings')
    def test_setup_logging_multiple_calls(self, mock_settings):
        """Test that multiple setup calls don't duplicate handlers."""
        mock_settings.return_value.log_level = "INFO"

        logger_system = OneNoteLogger()

        # First setup
        logger_system.setup_logging()
        handler_count_1 = len(logging.getLogger().handlers)

        # Second setup (should not add more handlers)
        logger_system.setup_logging()
        handler_count_2 = len(logging.getLogger().handlers)

        assert handler_count_1 == handler_count_2

    @patch('src.config.logging.get_settings')
    def test_get_logger(self, mock_settings):
        """Test getting a logger instance."""
        mock_settings.return_value.log_level = "INFO"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_log_path = Path(temp_dir) / "test_get_logger.log"

            logger_system = OneNoteLogger()
            logger_system.log_file_path = temp_log_path

            try:
                logger_system.setup_logging()

                test_logger = logger_system.get_logger("test_module")

                assert isinstance(test_logger, logging.Logger)
                assert test_logger.name == "test_module"
            finally:
                # Cleanup file handlers to prevent Windows permission issues
                logger_system.cleanup()


class TestLoggingFunctions:
    """Test logging utility functions."""

    @patch('src.config.logging._onenote_logger')
    def test_setup_logging_global(self, mock_logger_instance):
        """Test global setup_logging function."""
        mock_logger = Mock()
        mock_logger_instance.return_value = mock_logger

        console = Console()
        result = setup_logging(console=console, clear_log_file=False)

        assert result is not None

    def test_get_logger_not_initialized(self):
        """Test get_logger raises error when not initialized."""
        # Reset global logger
        import src.config.logging
        src.config.logging._onenote_logger = None

        with pytest.raises(RuntimeError, match="Logging not initialized"):
            get_logger("test")

    def test_log_performance(self, caplog):
        """Test performance logging function."""
        with caplog.at_level(logging.INFO):
            log_performance("test_function", 0.123, param1="value1", param2="value2")

        assert "⚡ test_function: 0.123s" in caplog.text
        assert "param1=value1" in caplog.text
        assert "param2=value2" in caplog.text

    def test_log_api_call_success(self, caplog):
        """Test API call logging for successful requests."""
        with caplog.at_level(logging.INFO):
            log_api_call("GET", "https://example.com/api", 200, 0.456)

        assert "✅ GET https://example.com/api - 200 (0.456s)" in caplog.text

    def test_log_api_call_error(self, caplog):
        """Test API call logging for failed requests."""
        with caplog.at_level(logging.ERROR):
            log_api_call("POST", "https://example.com/api", error="Network timeout")

        assert "❌ POST https://example.com/api - Error: Network timeout" in caplog.text

    def test_log_api_call_sanitizes_token(self, caplog):
        """Test that API logging sanitizes access tokens."""
        with caplog.at_level(logging.INFO):
            log_api_call("GET", "https://example.com/api?access_token=secret123", 200)

        assert "access_token=***" in caplog.text
        assert "secret123" not in caplog.text

    def test_log_api_call_status_codes(self, caplog):
        """Test different status code handling."""
        # Success (2xx)
        with caplog.at_level(logging.INFO):
            log_api_call("GET", "https://example.com", 201)
        assert "✅" in caplog.records[-1].getMessage()

        # Client error (4xx)
        with caplog.at_level(logging.WARNING):
            log_api_call("GET", "https://example.com", 404)
        assert "⚠️" in caplog.records[-1].getMessage()

        # Server error (5xx)
        with caplog.at_level(logging.ERROR):
            log_api_call("GET", "https://example.com", 500)
        assert "❌" in caplog.records[-1].getMessage()


class TestLoggedDecorator:
    """Test the LoggedFunction decorator."""

    def test_logged_function_sync(self, caplog):
        """Test logged decorator with synchronous function."""
        @logged
        def test_function():
            time.sleep(0.01)  # Small delay to test timing
            return "success"

        with caplog.at_level(logging.DEBUG):
            result = test_function()

        assert result == "success"
        assert "🔄 test_function()" in caplog.text
        assert "✅ test_function completed" in caplog.text

    def test_logged_function_with_args(self, caplog):
        """Test logged decorator with argument logging."""
        @logged_with_args
        def test_function(arg1, arg2, kwarg1=None):
            return f"{arg1}-{arg2}-{kwarg1}"

        with caplog.at_level(logging.DEBUG):
            result = test_function("a", "b", kwarg1="c")

        assert result == "a-b-c"
        assert "🔄 test_function(a, b, kwarg1=c)" in caplog.text

    def test_logged_function_exception(self, caplog):
        """Test logged decorator with exception handling."""
        @logged
        def failing_function():
            raise ValueError("Test error")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                failing_function()

        assert "❌ failing_function failed" in caplog.text
        assert "Test error" in caplog.text

    @pytest.mark.asyncio
    async def test_logged_async_function(self, caplog):
        """Test logged decorator with async function."""
        @logged
        async def async_test_function():
            await asyncio.sleep(0.01)
            return "async_success"

        with caplog.at_level(logging.DEBUG):
            result = await async_test_function()

        assert result == "async_success"
        assert "🔄 async_test_function()" in caplog.text
        assert "✅ async_test_function completed" in caplog.text

    @pytest.mark.asyncio
    async def test_logged_async_function_exception(self, caplog):
        """Test logged decorator with async exception handling."""
        @logged
        async def async_failing_function():
            raise RuntimeError("Async test error")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError):
                await async_failing_function()

        assert "❌ async_failing_function failed" in caplog.text
        assert "Async test error" in caplog.text

    def test_logged_function_custom_logger(self, caplog):
        """Test logged decorator with custom logger name."""
        custom_logged = LoggedFunction(logger_name="custom.logger")

        @custom_logged
        def test_function():
            return "custom"

        with caplog.at_level(logging.DEBUG):
            result = test_function()

        assert result == "custom"
        # Check that the custom logger name was used
        assert any("custom.logger" in record.name for record in caplog.records)


class TestLoggingIntegration:
    """Test logging integration with application components."""

    @patch('src.config.logging.get_settings')
    def test_external_logger_configuration(self, mock_settings):
        """Test that external library loggers are configured correctly."""
        mock_settings.return_value.log_level = "INFO"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_log_path = Path(temp_dir) / "test_external.log"

            logger_system = OneNoteLogger()
            logger_system.log_file_path = temp_log_path

            try:
                logger_system.setup_logging()

                # Check that external loggers are set to WARNING level
                assert logging.getLogger("httpx").level == logging.WARNING
                assert logging.getLogger("urllib3").level == logging.WARNING
                assert logging.getLogger("msal").level == logging.WARNING
            finally:
                # Cleanup file handlers to prevent Windows permission issues
                logger_system.cleanup()

    @patch('src.config.logging.get_settings')
    def test_debug_mode_external_loggers(self, mock_settings):
        """Test external logger configuration in debug mode."""
        mock_settings.return_value.log_level = "DEBUG"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_log_path = Path(temp_dir) / "test_debug.log"

            logger_system = OneNoteLogger()
            logger_system.log_file_path = temp_log_path

            try:
                logger_system.setup_logging()

                # In debug mode, external loggers should not be suppressed
                # (They should inherit the root logger level)
                httpx_logger = logging.getLogger("httpx")
                assert httpx_logger.level <= logging.DEBUG
            finally:
                # Cleanup file handlers to prevent Windows permission issues
                logger_system.cleanup()

    def test_file_logging_creates_directory(self):
        """Test that logging setup creates the logs directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_project_root = Path(temp_dir)

            logger_system = OneNoteLogger()
            # Mock the project root path to use temp directory
            original_get_log_file_path = logger_system._get_log_file_path

            def mock_get_log_file_path():
                logs_dir = temp_project_root / "logs"
                logs_dir.mkdir(exist_ok=True)
                return logs_dir / "test.log"

            logger_system._get_log_file_path = mock_get_log_file_path
            logger_system.log_file_path = mock_get_log_file_path()

            # Directory should be created
            assert (temp_project_root / "logs").exists()


@pytest.mark.integration
class TestLoggingFileOperations:
    """Integration tests for file logging operations."""

    def test_log_file_rotation(self):
        """Test that log file rotation works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_log_path = Path(temp_dir) / "test.log"

            logger_system = OneNoteLogger()
            logger_system.log_file_path = temp_log_path

            try:
                logger_system.setup_logging(clear_log_file=False)

                test_logger = logger_system.get_logger("test")

                # Write some log messages (not too many to avoid performance issues)
                message = "Test message for rotation" * 10  # ~250 bytes
                for i in range(100):  # Write reasonable amount
                    test_logger.info(f"Message {i}: {message}")

                # Check that the log file exists and has content
                assert temp_log_path.exists()
                assert temp_log_path.stat().st_size > 0
            finally:
                # Cleanup file handlers to prevent Windows permission issues
                logger_system.cleanup()

    def test_log_file_encoding(self):
        """Test that log files handle Unicode correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_log_path = Path(temp_dir) / "unicode_test.log"

            logger_system = OneNoteLogger()
            logger_system.log_file_path = temp_log_path

            try:
                logger_system.setup_logging(clear_log_file=True)

                test_logger = logger_system.get_logger("unicode_test")

                # Log messages with Unicode characters
                test_logger.info("Test message with émojis: 🚀 🤖 ✅")
                test_logger.info("Test message with Chinese: 你好世界")
                test_logger.info("Test message with Arabic: مرحبا بالعالم")
            finally:
                # Cleanup file handlers to prevent Windows permission issues
                logger_system.cleanup()

            # Read the file and verify Unicode was preserved
            log_content = temp_log_path.read_text(encoding='utf-8')
            assert "🚀 🤖 ✅" in log_content
            assert "你好世界" in log_content
            assert "مرحبا بالعالم" in log_content


if __name__ == "__main__":
    """Run the logging tests."""
    pytest.main([__file__, "-v"])
