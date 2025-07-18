# OneNote Copilot Test Suite Best Practices Guide

## Overview
This guide provides comprehensive best practices for working with the optimized OneNote Copilot test suite. Following these practices ensures optimal performance, reliability, and maintainability.

## Quick Start

### Daily Development Workflow
```powershell
# Load test commands
. .\test-commands.ps1

# Run fast tests for immediate feedback (<10s)
Test-Fast

# Run tests for specific module you're working on
Test-File src/auth/microsoft_auth.py

# Run single test for focused debugging
Test-Single tests/test_auth.py::TestMicrosoftAuth::test_successful_auth
```

### Pre-commit Workflow
```powershell
# Run pre-commit validation (<15s)
Test-PreCommit

# Run with coverage if needed
Test-Coverage-Fast
```

## Test Categories and Markers

### Functional Categories
- `@pytest.mark.auth` - Authentication-related tests
- `@pytest.mark.search` - Search functionality tests
- `@pytest.mark.embedding` - Embedding generation tests
- `@pytest.mark.vector_store` - Vector storage tests
- `@pytest.mark.cli` - Command-line interface tests
- `@pytest.mark.agent` - AI agent functionality tests

### Performance Categories
- `@pytest.mark.fast` - Tests that run in <1 second
- `@pytest.mark.slow` - Tests that may take longer (for CI/CD)
- `@pytest.mark.unit` - Unit tests (isolated, no external dependencies)
- `@pytest.mark.integration` - Integration tests (with external systems)

### Optimization Categories
- `@pytest.mark.session_scoped` - Tests using session-scoped fixtures
- `@pytest.mark.module_scoped` - Tests using module-scoped fixtures
- `@pytest.mark.mock_heavy` - Tests with heavy mocking

## Fixture Usage Guidelines

### Session-Scoped Fixtures
Use for expensive operations that can be shared across the entire test session:
```python
@pytest.fixture(scope="session")
def session_auth_setup():
    """One-time authentication setup for entire session."""
    # Expensive setup
    return auth_data
```

### Module-Scoped Fixtures
Use for data that can be shared across tests in a single module:
```python
@pytest.fixture(scope="module")
def module_settings():
    """Settings configuration shared per module."""
    return settings
```

### Function-Scoped Fixtures
Use for test-specific data that requires isolation:
```python
@pytest.fixture
def temp_file():
    """Temporary file for individual test."""
    with tempfile.NamedTemporaryFile() as f:
        yield f.name
```

## Performance Optimization Techniques

### 1. Test Marking Strategy
```python
# Mark tests appropriately
@pytest.mark.fast
@pytest.mark.unit
@pytest.mark.auth
def test_quick_auth_validation():
    pass

@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.auth
def test_full_auth_flow():
    pass
```

### 2. Mocking Heavy Dependencies
```python
# Mock expensive imports
@pytest.fixture(autouse=True)
def mock_heavy_imports():
    with patch('openai.OpenAI') as mock_openai:
        mock_openai.return_value.embeddings.create.return_value = mock_embedding_response
        yield
```

### 3. Parallel Execution
```powershell
# Run tests in parallel
python -m pytest tests/ -n auto

# Run specific category in parallel
python -m pytest tests/ -m "fast and unit" -n 2
```

## Common Patterns and Anti-Patterns

### Good Practices

#### Proper Test Isolation
```python
@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state between tests."""
    # Clear any global state
    yield
    # Cleanup after test
```

#### Efficient Mocking
```python
# Mock at the right level
@patch('src.module.expensive_function')
def test_feature(mock_expensive):
    mock_expensive.return_value = "expected_result"
    # Test logic
```

#### Appropriate Assertions
```python
# Use specific assertions
assert result.status == "success"
assert len(result.items) == 3
assert result.duration < 1.0
```

### Anti-Patterns

#### Avoid Global State
```python
# DON'T DO THIS
global_test_data = {}

def test_something():
    global_test_data['key'] = 'value'  # Affects other tests
```

#### Don't Over-Mock
```python
# DON'T DO THIS
@patch('module.function1')
@patch('module.function2')
@patch('module.function3')
@patch('module.function4')
def test_something(mock4, mock3, mock2, mock1):
    # Too many mocks - consider testing at higher level
```

#### Avoid Slow Operations in Fast Tests
```python
# DON'T DO THIS
@pytest.mark.fast
def test_something():
    time.sleep(5)  # This makes the test slow!
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Tests Running Slowly
**Symptoms**: Tests taking longer than expected
**Solutions**:
- Check test markers: `python -m pytest tests/ --markers`
- Run with timing: `python -m pytest tests/ --durations=10`
- Verify parallel execution: `python -m pytest tests/ -n auto`

#### 2. Test Isolation Issues
**Symptoms**: Tests fail when run together but pass individually
**Solutions**:
- Check for shared state
- Verify fixture cleanup
- Use proper mocking scope

#### 3. Mock-Related Failures
**Symptoms**: Tests fail after optimization with mocks
**Solutions**:
- Verify mock patch paths
- Check return value types
- Ensure all code paths are mocked

#### 4. Coverage Issues
**Symptoms**: Coverage drops after optimization
**Solutions**:
- Run coverage report: `pytest --cov=src --cov-report=html`
- Check for uncovered branches
- Verify test selection includes all necessary paths

### Debugging Commands

```powershell
# Check test collection
python -m pytest tests/ --collect-only

# Run with verbose output
python -m pytest tests/ -v

# Run single test with debugging
python -m pytest tests/test_auth.py::test_function -s -v

# Check which tests are selected by markers
python -m pytest tests/ -m "fast" --collect-only
```

## Performance Monitoring

### Regular Performance Checks
```powershell
# Weekly performance validation
python -m pytest tests/ --durations=0 | Tee-Object -FilePath "performance-$(Get-Date -Format 'yyyy-MM-dd').log"

# Coverage verification
python -m pytest tests/ --cov=src --cov-report=html
```

### Performance Thresholds
- Fast tests: < 10 seconds
- Unit tests: < 15 seconds  
- Full test suite: < 30 seconds
- Test collection: < 2 seconds

## Team Collaboration

### Code Review Guidelines
- Verify new tests have appropriate markers
- Check for proper fixture usage
- Ensure no slow operations in fast tests
- Validate mock usage is appropriate

### CI/CD Integration
```yaml
# Example GitHub Actions workflow
- name: Run Fast Tests
  run: python -m pytest tests/ -m "fast and unit" --tb=short

- name: Run Full Test Suite
  run: python -m pytest tests/ --cov=src --cov-report=xml
```

### Knowledge Sharing
- Regular team sessions on test optimization
- Documentation updates for new patterns
- Performance metrics tracking
- Best practice reinforcement

## Advanced Usage

### Custom Test Commands
Create custom commands for specific workflows:
```powershell
function Test-MyFeature {
    param($FeatureName)
    python -m pytest tests/ -k $FeatureName -v
}
```

### Performance Profiling
```powershell
# Profile test execution
python -m pytest tests/ --profile

# Memory profiling
python -m pytest tests/ --memory-profiler
```

### Test Data Management
```python
# Efficient test data creation
@pytest.fixture(scope="module")
def sample_data():
    return {
        "pages": [create_sample_page(i) for i in range(10)],
        "users": [create_sample_user(i) for i in range(5)]
    }
```

## Maintenance and Updates

### Regular Maintenance Tasks
- Weekly performance monitoring
- Monthly test optimization review
- Quarterly best practices updates
- Annual full test suite audit

### Updating Test Optimizations
1. Monitor performance metrics
2. Identify new bottlenecks
3. Apply optimization techniques
4. Validate improvements
5. Update documentation

## Getting Help

### Internal Resources
- Test optimization documentation
- Performance monitoring dashboards
- Team knowledge base
- Code review feedback

### External Resources
- pytest documentation
- pytest-xdist documentation
- Python testing best practices
- Performance testing guides

---

*This guide is maintained by the OneNote Copilot development team. Last updated: {datetime.now().strftime('%Y-%m-%d')}*
