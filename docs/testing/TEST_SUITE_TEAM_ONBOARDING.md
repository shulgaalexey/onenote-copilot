# OneNote Copilot Test Suite Team Onboarding Guide

## Welcome to the Optimized Test Suite!

This guide will help you quickly get up to speed with our optimized test suite and development workflow.

## Getting Started (10 Minutes)

### 1. Environment Setup
```powershell
# Clone repository
git clone <repository-url>
cd onenote-copilot

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Verify Installation
```powershell
# Test basic functionality
python -m pytest tests/ --version

# Run a quick test
python -m pytest tests/test_config.py -v
```

### 3. Load Test Commands
```powershell
# Load optimized test commands
. .\test-commands.ps1

# Verify commands are available
Get-Command Test-*
```

## Test Suite Overview

### Performance Improvements
- **Fast tests**: < 10 seconds for immediate feedback
- **Unit tests**: < 15 seconds for comprehensive validation
- **Full suite**: < 30 seconds (down from 98 seconds)
- **Parallel execution**: 4x faster on multi-core systems

### Test Categories
- **Functional**: auth, search, embedding, vector_store, cli, agent
- **Speed**: fast, slow, unit, integration
- **Optimization**: session_scoped, module_scoped, mock_heavy

## Daily Workflow

### Morning Routine (2 minutes)
```powershell
# Load test commands
. .\test-commands.ps1

# Run fast tests to ensure everything works
Test-Fast
```

### Development Cycle (30 seconds per cycle)
```powershell
# Make code changes
# Run relevant tests
Test-File src/auth/microsoft_auth.py

# Run specific test if needed
Test-Single tests/test_auth.py::TestMicrosoftAuth::test_token_refresh
```

### Pre-commit Routine (15 seconds)
```powershell
# Run pre-commit validation
Test-PreCommit

# Add coverage if needed
Test-Coverage-Fast
```

## Common Commands

### Quick Reference
```powershell
# Essential commands
Test-Fast              # Fast tests only (<10s)
Test-Unit              # Unit tests only (<15s)
Test-Auth              # Authentication tests
Test-Search            # Search functionality tests
Test-Coverage-Fast     # Fast tests with coverage

# Development commands
Test-File <filepath>   # Test specific file
Test-Single <test>     # Run single test
Test-Development       # Development workflow tests
```

### Advanced Usage
```powershell
# Run with timing
python -m pytest tests/ --durations=10

# Run in parallel
python -m pytest tests/ -n auto

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## Writing Tests

### Test Structure
```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.fast
@pytest.mark.unit
@pytest.mark.auth
class TestAuthComponent:
    """Test authentication component."""
    
    def test_basic_functionality(self, mock_settings):
        """Test basic auth functionality."""
        # Test implementation
        pass
    
    @pytest.mark.slow
    def test_integration_scenario(self):
        """Test full integration scenario."""
        # Longer test implementation
        pass
```

### Best Practices
- **Mark tests appropriately**: Use `@pytest.mark.fast` for quick tests
- **Use proper fixtures**: Leverage session and module scoped fixtures
- **Mock external dependencies**: Keep unit tests isolated
- **Write clear assertions**: Be specific about what you're testing

### Test Markers Guidelines
```python
# Mark fast tests (< 1 second)
@pytest.mark.fast
def test_quick_validation():
    pass

# Mark slow tests (> 1 second)
@pytest.mark.slow
def test_comprehensive_scenario():
    pass

# Mark unit tests (isolated)
@pytest.mark.unit
def test_isolated_function():
    pass

# Mark integration tests (with external systems)
@pytest.mark.integration
def test_with_external_api():
    pass
```

## Troubleshooting

### Common Issues

#### "Tests are running slowly"
```powershell
# Check if parallel execution is working
python -m pytest tests/ -n auto --durations=5

# Verify test markers
python -m pytest tests/ -m "fast" --collect-only
```

#### "Tests fail in parallel"
- Check for shared state between tests
- Verify proper fixture cleanup
- Ensure tests are properly isolated

#### "Mock errors"
- Verify patch paths match exact imports
- Check mock return value types
- Ensure all code paths are covered

### Getting Help
1. Check troubleshooting guide: `docs/TEST_SUITE_TROUBLESHOOTING.md`
2. Review best practices: `docs/TEST_SUITE_BEST_PRACTICES.md`
3. Ask team members in chat
4. Create issue with diagnostic information

## Development Workflow Examples

### Feature Development
```powershell
# 1. Start with failing test
Test-Single tests/test_new_feature.py::test_new_functionality

# 2. Implement feature
# Edit src/module.py

# 3. Run tests iteratively
Test-Fast  # Quick validation
Test-Unit  # More comprehensive

# 4. Before commit
Test-PreCommit
```

### Bug Fixing
```powershell
# 1. Reproduce bug with test
Test-Single tests/test_bug_scenario.py::test_bug_reproduction

# 2. Fix bug
# Edit src/module.py

# 3. Verify fix
Test-Single tests/test_bug_scenario.py::test_bug_reproduction
Test-Related  # Run related tests
```

### Code Review
```powershell
# Before reviewing
Test-Coverage-Fast  # Check coverage

# After review changes
Test-Fast  # Quick validation
Test-Unit  # Comprehensive check
```

## Advanced Features

### Custom Test Selection
```powershell
# Run tests by keyword
python -m pytest tests/ -k "auth and not slow"

# Run tests by marker combination
python -m pytest tests/ -m "fast and unit and auth"

# Run tests by file pattern
python -m pytest tests/test_auth*.py
```

### Performance Monitoring
```powershell
# Check performance trends
python -m pytest tests/ --durations=0 | Tee-Object -FilePath "performance.log"

# Monitor memory usage
python -m pytest tests/ --memory-profiler
```

### Test Data Management
```python
# Use module-scoped fixtures for shared data
@pytest.fixture(scope="module")
def sample_pages():
    return [create_page(i) for i in range(10)]

# Use session-scoped for expensive setup
@pytest.fixture(scope="session")
def auth_token():
    return generate_test_token()
```

## Team Collaboration

### Code Review Checklist
- [ ] New tests have appropriate markers
- [ ] Tests run in reasonable time
- [ ] Proper fixture usage
- [ ] No slow operations in fast tests
- [ ] Clear test descriptions

### Sharing Knowledge
- Weekly team sync on test optimization
- Monthly review of test performance
- Quarterly best practices update
- Document new patterns and solutions

## Useful Resources

### Documentation
- `docs/TEST_SUITE_BEST_PRACTICES.md` - Comprehensive best practices
- `docs/TEST_SUITE_TROUBLESHOOTING.md` - Troubleshooting guide
- `docs/COMPLETE_TEST_OPTIMIZATION_GUIDE.md` - Full optimization strategy

### Tools
- `test-commands.ps1` - Optimized test commands
- `scripts/phase3_*.py` - Validation and monitoring scripts
- Coverage reports in `htmlcov/`

### External Resources
- [pytest documentation](https://docs.pytest.org/)
- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/)
- [Python testing best practices](https://docs.python.org/3/library/unittest.html)

---

*Welcome to the team! This guide will help you become productive with our optimized test suite. Questions? Ask in team chat or create an issue.*

*Last updated: {datetime.now().strftime('%Y-%m-%d')}*
