WARNING: This is updated for the OneNote Copilot project.
Based on the previous structure but updated for LangGraph and pip.

# OneNote Copilot - Project Planning

## Project Overview
AI Agent system for enhanced OneNote interactions and productivity, built using LangGraph and modern Python development practices with GitHub Copilot integration and Windows/PowerShell compatibility.

## Architecture & Tech Stack

### Core Technologies
- **Language**: Python 3.11+
- **Framework**: LangGraph for agent development and orchestration
- **Environment**: Windows with PowerShell
- **Development**: VS Code with GitHub Copilot
- **Dependencies**: pip for package management
- **Testing**: pytest with coverage
- **Linting**: ruff + mypy
- **Documentation**: Markdown

### Virtual Environment
- **Setup**: Use `python -m venv .venv` in PowerShell
- **Activation**: `.\.venv\Scripts\Activate.ps1` in PowerShell
- **Package Management**: `pip` for reliable dependency management

## Project Structure & Conventions

### File Organization
```
onenote-copilot/
├── .github/
│   └── copilot-instructions.md    # GitHub Copilot configuration
├── prompts/
│   ├── commands/                  # Command templates for PRP generation/execution
│   ├── examples/                  # Example PRPs and patterns
│   └── PRPs/                      # Project Request Proposals
├── src/                           # Main source code
│   ├── agents/                    # LangGraph agent implementations
│   ├── tools/                     # Agent tools and utilities
│   └── config/                    # Configuration management
├── tests/                         # Test files mirroring main structure
├── docs/                          # Additional documentation
├── PLANNING.md                    # This file - project planning and architecture
├── TASK.md                        # Task tracking and completion status
├── README.md                      # Project overview and setup
├── pyproject.toml                 # Modern Python packaging configuration
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment variable template
```

### Naming Conventions
- **Files**: snake_case for Python files, kebab-case for documentation
- **Classes**: PascalCase
- **Functions/Variables**: snake_case
- **Constants**: UPPER_SNAKE_CASE
- **Modules**: Short, descriptive, lowercase names

### Code Organization Principles
- **Maximum file length**: 500 lines
- **Module separation**: Group by feature/responsibility
- **Agent structure**:
  - `agent.py` - Main agent definition and execution
  - `tools.py` - Tool functions used by the agent
  - `prompts.py` - System prompts
- **Clear imports**: Prefer relative imports within packages
- **Type hints**: Required for all function signatures

## Development Workflow

### GitHub Copilot Integration
- Leverage GitHub Copilot Chat for architecture discussions
- Use inline suggestions for boilerplate code
- Utilize Copilot agent mode (`#github-pull-request_copilot-coding-agent`) for feature implementation
- Follow PRP (Project Request Proposal) pattern for complex features

### PRP (Project Request Proposal) System
1. **PRP Generation**: Use `prompts/commands/generate-prp.md` to create comprehensive feature specifications
2. **PRP Execution**: Use `prompts/commands/execute-prp.md` to implement features
3. **PRP Storage**: All PRPs stored in `prompts/PRPs/` directory
4. **Template**: Use `prompts/PRPs/templates/prp_base.md` as foundation

### Command Reference (PowerShell)
```powershell
# Virtual Environment
.\.venv\Scripts\Activate.ps1

# Development
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"                 # Run tests with TEST_RUN.md tracking
ruff check --fix; mypy .                   # Lint and type check
python -m src.main                          # Run main application

# Package Management
pip install package-name                   # Add dependency
pip uninstall package-name                 # Remove dependency
pip freeze > requirements.txt              # Update requirements file
```

## Quality Standards

### Testing Requirements
- **Coverage**: Minimum 80% test coverage
- **Test Structure**: Mirror main application structure in `/tests`
- **Test Types**: Unit tests, integration tests, end-to-end tests
- **Test Categories**:
  - Happy path test
  - Edge case test
  - Failure case test

### 🚨 MANDATORY: TEST_RUN.md Testing Approach
**ALL test execution MUST follow this pattern to prevent premature command execution:**

#### Required Test Command
```powershell
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

#### Critical Rules
1. **ALWAYS redirect pytest output to `TEST_RUN.md`** - never run tests without this redirection
2. **WAIT for `%TESTS FINISHED%` marker** - this indicates test completion
3. **NEVER proceed to next command** until you see the completion marker

### 🗂️ File Deletion Tracking Protocol
**🚨 CRITICAL PRACTICE - MANDATORY FOR ALL FILE DELETIONS 🚨**

#### Before Deleting Any File:
1. **REQUIRED**: Add entry to `DEL_FILES.md` before deletion
2. **Include**: Full file path, deletion reason, context, and date
3. **Follow**: The template format provided in `DEL_FILES.md`
4. **Purpose**: Maintain audit trail and enable file recovery

#### Entry Template:
```markdown
**File Path**: `path/to/file.ext`
- **Reason**: Brief reason for deletion
- **Context**: Why file existed and why removing
- **Deleted by**: [Name/Agent identifier]
- **Date**: YYYY-MM-DD
```

#### Why This Matters:
- **Audit Trail**: Track all file removals and decisions
- **Project History**: Understand evolution and changes
- **Recovery**: Enable restoration of accidentally deleted files
- **Team Coordination**: Prevent confusion about missing files
- **Documentation**: Record decision-making process

**NEVER delete without logging in DEL_FILES.md first!**

#### Test Execution Workflow
1. **Execute command**: Run the exact PowerShell command above
2. **Monitor file**: Periodically check `TEST_RUN.md` contents for progress
3. **Wait for marker**: Look for `%TESTS FINISHED%` at file end
4. **Analyze results**: Review test outcomes only after seeing completion marker
5. **Take action**: Fix failures or proceed based on complete results

#### Troubleshooting Long-Running Tests
```powershell
# Check current test progress
Get-Content TEST_RUN.md -Tail 10

# Run individual test files if needed
python -m pytest tests/test_specific.py -v > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

### Code Quality
- **Formatting**: Use `black` for code formatting
- **Linting**: `ruff` for style and error checking
- **Type Checking**: `mypy` for static type analysis
- **Documentation**: Google-style docstrings for all functions

### Validation Gates
All code must pass these checks before merge:
```powershell
# Syntax & Style
ruff check --fix
mypy .

# Tests - MANDATORY TEST_RUN.md approach
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"

# Integration (if applicable)
# Manual testing of main workflows
```

## AI Agent Architecture

### Core Principles
- **Modularity**: Each agent has specific, well-defined responsibilities
- **Tool-based**: Agents use tools for external interactions
- **Stateful**: LangGraph provides graph-based state management
- **Type-safe**: Pydantic models for all data structures
- **Context-aware**: Agents maintain conversation context through graph state

### LangGraph Patterns
- **Graph-based Flow**: Agents follow defined graph workflows
- **State Management**: Persistent state across agent interactions
- **Tool Integration**: External APIs and services as graph nodes
- **Multi-Agent**: Coordinated multi-agent systems with shared state
- **Conditional Logic**: Dynamic flow control based on agent decisions

## Environment & Configuration

### Environment Variables
Use `python-dotenv` with `.env` files:
- **Development**: `.env.local` (gitignored)
- **Production**: `.env` (documented in `.env.example`)
- **Loading**: Use `load_dotenv()` in configuration modules

### Configuration Management
- **Settings**: Use `pydantic-settings` for configuration
- **Validation**: Validate all environment variables on startup
- **Defaults**: Provide sensible defaults for development

## Documentation Standards

### README Structure
- Project overview and purpose
- Installation and setup instructions
- Usage examples
- API documentation (if applicable)
- Contributing guidelines
- License information

### Code Documentation
- **Docstrings**: Google-style for all public functions
- **Comments**: Explain 'why' not 'what'
- **Inline comments**: Use `# Reason:` for complex logic
- **Type hints**: Required for all function parameters and returns

## Deployment & Distribution

### Packaging
- Use modern Python packaging standards
- Include all necessary metadata in `pyproject.toml`
- Pin dependencies for reproducible builds

### CI/CD Integration
- GitHub Actions for automated testing
- PowerShell-compatible scripts
- Windows-first deployment strategies

## Security Considerations

### Environment Security
- Never commit secrets to git
- Use `.env` files for local development
- Implement proper secret management for production

### AI Agent Security
- Validate all inputs to agents
- Implement rate limiting for external API calls
- Use structured outputs to prevent injection attacks

## Project Goals & Constraints

### Primary Goals
- Build production-ready AI agents
- Demonstrate modern Python development practices
- Showcase GitHub Copilot integration patterns
- Maintain Windows/PowerShell compatibility

### Constraints
- Windows development environment required
- PowerShell as primary shell
- GitHub Copilot as primary AI assistant
- Type safety throughout codebase
- Comprehensive testing required

## Evolution & Maintenance

### Version Management
- Semantic versioning for releases
- Keep CHANGELOG.md updated
- Tag releases in git

### Technical Debt Management
- Regular refactoring cycles
- Monitor file size limits (500 lines max)
- Update dependencies regularly
- Review and update documentation quarterly

## References & Resources

### Official Documentation
- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [GitHub Copilot Documentation](https://docs.github.com/copilot)
- [PowerShell Documentation](https://docs.microsoft.com/powershell)

### Best Practices
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Python Best Practices](https://realpython.com/python-application-layouts/)
- [Type Hint Best Practices](https://typing.readthedocs.io/en/latest/guides/writing_good_generics.html)
