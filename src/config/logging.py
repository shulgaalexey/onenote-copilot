"""
Comprehensive logging configuration for OneNote Copilot.

Provides structured logging with file output, clean startup, and Rich integration.
Follows Windows/PowerShell best practices and project requirements.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from .settings import get_settings


class OneNoteLogger:
    """
    Centralized logging configuration for OneNote Copilot.

    Features:
    - File logging with rotation
    - Rich console integration
    - Clean startup (clears log file)
    - Structured formatting
    - Performance tracking
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the logging system.

        Args:
            console: Rich console instance (creates new if None)
        """
        self.console = console or Console()
        self.settings = get_settings()
        self.log_file_path = self._get_log_file_path()
        self._configured = False

    def _get_log_file_path(self) -> Path:
        """Get the path for the main log file."""
        # Store logs in project root for easy access
        project_root = Path(__file__).parent.parent.parent
        logs_dir = project_root / "logs"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir / "onenote_copilot.log"

    def setup_logging(
        self,
        clear_log_file: bool = True,
        console_level: Optional[str] = None,
        file_level: Optional[str] = None
    ) -> None:
        """
        Configure comprehensive logging system.

        Args:
            clear_log_file: Whether to clear the log file on startup
            console_level: Console log level override
            file_level: File log level override
        """
        if self._configured:
            return

        # Determine log levels
        console_log_level = console_level or self.settings.log_level
        file_log_level = file_level or "DEBUG"  # Always capture debug in files

        # Clear log file if requested
        if clear_log_file and self.log_file_path.exists():
            try:
                self.log_file_path.unlink()
            except (PermissionError, OSError) as e:
                # On Windows, file might be locked - try to truncate instead
                try:
                    self.log_file_path.write_text("")
                except (PermissionError, OSError):
                    # If we can't clear the file, just continue
                    pass

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Capture everything

        # Remove existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create formatters
        console_formatter = logging.Formatter(
            "%(message)s"  # Rich handler handles the formatting
        )

        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Console handler with Rich
        console_handler = RichHandler(
            console=self.console,
            rich_tracebacks=True,
            show_path=console_log_level == "DEBUG",
            show_time=console_log_level == "DEBUG",
            markup=True
        )
        console_handler.setLevel(getattr(logging, console_log_level.upper()))
        console_handler.setFormatter(console_formatter)

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, file_log_level.upper()))
        file_handler.setFormatter(file_formatter)

        # Add handlers to root logger
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

        # Configure specific loggers
        self._configure_external_loggers()

        # Log startup message
        logger = logging.getLogger(__name__)
        logger.info("🚀 OneNote Copilot logging system initialized")
        logger.info(f"📁 Log file: {self.log_file_path}")
        logger.info(f"📊 Console level: {console_log_level}, File level: {file_log_level}")

        self._configured = True

    def _configure_external_loggers(self) -> None:
        """Configure logging levels for external libraries."""
        # Reduce noise from external libraries unless in debug mode
        if self.settings.log_level != "DEBUG":
            external_loggers = {
                "httpx": logging.WARNING,
                "urllib3": logging.WARNING,
                "msal": logging.WARNING,
                "openai": logging.WARNING,
                "langchain": logging.WARNING,
                "langgraph": logging.WARNING,
                "asyncio": logging.WARNING,
            }

            for logger_name, level in external_loggers.items():
                logging.getLogger(logger_name).setLevel(level)
        else:
            # In debug mode, ensure external loggers can inherit DEBUG level
            external_loggers = [
                "httpx", "urllib3", "msal", "openai",
                "langchain", "langgraph", "asyncio"
            ]
            for logger_name in external_loggers:
                # Set to NOTSET so they inherit from root logger (DEBUG)
                logging.getLogger(logger_name).setLevel(logging.NOTSET)

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module.

        Args:
            name: Logger name (typically __name__)

        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)

    def cleanup(self) -> None:
        """
        Cleanup logging handlers and close files.

        This method is particularly important on Windows where open file
        handles prevent temporary directories from being cleaned up properly.
        """
        root_logger = logging.getLogger()

        # Close and remove all file handlers
        for handler in root_logger.handlers[:]:  # Copy list to avoid modification during iteration
            if isinstance(handler, logging.FileHandler):
                handler.close()
                root_logger.removeHandler(handler)

        # Reset configuration state
        self._configured = False


# Global logger instance
_onenote_logger: Optional[OneNoteLogger] = None


def setup_logging(
    console: Optional[Console] = None,
    clear_log_file: bool = True,
    console_level: Optional[str] = None,
    file_level: Optional[str] = None
) -> OneNoteLogger:
    """
    Set up the global logging system.

    Args:
        console: Rich console instance
        clear_log_file: Whether to clear the log file on startup
        console_level: Console log level override
        file_level: File log level override

    Returns:
        Configured OneNoteLogger instance
    """
    global _onenote_logger

    if _onenote_logger is None:
        _onenote_logger = OneNoteLogger(console)

    _onenote_logger.setup_logging(
        clear_log_file=clear_log_file,
        console_level=console_level,
        file_level=file_level
    )

    return _onenote_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance

    Raises:
        RuntimeError: If logging hasn't been set up yet
    """
    if _onenote_logger is None:
        raise RuntimeError("Logging not initialized. Call setup_logging() first.")

    return _onenote_logger.get_logger(name)


def log_performance(func_name: str, duration: float, **kwargs) -> None:
    """
    Log performance metrics for functions.

    Args:
        func_name: Name of the function being measured
        duration: Duration in seconds
        **kwargs: Additional context data
    """
    logger = logging.getLogger("performance")

    context_str = ""
    if kwargs:
        context_items = [f"{k}={v}" for k, v in kwargs.items()]
        context_str = f" ({', '.join(context_items)})"

    logger.info(f"⚡ {func_name}: {duration:.3f}s{context_str}")


def log_api_call(
    method: str,
    url: str,
    status_code: Optional[int] = None,
    duration: Optional[float] = None,
    error: Optional[str] = None
) -> None:
    """
    Log API call details.

    Args:
        method: HTTP method
        url: Request URL (will be sanitized)
        status_code: Response status code
        duration: Request duration in seconds
        error: Error message if request failed
    """
    logger = logging.getLogger("api")

    # Sanitize URL to remove sensitive information
    sanitized_url = url
    if "access_token" in url:
        sanitized_url = url.split("access_token")[0] + "access_token=***"

    if error:
        logger.error(f"❌ {method} {sanitized_url} - Error: {error}")
    elif status_code:
        duration_str = f" ({duration:.3f}s)" if duration else ""
        if 200 <= status_code < 300:
            logger.info(f"✅ {method} {sanitized_url} - {status_code}{duration_str}")
        elif 400 <= status_code < 500:
            logger.warning(f"⚠️ {method} {sanitized_url} - {status_code}{duration_str}")
        else:
            logger.error(f"❌ {method} {sanitized_url} - {status_code}{duration_str}")
    else:
        logger.info(f"🔄 {method} {sanitized_url}")


class LoggedFunction:
    """Decorator for automatic function logging."""

    def __init__(self, logger_name: Optional[str] = None, log_args: bool = False):
        """
        Initialize the logged function decorator.

        Args:
            logger_name: Custom logger name (uses function module if None)
            log_args: Whether to log function arguments
        """
        self.logger_name = logger_name
        self.log_args = log_args

    def __call__(self, func):
        """Decorate the function with logging."""
        import functools
        import time

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(self.logger_name or func.__module__)

            # Log function entry
            if self.log_args and (args or kwargs):
                args_str = ", ".join([str(arg) for arg in args])
                kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
                all_args = ", ".join(filter(None, [args_str, kwargs_str]))
                logger.debug(f"🔄 {func.__name__}({all_args})")
            else:
                logger.debug(f"🔄 {func.__name__}()")

            # Execute function with timing
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.debug(f"✅ {func.__name__} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"❌ {func.__name__} failed in {duration:.3f}s: {e}")
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = logging.getLogger(self.logger_name or func.__module__)

            # Log function entry
            if self.log_args and (args or kwargs):
                args_str = ", ".join([str(arg) for arg in args])
                kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
                all_args = ", ".join(filter(None, [args_str, kwargs_str]))
                logger.debug(f"🔄 {func.__name__}({all_args})")
            else:
                logger.debug(f"🔄 {func.__name__}()")

            # Execute function with timing
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                logger.debug(f"✅ {func.__name__} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"❌ {func.__name__} failed in {duration:.3f}s: {e}")
                raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper


# Convenience decorator instances and functions
def logged(func_or_message=None, log_args=False):
    """
    Decorator for automatic function logging.

    Can be used in two ways:
    1. @logged - Simple decorator without parameters
    2. @logged("Custom message") - Decorator with custom logger name

    Args:
        func_or_message: Either a function (when used without parentheses)
                        or a string message (when used with parentheses)
        log_args: Whether to log function arguments

    Returns:
        Decorated function or decorator instance
    """
    # If called without parentheses: @logged
    if callable(func_or_message):
        return LoggedFunction(logger_name=None, log_args=log_args)(func_or_message)

    # If called with parentheses: @logged("message") or @logged()
    def decorator(func):
        logger_name = func_or_message if isinstance(func_or_message, str) else None
        return LoggedFunction(logger_name=logger_name, log_args=log_args)(func)

    return decorator

logged_with_args = lambda func_or_message=None: logged(func_or_message, log_args=True)


if __name__ == "__main__":
    """Test the logging configuration."""
    # Set up logging
    logger_system = setup_logging()

    # Test different log levels
    logger = get_logger(__name__)
    logger.debug("🐛 Debug message - detailed information")
    logger.info("ℹ️ Info message - general information")
    logger.warning("⚠️ Warning message - something unusual")
    logger.error("❌ Error message - something went wrong")

    # Test performance logging
    log_performance("test_function", 0.123, param1="value1", param2="value2")

    # Test API logging
    log_api_call("GET", "https://graph.microsoft.com/v1.0/me/onenote/pages", 200, 0.456)
    log_api_call("POST", "https://api.openai.com/v1/chat/completions", 429, 0.789)
    log_api_call("GET", "https://graph.microsoft.com/v1.0/me", error="Network timeout")

    # Test decorator
    @logged
    def test_function():
        """Test function for logging."""
        import time
        time.sleep(0.1)
        return "success"

    result = test_function()
    logger.info(f"✅ Test completed: {result}")
