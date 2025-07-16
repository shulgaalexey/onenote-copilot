# Long Running Tests - MANDATORY TEST_RUN.md Approach

## 🚨 CRITICAL: Use TEST_RUN.md for ALL Test Execution

**MANDATORY TESTING APPROACH - NEVER SKIP THIS**:

### Required Test Execution Pattern
Always use this exact PowerShell command for running tests:
```powershell
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

### Essential Rules
1. **ALWAYS redirect pytest output to `TEST_RUN.md`** - this file tracks test progress
2. **WAIT for the `%TESTS FINISHED%` marker** before proceeding to any next step
3. **NEVER abandon test sessions** even if there's initial delay or no immediate output
4. **Maximum wait time: 5 minutes** - if tests don't complete, investigate but don't give up
5. **Monitor `TEST_RUN.md` file contents** to track test progress in real-time

### Why This Approach Is Critical
- **Prevents premature action**: Agent won't jump to next command while tests are still running
- **Provides visibility**: Can see test progress and output as it happens
- **Ensures completion**: Clear marker indicates when all tests have finished
- **Debugging aid**: Full test output captured for analysis if tests fail

### Test Execution Workflow
1. **Run the command**: Use the exact PowerShell command above
2. **Monitor TEST_RUN.md**: Check file contents periodically to see progress
3. **Wait for marker**: Look for `%TESTS FINISHED%` at the end of the file
4. **Analyze results**: Only after seeing the marker, review test outcomes
5. **Take action**: Fix failures or proceed based on results

### Common Test Timing
- **Unit tests**: 30-120 seconds typically
- **Integration tests**: May take 2-5 minutes
- **Full test suite**: Allow up to 5 minutes for completion

### If Tests Take Too Long
- **First**: Be patient, tests often have slow startup
- **Second**: Check `TEST_RUN.md` for any progress indicators
- **Third**: If over 5 minutes with no marker, investigate the issue
- **Last resort**: Run tests individually to isolate problems

### Troubleshooting Long Tests
```powershell
# If tests seem stuck, check what's in TEST_RUN.md
Get-Content TEST_RUN.md -Tail 10

# Run tests one file at a time if needed
python -m pytest tests/test_specific_file.py -v > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

## Legacy Content (Updated)

**When running unit tests, always wait for the entire test suite to complete before analyzing the results or proceeding. Do not interrupt or abandon test sessions prematurely, even if there is a delay in initial output.**

- **IMPORTANT**: When running tests in the terminal, don't rush and allow tests to run and finish. Tests always take long time to run.
- **WHEN TESTS TAKE TOO LONG**: Use the TEST_RUN.md approach and run them one by one if needed.

Our Python unit tests typically take between 30 and 120 seconds to run. Be patient during this period and do not assume a failure if output is delayed.

A test run is considered successful only if:
1. The `%TESTS FINISHED%` marker appears in `TEST_RUN.md`
2. The terminal command returns an exit code of 0
3. No test failures are reported in the output

If tests fail (non-zero exit code), first review the traceback and failure summaries in `TEST_RUN.md`. Propose a fix and re-run tests using the same TEST_RUN.md approach. Only consider alternative test methods if the primary method consistently fails after multiple attempts.