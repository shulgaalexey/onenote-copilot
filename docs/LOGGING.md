# OneNote Copilot Logging System

This document describes the comprehensive logging system implemented in OneNote Copilot.

## Overview

The logging system provides structured logging with both console and file output, designed for development and production use.

## Features

### 🗂️ File Logging
- **Location**: `logs/onenote_copilot.log` in project root
- **Rotation**: 10MB files, 5 backup copies
- **Encoding**: UTF-8 with full Unicode support
- **Clean Start**: Log file cleared on each application startup

### 🖥️ Console Logging
- **Rich Integration**: Beautiful formatted output using Rich library
- **Configurable Levels**: Respects user-defined log levels
- **Debug Mode**: Enhanced output with timestamps and paths

### ⚡ Performance Tracking
- **API Calls**: HTTP request/response logging with timing
- **Function Execution**: Automatic timing with decorators
- **Context Logging**: Additional parameters and metadata

### 🛡️ Error Handling
- **Exception Tracking**: Full stack traces in debug mode
- **Windows Compatibility**: Handles file locking gracefully
- **External Library Control**: Suppresses noisy third-party logs

## Usage

### Basic Setup

```python
from src.config.logging import setup_logging, get_logger

# Initialize logging system
setup_logging(clear_log_file=True, console_level="INFO", file_level="DEBUG")

# Get logger for your module
logger = get_logger(__name__)

# Use the logger
logger.info("Application started successfully")
logger.error("Something went wrong", exc_info=True)
```

### Performance Logging

```python
from src.config.logging import log_performance, log_api_call

# Log function performance
start_time = time.time()
# ... your code ...
duration = time.time() - start_time
log_performance("my_function", duration, param1="value1", param2="value2")

# Log API calls
log_api_call("GET", "https://graph.microsoft.com/v1.0/me", 200, 0.456)
```

### Decorators

```python
from src.config.logging import logged, logged_with_args

# Basic function logging
@logged
def my_function():
    return "result"

# Function logging with arguments
@logged_with_args
def my_function_with_args(arg1, arg2, kwarg1=None):
    return f"{arg1}-{arg2}-{kwarg1}"

# Async function support
@logged
async def my_async_function():
    await asyncio.sleep(0.1)
    return "async_result"
```

## Configuration

### Environment Variables

```bash
# Logging configuration
ONENOTE_DEBUG=true                    # Enable debug mode
LOG_LEVEL=INFO                        # Console log level
LOG_FILE_ENABLED=true                 # Enable file logging
LOG_CLEAR_ON_STARTUP=true             # Clear log file on startup
LOG_PERFORMANCE_ENABLED=true          # Enable performance logging
```

### Settings in Code

```python
from src.config.settings import get_settings

settings = get_settings()
settings.log_level = "DEBUG"
settings.log_file_enabled = True
settings.log_clear_on_startup = True
settings.log_performance_enabled = True
```

## Log Format

### Console Output (Rich Formatted)
```
INFO     🚀 OneNote Copilot logging system initialized
INFO     📁 Log file: C:\src\onenote-copilot\logs\onenote_copilot.log
INFO     ✅ GET https://graph.microsoft.com/v1.0/me/onenote/pages - 200 (0.456s)
```

### File Output (Structured)
```
2025-07-16 15:51:31 - __main__ - INFO - setup_logging:125 - 🚀 OneNote Copilot logging system initialized
2025-07-16 15:51:31 - performance - INFO - log_performance:232 - ⚡ search_pages: 0.456s (query=test, results=5)
2025-07-16 15:51:31 - api - INFO - log_api_call:264 - ✅ GET https://graph.microsoft.com/v1.0/me/onenote/pages - 200 (0.456s)
```

## Log Levels

- **DEBUG**: Detailed information for debugging
- **INFO**: General application flow and status updates
- **WARNING**: Warnings about unusual conditions
- **ERROR**: Error conditions that don't stop the application
- **CRITICAL**: Serious errors that may stop the application

## Special Loggers

### Performance Logger
- **Name**: `performance`
- **Purpose**: Function execution timing
- **Format**: `⚡ function_name: duration (context)`

### API Logger
- **Name**: `api`
- **Purpose**: HTTP request/response tracking
- **Format**: `✅/⚠️/❌ METHOD URL - STATUS (duration)`

## Best Practices

### 1. Use Appropriate Log Levels
```python
logger.debug("Detailed debugging information")
logger.info("General information about application flow")
logger.warning("Something unusual happened but it's not an error")
logger.error("An error occurred", exc_info=True)
```

### 2. Include Context
```python
logger.info(f"Processing user request", extra={
    "user_id": user_id,
    "request_type": "search",
    "query": query
})
```

### 3. Use Performance Logging for Critical Paths
```python
@logged
async def search_onenote_pages(query: str) -> List[OneNotePage]:
    # Function automatically logged with timing
    pass
```

### 4. Sanitize Sensitive Information
```python
# The logging system automatically sanitizes access tokens
log_api_call("GET", "https://api.service.com?access_token=secret123", 200)
# Logs: "GET https://api.service.com?access_token=***"
```

## Debugging

### Enable Debug Mode
```bash
python -m src.main --debug
```

### View Recent Logs
```bash
tail -f logs/onenote_copilot.log
```

### Check Log File Size
```bash
ls -la logs/
```

## Troubleshooting

### Common Issues

1. **Log file not created**: Check permissions on `logs/` directory
2. **File locked on Windows**: The system handles this gracefully by truncating instead of deleting
3. **Too many logs**: Adjust `log_level` in settings or disable `log_performance_enabled`
4. **Unicode characters not showing**: Ensure terminal supports UTF-8

### Log File Cleanup

```python
# Manual cleanup if needed
from pathlib import Path
log_file = Path("logs/onenote_copilot.log")
if log_file.exists():
    log_file.unlink()  # Delete log file
```

## Testing

Run logging tests:
```bash
python -m pytest tests/test_logging.py -v
```

Test configuration:
```bash
python -m src.config.logging
```
