# Logging Configuration Improvements

## Overview
The logging system has been significantly improved to provide cleaner, more useful debug information while filtering out excessive noise from external libraries.

## Key Improvements

### 1. External Library Filtering
- **httpcore**: Reduced from DEBUG to WARNING level to eliminate TCP connection noise
- **markdown_it**: Completely filtered markdown parsing internals that were flooding logs
- **MSAL**: Kept at INFO level for authentication debugging while reducing noise
- **Other libraries**: Comprehensive filtering of langchain, openai, asyncio, etc.

### 2. Enhanced Performance Logging
```python
# Old format:
⚡ function_name: 0.123s (param1=value1, param2=value2)

# New format:
[FAST] function_name: 123ms (count=5, operation=search)
[SLOW] slow_operation: 2.10s (results=100, status=completed)
```

Features:
- Readable duration formatting (ms for < 1s, s for >= 1s)
- Performance indicators: [FAST] < 100ms, [NORM] < 1s, [SLOW] >= 1s
- Contextual parameter filtering (count, size, pages, results, operation, etc.)

### 3. Windows Compatibility
- Removed Unicode emoji characters that caused encoding errors
- Replaced with plain text prefixes: [SUCCESS], [ERROR], [ENTER], [EXIT], etc.

### 4. Dynamic Debug Control
New functions for targeted debugging:
```python
from src.config.logging import enable_component_debug, disable_component_debug

# Enable debug for specific component when needed
enable_component_debug('httpcore')  # Only when debugging HTTP issues

# Disable when done
disable_component_debug('httpcore')
```

### 5. Noise Filter
Added a logging filter that completely excludes extremely verbose patterns:
- `markdown_it.rules_block.*` - Markdown parsing internals
- `httpcore.http11` - HTTP connection details
- `httpcore.connection` - TCP connection details

## Results

### Before
- 1500+ log lines for simple operations
- Flooded with TCP connection details and markdown parsing steps
- Application logic buried in external library noise
- Unicode encoding errors on Windows

### After
- ~13 focused log lines for the same operations
- Clear application-level messages with performance metrics
- External library noise filtered but errors still visible
- Windows-compatible plain text formatting

## Usage Examples

### Basic Logging
```python
from src.config.logging import setup_logging, get_logger

logger_system = setup_logging()
logger = get_logger(__name__)

logger.info("Application started")  # Clean, focused messages
logger.debug("Detailed debug info") # Application-level only
```

### Performance Tracking
```python
from src.config.logging import log_performance

# Automatic formatting and performance classification
log_performance('search_operation', 0.045, count=10, operation='semantic')
# Output: [FAST] search_operation: 45ms (count=10, operation=semantic)
```

### Targeted Debugging
```python
from src.config.logging import enable_component_debug

# When you need to debug HTTP issues specifically
enable_component_debug('httpcore')

# Your HTTP operations here...

disable_component_debug('httpcore')  # Clean up when done
```

## Configuration Files
- **Main config**: `src/config/logging.py`
- **Log output**: `logs/onenote_copilot.log`
- **Settings**: `src/config/settings.py` (log_level configuration)

## Future Enhancements
- Consider adding structured logging (JSON format) for production monitoring
- Add log aggregation and analysis tools for performance insights
- Implement log level configuration per module/component
- Add log sampling for high-frequency operations
