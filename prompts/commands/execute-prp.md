# Execute BASE PRP

Implement a feature using using the PRP file.

## PRP File: $ARGUMENTS

## Execution Process

1. **Load PRP**
   - Read the specified PRP file
   - Understand all context and requirements
   - Follow all instructions in the PRP and extend the research if needed
   - Ensure you have all needed context to implement the PRP fully
   - Do more web searches and codebase exploration as needed

2. **ULTRATHINK**
   - Think hard before you execute the plan. Create a comprehensive plan addressing all requirements.
   - Break down complex tasks into smaller, manageable steps using your todos tools.
   - Use the TodoWrite tool to create and track your implementation plan.
   - Identify implementation patterns from existing code to follow.

3. **Execute the plan**
   - Execute the PRP using GitHub Copilot and its agent mode when appropriate
   - Use #github-pull-request_copilot-coding-agent for complex implementations
   - Implement all the code following Windows/PowerShell best practices

4. **Validate**
   - **MANDATORY**: Use TEST_RUN.md approach for all test execution
   - Run validation command: `python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"`
   - **WAIT** for `%TESTS FINISHED%` marker before proceeding
   - Monitor `TEST_RUN.md` contents to track test progress
   - Fix any failures shown in TEST_RUN.md
   - Re-run tests using same TEST_RUN.md approach until all pass
   - Never skip the TEST_RUN.md pattern - it prevents premature command execution

5. **Complete**
   - Ensure all checklist items done
   - Run final validation suite
   - Report completion status
   - Read the PRP again to ensure you have implemented everything

6. **Reference the PRP**
   - You can always reference the PRP again if needed

Note: If validation fails, use error patterns in PRP to fix and retry.