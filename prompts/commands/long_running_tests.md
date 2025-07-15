**When running unit tests, always wait for the entire test suite to complete before analyzing the results or proceeding. Do not interrupt or abandon test sessions prematurely, even if there is a delay in initial output.**
- **IMPORTANT**: When running tests in the terminal, don't rush and allow tests to run and finish. Tests always take long time to run.
- **WHEN TESTS TAKE TOO LONG**: just run them one by one.

Our Python unit tests typically take between 30 and 120 seconds to run. Be patient during this period and do not assume a failure if output is delayed.

A test run is considered successful only if the terminal command returns an exit code of 0, indicating all tests passed. If the exit code is non-zero or failures are reported, initiate a thorough debugging cycle." This leverages the standardized pytest exit codes where 0 signifies success, 1 indicates failures, and other codes denote interruptions or errors.

After running tests, thoroughly analyze the terminal output. Prioritize the final summary lines and the command's exit code. If the output is extensive, focus on identifying key success/failure indicators and detailed error messages, rather than parsing every line.

If tests fail (non-zero exit code), first review the traceback and failure summaries. Propose a fix and re-run tests. Only consider alternative test methods if the primary method consistently fails after multiple attempts.