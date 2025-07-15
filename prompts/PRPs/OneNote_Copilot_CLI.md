name: "OneNote Copilot CLI: LangGraph-Based AI Assistant for Natural Language OneNote Search"
description: |
  A comprehensive PRP for building a PowerShell-compatible CLI application that provides intelligent search
  and interaction with Microsoft OneNote using natural language queries through LangGraph agents.

## Purpose
Build a production-ready AI-powered CLI assistant that allows users to search, query, and interact with their Microsoft OneNote content using natural language. The system uses LangGraph for stateful agent management, Microsoft Graph API for OneNote access, and Rich library for beautiful terminal interfaces.

## Core Principles
1. **Context is King**: Include ALL necessary documentation, examples, and caveats
2. **Validation Loops**: Provide executable tests/lints the AI can run and fix
3. **Information Dense**: Use keywords and patterns from the codebase
4. **Progressive Success**: Start simple, validate, then enhance
5. **GitHub Copilot Integration**: Leverage GitHub Copilot and its agent mode for code generation
6. **Windows/PowerShell Compatibility**: All commands and scripts should work on Windows with PowerShell

---

## Goal
Create a CLI application where users can search their OneNote content using natural language queries like:
- "What did I write about project planning last week?"
- "Show me all my meeting notes from December"
- "Find notes about Python development best practices"

The system should provide intelligent summaries, direct answers, and source links to original OneNote pages.

## Why
- **Business value**: Dramatically improves productivity by making OneNote content instantly searchable with AI
- **Integration**: Demonstrates modern AI agent patterns with real-world Microsoft APIs
- **Problems solved**: Eliminates manual browsing through notebooks to find specific information

## What
A LangGraph-based CLI application with:
- Interactive chat interface using Rich library for beautiful formatting
- Microsoft Graph API integration for OneNote access
- MSAL authentication with browser-based OAuth2 flow
- Streaming AI responses with source attribution
- Comprehensive error handling and graceful degradation

### Success Criteria
- [ ] Users can authenticate with personal Microsoft accounts
- [ ] Natural language search returns relevant OneNote content
- [ ] AI provides intelligent summaries with source links
- [ ] CLI interface is beautiful and responsive
- [ ] All tests pass and code meets quality standards
- [ ] Works seamlessly on Windows with PowerShell

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- url: https://learn.microsoft.com/en-us/graph/integrate-with-onenote
  why: Core OneNote API integration patterns and authentication requirements

- url: https://learn.microsoft.com/en-us/graph/api/resources/onenote-api-overview
  why: Complete OneNote REST API reference with endpoints and data models

- url: https://learn.microsoft.com/en-us/graph/search-query-parameter
  why: Microsoft Graph $search parameter for filtering OneNote content

- url: https://learn.microsoft.com/en-us/entra/msal/python/
  why: MSAL Python authentication patterns for personal accounts

- url: https://langchain-ai.github.io/langgraph/concepts/why-langgraph/
  why: LangGraph fundamentals and stateful agent patterns

- url: https://realpython.com/langgraph-python/
  why: Hands-on LangGraph tutorial with Python examples

- url: https://rich.readthedocs.io/en/stable/markdown.html
  why: Rich library markdown rendering for beautiful CLI output

- url: https://medium.com/@jarisko/easiest-way-for-graph-api-with-personal-microsoft-account-an-onenote-example-e67ee336e7b5
  why: Real-world example of Graph API with personal accounts

- file: prompts/examples/example_msal_auth.py.md
  why: Authentication strategy and implementation pattern for personal Microsoft accounts

- file: prompts/examples/example_chat_cli.py.md
  why: Rich CLI chat interface pattern with streaming responses and session management

- file: prompts/INITIAL.md
  why: Complete feature requirements, examples, and configuration details
```

### Current Codebase Tree
```powershell
# Current structure (Get-ChildItem -Recurse)
c:\src\onenote-copilot\
├── .env.example                     # Environment template with OpenAI config
├── requirements.txt                 # Dependencies including LangGraph, MSAL, Rich
├── pyproject.toml                   # Modern Python packaging
├── src/                            # Empty - ready for implementation
├── tests/                          # Empty - ready for tests
├── prompts/
│   ├── INITIAL.md                  # Complete feature specification
│   ├── examples/
│   │   ├── example_msal_auth.py.md # MSAL authentication patterns
│   │   └── example_chat_cli.py.md  # Rich CLI interface examples
│   └── PRPs/
│       └── templates/
│           └── prp_base.md         # PRP template structure
└── PROGRESS.md                     # Current progress tracking
```

### Desired Codebase Tree with Files to be Added
```powershell
# Target structure after implementation
c:\src\onenote-copilot\
├── src/
│   ├── __init__.py                 # Package init
│   ├── main.py                     # CLI entry point with typer/rich
│   ├── config/
│   │   ├── __init__.py             # Package init
│   │   └── settings.py             # Pydantic settings with environment validation
│   ├── auth/
│   │   ├── __init__.py             # Package init
│   │   └── microsoft_auth.py       # MSAL authentication with token caching
│   ├── agents/
│   │   ├── __init__.py             # Package init
│   │   ├── onenote_agent.py        # Main LangGraph agent for OneNote interactions
│   │   └── prompts.py              # System prompts and agent instructions
│   ├── tools/
│   │   ├── __init__.py             # Package init
│   │   ├── onenote_search.py       # OneNote search tool using Graph API
│   │   └── onenote_content.py      # OneNote content retrieval and processing
│   ├── models/
│   │   ├── __init__.py             # Package init
│   │   ├── onenote.py              # Pydantic models for OneNote data
│   │   └── responses.py            # Response models for agent outputs
│   └── cli/
│       ├── __init__.py             # Package init
│       ├── interface.py            # Rich-based interactive CLI
│       └── formatting.py          # Output formatting and markdown rendering
├── tests/
│   ├── __init__.py                 # Package init
│   ├── test_config/
│   │   └── test_settings.py        # Configuration tests
│   ├── test_auth/
│   │   └── test_microsoft_auth.py  # Authentication tests
│   ├── test_agents/
│   │   └── test_onenote_agent.py   # Agent functionality tests
│   ├── test_tools/
│   │   ├── test_onenote_search.py  # Search tool tests
│   │   └── test_onenote_content.py # Content retrieval tests
│   ├── test_models/
│   │   ├── test_onenote.py         # Data model tests
│   │   └── test_responses.py       # Response model tests
│   └── test_cli/
│       ├── test_interface.py       # CLI interface tests
│       └── test_formatting.py     # Output formatting tests
├── .env.local                      # User environment (gitignored)
└── credentials/                    # MSAL token cache directory (gitignored)
    └── .gitkeep
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: OneNote API through Graph requires specific scopes
# Notes.Read for read access, Notes.ReadWrite for write access
# Scope must be exact: "Notes.Read" not "notes.read"

# CRITICAL: Personal Microsoft accounts use authority "common"
# AUTHORITY = "https://login.microsoftonline.com/common"

# CRITICAL: MSAL requires PublicClientApplication for personal accounts
# Not ConfidentialClientApplication

# CRITICAL: OneNote search using $search parameter has limitations
# Only searches page titles and content, not tags or metadata directly
# Format: GET /me/onenote/pages?$search="search term"

# CRITICAL: LangGraph agents must be async throughout
# No mixing sync and async code in agent implementations

# CRITICAL: Microsoft Graph API rate limits
# 10,000 requests per 10 minutes per user
# Must implement proper retry logic with exponential backoff

# CRITICAL: Rich library Live() context for streaming updates
# Must be used properly to avoid terminal corruption
# Always use try/finally blocks with Live contexts

# CRITICAL: OneNote content is returned as HTML
# Need to parse and extract text content for AI processing
# BeautifulSoup or similar HTML parser required

# CRITICAL: Token refresh must be handled gracefully
# MSAL handles this automatically but network errors need handling

# CRITICAL: Windows path handling in token cache
# Use pathlib.Path for cross-platform compatibility
# Default cache location: ~/.msal_token_cache.json
```

## Implementation Blueprint

### GitHub Copilot Workflow Integration
```yaml
# Leverage GitHub Copilot for implementation:
- Use GitHub Copilot Chat for complex LangGraph agent architecture discussions
- Leverage inline suggestions for boilerplate Pydantic models and async functions
- Use Copilot agent mode (#github-pull-request_copilot-coding-agent) for full feature implementation
- Validate generated code using the validation loops below
- Follow PowerShell commands for Windows compatibility
```

### Data Models and Structure

Core data models ensure type safety and API consistency:
```python
# models/onenote.py - OneNote API data structures
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime

class OneNoteNotebook(BaseModel):
    id: str = Field(..., description="Unique notebook identifier")
    display_name: str = Field(..., alias="displayName")
    created_date_time: datetime = Field(..., alias="createdDateTime")
    last_modified_date_time: datetime = Field(..., alias="lastModifiedDateTime")
    links: Dict[str, Any] = Field(default_factory=dict)

class OneNotePage(BaseModel):
    id: str
    title: str
    content_url: Optional[HttpUrl] = Field(None, alias="contentUrl")
    created_date_time: datetime = Field(..., alias="createdDateTime")
    last_modified_date_time: datetime = Field(..., alias="lastModifiedDateTime")
    content: Optional[str] = None  # HTML content when retrieved
    text_content: Optional[str] = None  # Extracted text for AI processing

class SearchResult(BaseModel):
    pages: List[OneNotePage]
    query: str
    total_count: int = Field(default=0)
    search_metadata: Dict[str, Any] = Field(default_factory=dict)

# models/responses.py - Agent response structures
class OneNoteSearchResponse(BaseModel):
    answer: str = Field(..., description="AI-generated answer to user query")
    sources: List[OneNotePage] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    search_query_used: str = Field(..., description="Actual search query sent to OneNote")
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### List of Tasks to be Completed

```yaml
Task 1: Environment and Configuration Setup
CREATE src/config/settings.py:
  - PATTERN: Use pydantic-settings with environment validation
  - VALIDATE: All required API keys and endpoints
  - INCLUDE: OpenAI, MSAL, and Graph API configurations

UPDATE .env.example:
  - ADD: Microsoft Graph and MSAL configuration variables
  - INCLUDE: All OneNote-specific settings
  - DOCUMENT: Each variable with clear descriptions

Task 2: Microsoft Authentication Implementation
CREATE src/auth/microsoft_auth.py:
  - PATTERN: Follow prompts/examples/example_msal_auth.py.md
  - IMPLEMENT: Browser-based OAuth2 flow for personal accounts
  - HANDLE: Token caching and automatic refresh
  - SCOPE: Notes.Read permission for OneNote access

Task 3: OneNote API Tools Implementation
CREATE src/tools/onenote_search.py:
  - IMPLEMENT: Microsoft Graph API integration for search
  - HANDLE: $search parameter for content filtering
  - PARSE: HTML content to extract readable text
  - ERROR_HANDLING: Rate limits and network failures

CREATE src/tools/onenote_content.py:
  - IMPLEMENT: Content retrieval and processing
  - EXTRACT: Text from HTML responses
  - STRUCTURE: Content for AI agent consumption

Task 4: LangGraph Agent Implementation
CREATE src/agents/onenote_agent.py:
  - PATTERN: Follow LangGraph agent examples from research
  - IMPLEMENT: Stateful agent with tool integration
  - HANDLE: Natural language query processing
  - STREAM: Responses for real-time CLI feedback

CREATE src/agents/prompts.py:
  - DEFINE: System prompts for OneNote assistance
  - INCLUDE: Instructions for search optimization
  - TEMPLATE: Response formatting guidelines

Task 5: Rich CLI Interface Implementation
CREATE src/cli/interface.py:
  - PATTERN: Follow prompts/examples/example_chat_cli.py.md
  - IMPLEMENT: Interactive chat interface with Rich
  - HANDLE: Streaming responses with Live() context
  - INCLUDE: Command system (/help, /exit, etc.)

CREATE src/cli/formatting.py:
  - IMPLEMENT: Markdown rendering for responses
  - HANDLE: Source link formatting
  - STYLE: Consistent color scheme and layout

Task 6: Main Application Entry Point
CREATE src/main.py:
  - IMPLEMENT: Typer-based CLI application
  - INTEGRATE: All components (auth, agent, CLI)
  - HANDLE: Application lifecycle and error recovery
  - CONFIGURE: Logging and debugging options

Task 7: Comprehensive Testing Suite
CREATE tests/ structure:
  - UNIT_TESTS: All modules with 80%+ coverage
  - INTEGRATION_TESTS: Full authentication and API flows
  - CLI_TESTS: User interaction scenarios
  - MOCK_TESTS: External API calls for offline testing
```

### Per Task Pseudocode

```python
# Task 2: Microsoft Authentication (critical implementation details)
class MicrosoftAuthenticator:
    async def authenticate(self) -> str:
        # PATTERN: Check cache first (see MSAL docs)
        accounts = self.app.get_accounts()
        if accounts:
            # GOTCHA: Silent token acquisition can fail
            try:
                result = self.app.acquire_token_silent(SCOPES, account=accounts[0])
                if result and "access_token" in result:
                    return result["access_token"]
            except Exception:
                # Fall through to interactive auth
                pass

        # PATTERN: Interactive browser flow
        # CRITICAL: Use authorization_code flow for personal accounts
        auth_url = self.app.get_authorization_request_url(
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        # GOTCHA: Must handle localhost callback server
        # Start local server, open browser, wait for callback
        token = await self._handle_interactive_flow(auth_url)
        return token

# Task 3: OneNote Search (Graph API integration)
async def search_onenote_content(query: str, auth_token: str) -> SearchResult:
    # PATTERN: Use $search parameter for content filtering
    endpoint = f"https://graph.microsoft.com/v1.0/me/onenote/pages"
    params = {"$search": query, "$top": 20}

    # CRITICAL: Proper authorization header format
    headers = {"Authorization": f"Bearer {auth_token}"}

    # GOTCHA: Handle rate limiting with retry logic
    @retry(attempts=3, backoff=exponential)
    async def _make_request():
        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            return response.json()

    data = await _make_request()

    # CRITICAL: Parse HTML content to extract text
    pages = []
    for page_data in data.get("value", []):
        # Get full page content if needed
        if page_data.get("contentUrl"):
            content = await _fetch_page_content(page_data["contentUrl"], headers)
            page_data["text_content"] = _extract_text_from_html(content)

        pages.append(OneNotePage(**page_data))

    return SearchResult(pages=pages, query=query, total_count=len(pages))

# Task 4: LangGraph Agent (stateful AI agent)
from langgraph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI

class OneNoteAgent:
    def __init__(self):
        # PATTERN: Initialize LLM and tools
        self.llm = ChatOpenAI(model="gpt-4o-mini")
        self.tools = [self.search_tool, self.content_tool]

        # CRITICAL: Define agent state and graph
        self.graph = self._create_agent_graph()

    def _create_agent_graph(self) -> StateGraph:
        # PATTERN: Node-based agent workflow
        workflow = StateGraph(MessagesState)

        workflow.add_node("agent", self._call_model)
        workflow.add_node("tools", self._execute_tools)

        # CRITICAL: Conditional edges for tool usage
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {"continue": "tools", "end": "__end__"}
        )

        workflow.set_entry_point("agent")
        return workflow.compile()

    async def process_query(self, query: str) -> OneNoteSearchResponse:
        # PATTERN: Stream responses for CLI feedback
        messages = [{"role": "user", "content": query}]

        # GOTCHA: Handle streaming state updates
        async for event in self.graph.astream({"messages": messages}):
            # Process state updates and yield intermediate results
            yield self._format_streaming_response(event)

# Task 5: Rich CLI Interface (beautiful terminal experience)
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

class OneNoteCLI:
    def __init__(self):
        self.console = Console()
        self.agent = OneNoteAgent()

    async def start_chat(self):
        # PATTERN: Interactive chat loop with Rich formatting
        self._show_welcome()

        while True:
            user_input = self._get_user_input()

            if user_input.startswith('/'):
                await self._handle_command(user_input)
                continue

            # CRITICAL: Stream responses with Live() context
            with Live(
                self._create_loading_panel(),
                refresh_per_second=10,
                console=self.console
            ) as live:
                response_parts = []

                async for chunk in self.agent.process_query(user_input):
                    response_parts.append(chunk)
                    # PATTERN: Update live display with partial response
                    live.update(self._format_partial_response(response_parts))

                # FINAL: Display complete response with sources
                final_response = self._format_complete_response(response_parts)
                live.update(final_response)
```

### Integration Points
```yaml
AUTHENTICATION:
  - cache_location: "~/.msal_token_cache.json"
  - authority: "https://login.microsoftonline.com/common"
  - scopes: ["Notes.Read", "User.Read"]

MICROSOFT_GRAPH:
  - base_url: "https://graph.microsoft.com/v1.0"
  - endpoints: ["/me/onenote/notebooks", "/me/onenote/pages"]
  - rate_limits: "10,000 requests per 10 minutes"

CLI_COMMANDS:
  - "/help": Show available commands and usage
  - "/notebooks": List all accessible notebooks
  - "/recent": Show recently modified pages
  - "/clear": Clear conversation history
  - "/exit": Quit the application

ENVIRONMENT_VARIABLES:
  - OPENAI_API_KEY: Required for LangGraph agent
  - AZURE_CLIENT_ID: Required for MSAL authentication
  - LOG_LEVEL: Optional logging configuration
  - CACHE_DIR: Optional custom cache directory
```

## Validation Loop

### Level 1: Syntax & Style
```powershell
# Run these FIRST - fix any errors before proceeding (Windows PowerShell)
ruff check src/ --fix                      # Auto-fix formatting issues
mypy src/                                  # Type checking validation
# Expected: No errors. If errors, READ the error message and fix root cause.
```

### Level 2: Unit Tests
```python
# Key test patterns to implement:

# Authentication tests
def test_msal_authentication():
    """Test MSAL authentication flow"""
    auth = MicrosoftAuthenticator()
    # Test with mocked token response
    assert auth.validate_token(mock_token)

def test_token_refresh():
    """Test automatic token refresh"""
    # Mock expired token scenario
    # Verify refresh happens automatically

# OneNote API tests
def test_search_functionality():
    """Test OneNote search with various queries"""
    search_tool = OneNoteSearchTool()
    # Test with mocked Graph API responses
    result = search_tool.search("test query")
    assert isinstance(result, SearchResult)

def test_content_extraction():
    """Test HTML to text conversion"""
    html_content = "<div>Test content</div>"
    text = extract_text_from_html(html_content)
    assert text == "Test content"

# Agent tests
def test_agent_query_processing():
    """Test LangGraph agent query handling"""
    agent = OneNoteAgent()
    # Test with mocked tools and LLM
    response = agent.process_query("find my notes about python")
    assert isinstance(response, OneNoteSearchResponse)

# CLI tests
def test_cli_formatting():
    """Test Rich formatting functions"""
    formatter = CLIFormatter()
    # Test markdown rendering
    # Test source link formatting
```

```powershell
# Run and iterate until passing (Windows PowerShell):
python -m pytest tests/ -v --cov=src --cov-report=term-missing
# Target: 80%+ coverage. If failing, read errors carefully and fix issues.
```

### Level 3: Integration Tests
```powershell
# Authentication integration test
python -m src.auth.microsoft_auth
# Expected: Browser opens, successful login flow, token cached

# OneNote API integration test
python -c "
import asyncio
from src.tools.onenote_search import search_onenote_content
async def test():
    result = await search_onenote_content('test', 'fake_token')
    print(result)
asyncio.run(test())
"
# Expected: Proper error handling for invalid token

# Full CLI integration test
python -m src.main
# Expected: Welcome message, command prompt, graceful error handling
```

### Level 4: End-to-End Validation
```powershell
# Complete user workflow test
.\.venv\Scripts\Activate.ps1              # Activate virtual environment
python -m src.main                         # Start the CLI

# In the CLI, test these scenarios:
# 1. Authentication flow works
# 2. Search query returns results
# 3. Results are properly formatted
# 4. Source links are functional
# 5. Error handling for no results
# 6. Help command works
# 7. Exit command works cleanly
```

## Final Validation Checklist
- [ ] All tests pass: `python -m pytest tests/ -v --cov=src --cov-report=term-missing`
- [ ] No linting errors: `ruff check src/`
- [ ] No type errors: `mypy src/`
- [ ] Authentication flow works in browser
- [ ] OneNote search returns real results (with valid credentials)
- [ ] CLI interface is responsive and beautiful
- [ ] Error cases handled gracefully with helpful messages
- [ ] Logs are informative but not verbose
- [ ] Documentation updated with setup instructions

---

## Anti-Patterns to Avoid
- ❌ Don't store credentials in code or version control
- ❌ Don't ignore Graph API rate limits - implement proper retry logic
- ❌ Don't mix sync and async code in LangGraph agents
- ❌ Don't parse HTML with regex - use proper HTML parser
- ❌ Don't hardcode Microsoft Graph endpoints - use configuration
- ❌ Don't skip token validation - always verify before API calls
- ❌ Don't ignore MSAL exceptions - handle authentication failures gracefully
- ❌ Don't corrupt Rich Live() contexts - always use try/finally blocks

## Confidence Score: 9/10

This PRP provides comprehensive context for successful implementation:
- ✅ Complete Microsoft Graph API integration patterns
- ✅ Detailed MSAL authentication workflows
- ✅ LangGraph agent architecture with real examples
- ✅ Rich CLI interface patterns from working code
- ✅ Comprehensive error handling strategies
- ✅ Windows/PowerShell compatibility throughout
- ✅ Executable validation loops for iterative improvement
- ✅ Real-world gotchas and library quirks documented

The only minor uncertainty is potential OneNote API response variations across different account types, but the comprehensive error handling should address this gracefully.
