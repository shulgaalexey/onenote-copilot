### 🔄 Project Awareness & Context
- **START EACH STEP BY WRITING IN `PROGRESS.md`** to track your progress and decisions.
- **Add link to the current PRP file** in `PROGRESS.md` to maintain context.
- **Always read `PROGRESS.md` or `PLANNING.md`** or the appropriate PRP file at the start of a new conversation to understand the project's architecture, goals, style, and constraints.
- **Check `TASK.md` or the current PRP file** before starting a new task. If the task isn't listed, add it with a brief description and today's date.
- **Use consistent naming conventions, file structure, and architecture patterns** as described in `PLANNING.md` or PRP.
- **Use the virtual environment** whenever executing Python commands, including for unit tests. On Windows, activate with `.\.venv\Scripts\Activate.ps1` in PowerShell.
- **Store all prompts in `./prompts/` folder** - this is the central location for all prompts, PRPs, examples, and command templates. Exception: copilot-instructions.md stays in `./.github/` folder.

### 🖥️ Windows/PowerShell Environment
- **Environment**: Windows 11 with PowerShell 7
- **Editor**: VS Code with GitHub Copilot
- **Package Manager**: pip for reliable dependency management
- **Command Chaining**: Use `;` instead of `&&` for multiple commands in PowerShell
- **Path Separators**: Use forward slashes `/` in Python code, backslashes `\` only in PowerShell paths
- **Virtual Environment**: Always use `.\.venv\Scripts\Activate.ps1` for activation
- **pip over uv**: Use `pip` for package management, not `uv`. It provides better compatibility and is the standard Python package manager.

### 🤖 GitHub Copilot Integration
- **Leverage Copilot Chat**: For architectural discussions and complex problem solving
- **Use Agent Mode**: `#github-pull-request_copilot-coding-agent` for feature implementation
- **Inline Suggestions**: Accept for boilerplate code, review for business logic
- **Code Reviews**: Use Copilot to review and suggest improvements

### 📋 PRP (Project Request Proposal) Workflow
All PRPs and templates are stored in `./prompts/` folder:
1. **Generate PRP**: Use `prompts/commands/generate-prp.md` template
2. **Research**: Include comprehensive context and external references
3. **Plan**: Break down into tasks with clear validation gates
4. **Execute**: Use `prompts/commands/execute-prp.md` for implementation
5. **Validate**: Run all quality checks before completion
6. **Store**: Save all PRPs in `prompts/PRPs/` directory

### 🔧 Essential Commands (PowerShell)
```powershell
# Virtual Environment
.\.venv\Scripts\Activate.ps1                # Activate virtual environment
deactivate                                 # Deactivate virtual environment

# Development
pip install -r requirements.txt             # Install dependencies
pip install package-name                    # Add new dependency
pip freeze > requirements.txt               # Update requirements after adding packages

# Quality Checks
ruff check --fix; mypy .                    # Lint and type check

# Development - Standard Testing
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"  # Run tests with TEST_RUN.md tracking
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"  # Tests with coverage and HTML report

# Development - Optimized Testing (26% faster startup)
python -m pytest tests/ --noconftest --no-cov -q -x > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"  # Lightning-fast testing for TDD
python -m pytest tests/ --cov=src --cov-report=term-missing -q > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"  # Fast coverage reporting

# Performance Testing
python -m pytest tests/ --collect-only -q > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"  # Benchmark startup performance

# Application
python -m src.main                          # Run main application (future)
```

### 🧱 Code Structure & Modularity
- **Never create a file longer than 500 lines of code.** If a file approaches this limit, refactor by splitting it into modules or helper files.
- **Organize code into clearly separated modules**, grouped by feature or responsibility.
  For agents this looks like:
    - `agent.py` - Main agent definition and execution logic
    - `tools.py` - Tool functions used by the agent
    - `prompts.py` - System prompts (store actual prompts in `./prompts/` folder)
- **Use clear, consistent imports** (prefer relative imports within packages).
- **Use python_dotenv and load_dotenv()** for environment variables.

When you need to do a refactoring, use the `prompts/commands/refactor.md` template.

### 🧪 Testing & Reliability
- **Always create Pytest unit tests for new features** (functions, classes, routes, etc).
- **After updating any logic**, check whether existing unit tests need to be updated. If so, do it.
- **Tests should live in a `/tests` folder** mirroring the main app structure.
- **Coverage**: Minimum 80% code coverage required
- **Types**: Include unit tests, integration tests, and end-to-end tests
- **Pattern**: Each feature needs happy path, edge case, and failure tests


### 📝 Test Output Tracking
**🚨 MANDATORY TESTING APPROACH - NEVER SKIP THIS**:
- **ALWAYS use `TEST_RUN.md` for ANY test execution** - this includes unit tests, integration tests, debugging tests, ad-hoc tests, or ANY Python script execution that could take time
- **NEVER run tests directly in terminal without output redirection** - this leads to incomplete execution tracking
- **When running tests, save the output in a `TEST_RUN.md` file** at the project root (ensure each trace line is started with the current timestamp).
- **Overwrite this file on each test run** - it's a temporary tracking file.
- **When tests finish, append the line `%TESTS FINISHED%`** to mark completion.
- **Monitor this file and never proceed to the next step** until you see this marker.
- **Maximum wait time: 5 minutes** - if tests don't complete within this timeframe, investigate or abort.
- **Use this approach for ALL test runs** to ensure proper completion tracking.
- **NO EXCEPTIONS**: Even simple Python scripts, import tests, or debugging code MUST use this approach if they could take more than a few seconds

<!--  ── Test execution rules ───────────────────────────────────────── -->

### 🏃‍♂️ VS Code Task-Based Test Execution
**When I ask to "run tests", follow these rules:**
- **ALWAYS** invoke the VS Code task **"pytest (all)"** instead of typing `pytest` in the terminal when you need to run all or large number of tests
- **Wait until that task TERMINATES** (VS Code Tasks API "terminated" event) before you continue with any other action
- **If the task fails**, surface the full task output in chat so I can diagnose it
- **Never start a second long-running task or terminal command** until the current task has finished
- This ensures proper task lifecycle management and prevents resource conflicts

### 🚀 Optimized Test Commands for Different Scenarios:

#### Ultra-Fast Testing (Lightning Mode - 4.3s startup):
```powershell
# For rapid TDD cycles - bypasses heavy conftest imports
python -m pytest tests/ --noconftest --no-cov -q -x > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

#### Fast Coverage Testing:
```powershell
# Optimized coverage reporting - faster than full coverage
python -m pytest tests/ --cov=src --cov-report=term-missing -q > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

#### Full Test Suite with Coverage:
```powershell
# Complete test suite with HTML coverage report
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

#### Performance Benchmarking:
```powershell
# Monitor pytest startup performance
python -m pytest tests/ --collect-only -q > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

### 🕐 Long-Running Test Management:
- **Long-running tests** (>30 seconds) should use the standard TEST_RUN.md approach
- **Network timeout tests** can take 8+ seconds each - use optimized versions for development
- **Embedding generation tests** can take 8+ seconds - use pre-computed fixtures for speed
- **Agent initialization tests** can take 3+ seconds - use proper mocking for faster execution
- **For development**: Use `--noconftest` flag to skip heavy imports and reduce startup time by 26%
- **For CI/CD**: Use full test suite with coverage for comprehensive validation

Example PowerShell command for test tracking:
```powershell
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

**CRITICAL EXAMPLES OF WHAT REQUIRES TEST_RUN.md**:
- `python -m pytest` (any pytest command)
- `python test_something.py` (any test script)
- `python -c "import complex_module; complex_module.test()"` (any import or code execution)
- `python app.py` (any application startup)
- `python -m src.main` (any module execution)

**WHY THIS IS CRITICAL**: This prevents Copilot Agent from jumping to the next command before tests finish. Tests often take time to start up, and the Agent must be patient and wait for the completion marker rather than abandoning the test session.

Use the `TEST_RUN.md` file content to fix failing tests if any.

**ABSOLUTELY FORBIDDEN**:
- Running tests directly in terminal without `> TEST_RUN.md 2>&1`
- Using `sleep` or `timeout` commands to wait for tests
- Creating ad-hoc test files and running them without TEST_RUN.md tracking
- Proceeding to next steps without seeing `%TESTS FINISHED%` marker

Also when running the app in the terminal. **IT TAKES TIME TO START THE APP!!!**

**📚 PYTEST STARTUP OPTIMIZATION & TESTING BEST PRACTICES**:
- **ALL developers (humans and AI assistants) MUST follow the testing best practices documented in `./docs/PYTEST_STARTUP_OPTIMIZATION.md`**
- **MANDATORY reading**: `./docs/PYTEST_STARTUP_OPTIMIZATION.md` - contains complete pytest startup optimization guide and testing workflows
- **Key optimization strategies**: 26% faster pytest startup through `--noconftest` and `--no-cov` flags
- **Available optimized commands**:
  - `Test-Lightning` - Ultra-fast testing (4.3s startup)
  - `Test-Coverage-Fast` - Optimized coverage reporting
  - `Test-StartupBenchmark` - Performance monitoring
- **Development workflow**: Use `Test-Lightning` for rapid TDD cycles, `Test-Coverage-Fast` for comprehensive validation

**🔥 TESTING COMPLIANCE REQUIREMENTS**:
- **BEFORE ANY CODE CHANGES**: Review relevant sections in `./docs/PYTEST_STARTUP_OPTIMIZATION.md`
- **AFTER ANY CODE CHANGES**: Run tests using the optimized test patterns documented in the optimization guide
- **FOR PERFORMANCE ISSUES**: Use `Test-StartupBenchmark` to monitor pytest startup performance
- **FOR NEW FEATURES**: Follow TDD patterns with optimized test commands for faster feedback
- **NO EXCEPTIONS**: These practices apply to ALL code development in this repository


### ✅ Task Completion
- **Mark completed tasks in `TASK.md`** immediately after finishing them.
- Add new sub-tasks or TODOs discovered during development to `TASK.md` under a "Discovered During Work" section.


### Deleting temporary files
- **Delete temporary files** that you created during troubleshooting
- **Do not delete files** that are part of the project structure or used by other components
- **WHEN DELETED**: Add a note in `DEL.md` and `PROGRESS.md` stating what was deleted and why

### 🎨 Style & Conventions
- **Use Python** as the primary language (3.11+).
- **Follow PEP8**, use type hints, and format with `ruff` and `mypy`.
- **Use `pydantic` for data validation** and LangGraph for agent development.
- **Functions**: All new functions must have Google-style docstrings and type hints
- **Classes**: PascalCase naming, prefer composition over inheritance
- **Async**: Use async/await patterns for all agent operations
- **Type Safety**: Use Pydantic models for all data validation
- Write **docstrings for every function** using the Google style:
  ```python
  def example():
      """
      Brief summary.

      Args:
          param1 (type): Description.

      Returns:
          type: Description.
      """
  ```

### 🤖 AI Agent Development Guidelines
- **Async First**: All agent operations must be asynchronous
- **Tool Pattern**: Use tools for external interactions, avoid direct API calls in agents
- **Context Management**: Properly handle conversation context and state
- **Error Handling**: Implement graceful error handling and recovery
- **Validation**: Use Pydantic models for all inputs and outputs

### 🖥️ Chat CLI Development Guidelines
- **Async Operations**: Use Python's `asyncio` for all asynchronous operations, including API calls and user input handling
- **Rich UI Library**: Integrate the `rich` library for enhanced command-line formatting:
  - Use `rich.panel.Panel` for bordered content sections
  - Use `rich.markdown.Markdown` for formatted text rendering
  - Use `rich.live.Live` for real-time updates and streaming responses
  - Use `rich.console.Console` for consistent output formatting
- **Chat Commands**: Implement standardized chat commands with `/` prefix:
  - `/help` - Display available commands and usage instructions
  - `/reset` - Clear current conversation and start fresh
  - `/history` - Show conversation history with timestamps
  - `/session` - Display current session information and statistics
  - `/starters` - Show conversation starter suggestions
  - `/quit` or `/exit` - Gracefully terminate the application
- **Welcome Experience**: Create rich-styled welcome messages:
  - Use headers and panels to introduce the application
  - Display available commands and features clearly
  - Include version information and basic usage tips
- **Live Display**: Implement dynamic response streaming:
  - Use `rich.live.Live` for real-time content updates
  - Show typing indicators during API calls
  - Stream responses character-by-character for natural feel
- **Session Management**: Track and manage conversation state:
  - Maintain conversation history with metadata
  - Implement session reset functionality
  - Provide session statistics (message count, duration, etc.)
  - Save/load session data for persistence
- **Error Handling**: Handle common CLI interruptions gracefully:
  - Catch `KeyboardInterrupt` (Ctrl+C) for clean shutdown
  - Handle `EOFError` for input stream termination
  - Provide user-friendly error messages with recovery suggestions
  - Implement fallback mechanisms for API failures

### 🚫 Do Not Touch
- **Legacy Code**: Don't modify working implementations without explicit requirements
- **Generated Files**: Don't manually edit auto-generated configuration files
- **External Dependencies**: Don't modify external library code directly
- **Git History**: Don't rewrite commit history on shared branches

### 🗂️ File Deletion Tracking
**🚨 CRITICAL PRACTICE - NEVER SKIP THIS STEP 🚨**

Before deleting ANY file in the repository:
1. **MANDATORY**: Add the file to `DEL_FILES.md` with deletion details
2. **Include**: Full file path, reason for deletion, date, and context
3. **Template**: Follow the template provided in `DEL_FILES.md`
4. **Purpose**: Maintain project history and enable recovery if needed

**Example entry format:**
```markdown
**File Path**: `tests/test_example.py`
- **Reason**: Failing tests due to outdated mocking approach
- **Context**: Replaced with simpler test implementation
- **Deleted by**: [Your name/Agent]
- **Date**: YYYY-MM-DD
```

**Why this matters:**
- Provides audit trail for deleted files
- Helps understand project evolution
- Enables recovery of accidentally deleted files
- Documents decision-making process
- Prevents confusion about missing files

**NEVER delete a file without logging it in DEL_FILES.md first!**

### 🔧 Environment Variables
- **Development**: Use `.env.local` file (gitignored)
- **Documentation**: Update `.env.example` when adding new variables
- **Loading**: Always use `python-dotenv` for environment variable loading
- **Validation**: Validate required environment variables on application startup

### ✅ Quality Gates
Before any commit or pull request:
```powershell
# Must pass all of these checks
ruff check --fix                            # Code formatting and linting
mypy .                                       # Type checking
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"  # Testing with coverage using TEST_RUN.md approach
```

### 📚 Documentation & Explainability
- **Update `README.md`** when new features are added, dependencies change, or setup steps are modified.
- **Comment non-obvious code** and ensure everything is understandable to a mid-level developer.
- When writing complex logic, **add an inline `# Reason:` comment** explaining the why, not just the what.
- **Keep inline documentation focused on 'why' not 'what'**

### 🔧 Troubleshooting
- **Virtual Environment Issues**: Ensure PowerShell execution policy allows script execution. Use `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` if needed
- **Package Management Issues**: Use `pip` for reliable dependency management. Clear pip cache with `pip cache purge` if installation issues occur
- **Testing Issues**: Use TEST_RUN.md approach for verbose output: `python -m pytest tests/ -v > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"`. Use `--pdb` flag to drop into debugger on test failures

### 🧠 AI Behavior Rules
- **Never assume missing context. Ask questions if uncertain.**
- **Never hallucinate libraries or functions** – only use known, verified Python packages.
- **Always confirm file paths and module names** exist before referencing them in code or tests.
- **Never delete or overwrite existing code** unless explicitly instructed to or if part of a task from `TASK.md`.
- **Use structured exceptions with clear error messages for error handling**
- **Use structured logging with appropriate levels**
- **Use Pydantic Settings for configuration management**

### 🎯 Project Goals & Common Patterns
- Build production-ready AI agents for social interactions
- Demonstrate modern Python development practices on Windows
- Showcase effective GitHub Copilot integration patterns
- Create reusable patterns for future AI agent projects
- **Packaging**: Use modern Python packaging with `pyproject.toml`
- **Dependencies**: Pin exact versions for reproducible builds
- **Scripts**: All deployment scripts must be PowerShell compatible

**🚨 LEARN FROM RECENT VIOLATIONS 🚨**

**Case Study - July 16, 2025**: During query processing fix, the Agent created ad-hoc test files (`test_query_fix.py`, `simple_test.py`) and ran them directly in terminal without TEST_RUN.md redirection. This violated the mandatory testing protocol and could have led to missed failures or incomplete execution tracking.

**What was done wrong:**
- Created temporary test files without proper execution tracking
- Ran `python test_query_fix.py` directly in terminal
- Lost patience when import seemed stuck and abandoned proper approach
- Proceeded to next steps without completion confirmation

**Why this was dangerous:**
- Could miss critical test failures
- No execution tracking or debugging information
- Sets bad precedent for future development
- Violates established project protocols

**Correct approach for ANY Python execution:**
```powershell
# Even for simple scripts - ALWAYS use TEST_RUN.md
python test_query_fix.py > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"

# Monitor progress
Get-Content TEST_RUN.md -Tail 5

# Wait for completion
Select-String -Path TEST_RUN.md -Pattern "%TESTS FINISHED%"
```

**NEVER AGAIN**: Any Python script execution that could take time MUST use TEST_RUN.md approach.