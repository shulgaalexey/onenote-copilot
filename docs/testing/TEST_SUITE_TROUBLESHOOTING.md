# OneNote Copilot Test Suite Troubleshooting Guide

## Quick Diagnosis

### Performance Issues

#### Tests Running Slowly
```powershell
# Check test timing
python -m pytest tests/ --durations=10

# Identify slow tests
python -m pytest tests/ --durations=0 | Select-String -Pattern "s call"

# Check parallel execution
python -m pytest tests/ -n auto --durations=5
```

**Common Causes**:
- Missing parallel execution (`-n auto`)
- Slow tests not properly marked
- Heavy imports in test files
- Missing mocks for external services

#### Test Collection Slow
```powershell
# Time test collection
Measure-Command { python -m pytest tests/ --collect-only }

# Check for import issues
python -c "import tests.conftest; print('conftest.py imports OK')"
```

**Common Causes**:
- Heavy imports in conftest.py
- Missing lazy imports
- Circular import dependencies

### Test Execution Issues

#### Tests Fail in Parallel but Pass Individually
```powershell
# Run sequentially
python -m pytest tests/test_problematic.py -v

# Run in parallel
python -m pytest tests/test_problematic.py -n 2 -v
```

**Common Causes**:
- Shared global state
- File system conflicts
- Database connection issues
- Race conditions

#### Mock-Related Failures
```powershell
# Check mock configuration
python -c "from unittest.mock import patch; print('Mock module OK')"

# Verify patch paths
python -m pytest tests/ -v -s | Select-String -Pattern "Mock"
```

**Common Causes**:
- Incorrect patch paths
- Missing mock imports
- Wrong mock return types
- Scope issues with patches

### Environment Issues

#### Virtual Environment Problems
```powershell
# Check virtual environment
python -c "import sys; print(sys.prefix)"

# Verify dependencies
pip list | Select-String -Pattern "pytest"
```

**Solutions**:
```powershell
# Recreate virtual environment
deactivate
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### Missing Dependencies
```powershell
# Check pytest plugins
python -m pytest --version

# Install missing plugins
pip install pytest-xdist pytest-cov pytest-sugar pytest-asyncio
```

### Coverage Issues

#### Coverage Drops After Optimization
```powershell
# Generate detailed coverage report
python -m pytest tests/ --cov=src --cov-report=html

# Check uncovered lines
python -m pytest tests/ --cov=src --cov-report=term-missing
```

**Solutions**:
- Verify test selection includes all paths
- Check for over-mocking
- Ensure integration tests run in CI

#### Coverage Collection Errors
```powershell
# Check coverage configuration
python -c "import coverage; print(coverage.__version__)"

# Test coverage module
python -m pytest tests/test_simple.py --cov=src
```

## Error Message Decoder

### Common Error Messages and Solutions

#### "No tests ran matching the given pattern"
```
ERROR: No tests ran matching the given pattern
```

**Causes**:
- Incorrect test marker
- Wrong file path
- Missing test files

**Solutions**:
```powershell
# Check available markers
python -m pytest --markers

# List all tests
python -m pytest --collect-only

# Check specific marker
python -m pytest tests/ -m "fast" --collect-only
```

#### "ImportError: No module named 'pytest_xdist'"
```
ImportError: No module named 'pytest_xdist'
```

**Solutions**:
```powershell
# Install pytest-xdist
pip install pytest-xdist

# Add to requirements.txt
Add-Content -Path "requirements.txt" -Value "pytest-xdist>=2.5.0"
```

#### "ResourceWarning: unclosed file"
```
ResourceWarning: unclosed file <_io.TextIOWrapper>
```

**Solutions**:
```python
# Use context managers
with open('file.txt', 'r') as f:
    content = f.read()

# Or ensure proper cleanup in fixtures
@pytest.fixture
def temp_file():
    f = tempfile.NamedTemporaryFile(delete=False)
    yield f.name
    f.close()
    os.unlink(f.name)
```

#### "RuntimeError: cannot be called from a running event loop"
```
RuntimeError: cannot be called from a running event loop
```

**Solutions**:
```python
# Use pytest-asyncio
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None

# Or use asyncio.run() with new loop
def test_async_function():
    async def run_test():
        result = await async_function()
        assert result is not None
    
    asyncio.run(run_test())
```

## Performance Debugging

### Profiling Test Execution

#### Time Profiling
```powershell
# Profile individual test
python -m pytest tests/test_auth.py::test_slow_function --profile

# Profile with cProfile
python -m cProfile -o profile_output.prof -m pytest tests/test_auth.py
```

#### Memory Profiling
```powershell
# Install memory profiler
pip install memory-profiler

# Profile memory usage
python -m pytest tests/ --memory-profiler
```

### Identifying Bottlenecks

#### Test-Level Bottlenecks
```powershell
# Get detailed timing
python -m pytest tests/ --durations=0 --tb=no

# Focus on slowest tests
python -m pytest tests/ --durations=10 --tb=no | Select-String -Pattern "slowest"
```

#### Import-Level Bottlenecks
```python
# Time imports
import time
start = time.time()
import expensive_module
print(f"Import took {time.time() - start:.2f} seconds")
```

## Advanced Troubleshooting

### Debugging Test Isolation Issues

#### Find Shared State
```python
# Add to conftest.py
@pytest.fixture(autouse=True)
def debug_shared_state():
    # Print global state before test
    print(f"Global state: {globals()}")
    yield
    # Print global state after test
    print(f"Global state after: {globals()}")
```

#### Race Condition Detection
```powershell
# Run tests multiple times
for ($i = 1; $i -le 5; $i++) {
    Write-Host "Run $i"
    python -m pytest tests/test_problematic.py -n 2
}
```

### Debugging Mock Issues

#### Mock Call Verification
```python
# In test
mock_function.assert_called_once_with(expected_arg)
mock_function.assert_called()
print(f"Mock called with: {mock_function.call_args}")
```

#### Mock Return Value Debugging
```python
# Check mock return value
mock_function.return_value = expected_value
result = function_under_test()
print(f"Mock returned: {mock_function.return_value}")
print(f"Function returned: {result}")
```

### System-Level Debugging

#### Check System Resources
```powershell
# Check memory usage
Get-Process python | Select-Object CPU, WorkingSet

# Check disk space
Get-PSDrive C | Select-Object Used, Free

# Check CPU usage
Get-Counter "\Processor(_Total)\% Processor Time"
```

#### Check File System Issues
```powershell
# Check file locks
Get-Process | Where-Object {$_.ProcessName -eq "python"} | Select-Object Id, ProcessName, Path

# Check permissions
Test-Path -Path "tests/" -PathType Container
```

## Recovery Procedures

### Emergency Rollback
```powershell
# Rollback to working state
git checkout HEAD~1 -- tests/conftest.py
git checkout HEAD~1 -- pyproject.toml

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Full Test Environment Reset
```powershell
# Clean Python cache
Get-ChildItem -Path . -Recurse -Name "__pycache__" | Remove-Item -Recurse -Force

# Clean pytest cache
Remove-Item -Path ".pytest_cache" -Recurse -Force

# Reset virtual environment
deactivate
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Getting Additional Help

### Diagnostic Commands
```powershell
# Generate diagnostic report
python scripts/phase3_issue_resolution.py

# Check system info
python -c "import sys; print(sys.version); print(sys.executable)"

# Check pytest configuration
python -m pytest --collect-only | Select-String -Pattern "configuration"
```

### Support Resources
- Internal documentation
- Team knowledge base
- GitHub issues
- pytest documentation
- Stack Overflow (tag: pytest)

---

*This troubleshooting guide is maintained by the OneNote Copilot development team. Last updated: {datetime.now().strftime('%Y-%m-%d')}*
