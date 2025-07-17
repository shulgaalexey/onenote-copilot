# TEST_RUN.md Approach - Mandatory Testing Pattern

## 🚨 CRITICAL: Why This Approach Is Required

The `TEST_RUN.md` approach is **MANDATORY** for all pytest execution and ANY Python script execution that could take time to prevent Copilot Agent from prematurely jumping to the next command while code is still running. This is a common issue where the Agent loses patience during test startup and tries alternative approaches, which is completely inappropriate.

## 🚨 RECENT VIOLATION EXAMPLE - NEVER DO THIS AGAIN

**What I Did Wrong (July 16, 2025):**
1. Created ad-hoc test files (`test_query_fix.py`, `simple_test.py`)
2. Ran them directly in terminal: `python test_query_fix.py`
3. Lost patience when import seemed stuck
4. Didn't wait for completion markers
5. Abandoned proper testing approach

**Why This Was CRITICAL MISTAKE:**
- Violated mandatory testing protocol
- Could have missed important failures
- Didn't track execution properly
- Set bad precedent for future development

**What Should Have Been Done:**
```powershell
# Create test file if needed
# ... create test file ...

# ALWAYS run with TEST_RUN.md redirection
python test_query_fix.py > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"

# Monitor progress
Get-Content TEST_RUN.md -Tail 5

# Wait for completion marker
Select-String -Path TEST_RUN.md -Pattern "%TESTS FINISHED%"

# Only then proceed to next steps
```

**LESSON LEARNED**:
- NEVER create and run tests without TEST_RUN.md approach
- NEVER lose patience during test execution
- ALWAYS wait for completion markers
- ALWAYS follow the established protocol

## How to Recover from Violations

If you've already run tests incorrectly:
1. **STOP immediately** - don't proceed with next steps
2. **Re-run with proper TEST_RUN.md approach**
3. **Wait for completion marker**
4. **Document the violation** in PROGRESS.md or DEL_FILES.md
5. **Update instructions** to prevent future violations

## 🚫 ABSOLUTELY FORBIDDEN PATTERNS

**NEVER DO THESE THINGS:**
- Running tests directly in terminal: `python -m pytest tests/`
- Running Python scripts directly: `python test_something.py`
- Creating ad-hoc test files and running them without TEST_RUN.md
- Using sleep/timeout commands to "wait" for tests
- Proceeding to next steps without seeing `%TESTS FINISHED%` marker
- Abandoning test sessions because there's no immediate output

**THESE VIOLATIONS WILL CAUSE PROJECT FAILURES!**

## Required Command Pattern

**ALWAYS use this exact PowerShell command for running tests:**

```powershell
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

**For ANY Python script execution that could take time:**

```powershell
python your_script.py > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

## Essential Rules

1. **NEVER run pytest without TEST_RUN.md redirection**
2. **NEVER run any Python script without TEST_RUN.md if it could take more than 5 seconds**
3. **ALWAYS wait for the `%TESTS FINISHED%` marker** before proceeding to any next step
4. **MONITOR TEST_RUN.md contents** to track progress in real-time
5. **NEVER abandon test sessions** even if there's initial delay or no immediate output
6. **MAXIMUM wait time: 5 minutes** - if execution doesn't complete, investigate but don't give up
7. **DELETE temporary test files** only after using TEST_RUN.md approach

## How It Works

### The Process
1. **Command executes**: pytest starts running and outputs to `TEST_RUN.md`
2. **Progress tracking**: Test output gets written to the file as tests run
3. **Completion marker**: When all tests finish, `%TESTS FINISHED%` is appended
4. **Verification**: Agent checks for this marker to confirm completion
5. **Analysis**: Only after seeing the marker, review test results

### What Gets Captured
- All test output (stdout and stderr)
- Test progress indicators
- Failure details and tracebacks
- Coverage reports
- Final test summary
- Completion marker (`%TESTS FINISHED%`)

## Monitoring TEST_RUN.md

### Check Current Progress
```powershell
# View last 10 lines to see current status
Get-Content TEST_RUN.md -Tail 10

# View entire file contents
Get-Content TEST_RUN.md

# Check if tests are finished
Select-String -Path TEST_RUN.md -Pattern "%TESTS FINISHED%"
```

### Understanding the Output
- **Test collection**: Initial phase where pytest discovers tests
- **Test execution**: Individual test results with PASSED/FAILED/SKIPPED
- **Coverage report**: Coverage percentages and missing lines
- **Summary**: Final count of passed/failed/skipped tests
- **Completion marker**: `%TESTS FINISHED%` indicates all done

## Common Scenarios

### Normal Test Run
```
========================= test session starts =========================
platform win32 -- Python 3.11.0, pytest-8.4.1, pluggy-1.5.0
cachedir: .pytest_cache
rootdir: C:\src\onenote-copilot
configfile: pyproject.toml
plugins: cov-6.0.0, asyncio-0.24.0
collected 25 items

tests\test_auth.py::test_microsoft_auth PASSED                 [  4%]
tests\test_cli_interface.py::test_welcome_message PASSED      [  8%]
...
========================== 25 passed in 45.23s ==========================
%TESTS FINISHED%
```

### Test Run with Failures
```
========================= test session starts =========================
...
tests\test_onenote_agent.py::test_query_processing FAILED     [ 80%]

=========================== FAILURES ===========================
_____________ test_query_processing _____________
...detailed failure traceback...

======================== 1 failed, 24 passed in 52.10s ========================
%TESTS FINISHED%
```

### Long Running Tests
```
========================= test session starts =========================
platform win32 -- Python 3.11.0, pytest-8.4.1, pluggy-1.5.0
...
tests\test_integration.py::test_full_workflow PASSED          [ 96%]
(Tests can take 30-120 seconds - be patient!)
```

## Troubleshooting

### If Tests Seem Stuck
1. **Check TEST_RUN.md**: Look for any progress indicators
2. **Be patient**: Tests often have slow startup, especially on first run
3. **Wait for marker**: Don't proceed until `%TESTS FINISHED%` appears
4. **Check timing**: Allow up to 5 minutes for completion

### If Tests Take Too Long
```powershell
# Run individual test files
python -m pytest tests/test_specific_file.py -v > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"

# Run only fast tests (if marked)
python -m pytest -m "not slow" tests/ -v > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

### If Tests Fail
1. **Review TEST_RUN.md**: Examine failure details and tracebacks
2. **Fix issues**: Address the specific problems identified
3. **Re-run with same pattern**: Use TEST_RUN.md approach again
4. **Iterate**: Repeat until all tests pass

## Examples of Proper Usage

### Basic Test Run
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run tests with TEST_RUN.md tracking
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"

# Wait and monitor
Get-Content TEST_RUN.md -Tail 10
# Look for "%TESTS FINISHED%" before proceeding
```

### Coverage-Only Run
```powershell
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

### Verbose Debugging Run
```powershell
python -m pytest tests/ -v -s --tb=long > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

## Integration with Development Workflow

### Pre-Commit Checks
```powershell
# Quality checks before commit
ruff check --fix; mypy .; python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

### CI/CD Pipeline
All automated testing should also use this pattern to ensure consistent behavior between local development and CI environments.

### PRP Validation
When executing PRPs, the validation phase must use TEST_RUN.md approach to ensure all tests complete before marking the PRP as successfully implemented.

## Summary

The TEST_RUN.md approach is **not optional** - it's a critical part of the development workflow that ensures:

- ✅ Tests complete before next actions
- ✅ Full test output is captured for analysis
- ✅ Agent doesn't prematurely abort test sessions
- ✅ Clear completion indicators
- ✅ Comprehensive debugging information

**Always use this pattern. Never skip it. Never run pytest without it.**
