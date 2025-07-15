## FEATURE:

- **OneNote Copilot CLI**: A PowerShell-based command-line application that provides intelligent search and interaction with Microsoft OneNote using natural language queries
- **Interactive Chat Interface**: Conversational CLI that allows users to ask questions about their OneNote content in plain English
- **Comprehensive Search**: Semantic search across all OneNote notebooks, pages, sections, text content, titles, tags, metadata, and embedded links
- **AI-Powered Responses**: Uses GPT-4o to provide intelligent summaries, answers, and insights from OneNote content
- **Smart Output Formatting**: Automatically selects the best presentation format (plain text, colored text, markdown) based on response type
- **Source References**: Provides links to original OneNote pages for detailed exploration
- **Read-Only Access**: Safe, non-destructive interaction with OneNote data (MVP version)

## EXAMPLES:

User interaction examples:
```powershell
# Start the interactive CLI
python -m src.main

> What did I write about project planning last week?
[AI searches and summarizes recent project planning notes with page links]

> Show me all my meeting notes from December
[AI finds and summarizes meeting notes with source links]

> What are the main themes in my research about AI agents?
[AI analyzes content and provides thematic summary]

> Find notes about Python development best practices
[AI returns relevant code snippets and practices with page references]
```

CLI Features:
- Interactive chat mode with conversation history
- Graceful error handling for connectivity issues
- Clear progress indicators for longer searches
- Intelligent response formatting based on content type

## DOCUMENTATION:

### Core Technologies:
- **Microsoft Graph API**: https://docs.microsoft.com/en-us/graph/api/onenote-list-notebooks
- **OneNote API Reference**: https://docs.microsoft.com/en-us/graph/api/resources/onenote
- **OpenAI GPT-4o**: https://platform.openai.com/docs/models/gpt-4o
- **Pydantic AI**: https://ai.pydantic.dev/
- **Microsoft Authentication Library (MSAL)**: https://docs.microsoft.com/en-us/azure/active-directory/develop/msal-overview

### Authentication Flow:
- Web browser-based OAuth2 authentication
- Personal Microsoft account support
- Secure token storage for session persistence

### Search Architecture:
- Real-time API calls to OneNote (no local caching)
- Semantic search using AI embeddings
- Content aggregation across all accessible notebooks

## OTHER CONSIDERATIONS:

### MVP Features (Priority Order):
1. **Basic Natural Language Search**: Query OneNote content using conversational English
2. **Content Summarization**: AI-generated summaries of search results
3. **Question Answering**: Direct answers to specific questions about content
4. **Recent Content Discovery**: Find recently modified or accessed content

### Future Features (Post-MVP, not doing it now):
1. **Writing Capabilities**: Create and edit OneNote content through CLI
2. **Content Organization Suggestions**: AI-powered recommendations for note organization
3. **Integration with Other Tools**: Connect with calendars, emails, and task managers
4. **Advanced Analytics**: Content insights, usage patterns, and knowledge gaps

### Technical Requirements:
- **Python 3.11+** with async/await support
- **PowerShell 7** compatibility for Windows 11
- **Virtual Environment**: `.\.venv\Scripts\Activate.ps1`
- **Error Handling**: Graceful degradation for API rate limits and connectivity issues
- **Performance**: Thorough analysis prioritized over speed
- **Security**: No local data caching, secure credential management

### User Experience:
- **Minimal Configuration**: Automatic discovery of all accessible notebooks
- **Smart Formatting**: Dynamic output format selection based on response type
- **Source Traceability**: All responses include links to original OneNote pages
- **Error Communication**: Clear, actionable error messages for users

### Development Standards:
- **Type Safety**: Full type hints with mypy validation
- **Testing**: Comprehensive unit tests with 80%+ coverage
- **Code Quality**: Ruff formatting and linting
- **Documentation**: Google-style docstrings for all functions
- **Modularity**: No files exceeding 500 lines of code

## CONFIGURATION:

### Environment Variables (.env.local):
```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o

# Microsoft Graph API Configuration
AZURE_CLIENT_ID=your_azure_app_client_id
AZURE_TENANT_ID=common  # For personal accounts
AZURE_REDIRECT_URI=http://localhost:8080/callback

# Application Settings
LOG_LEVEL=INFO
MAX_SEARCH_RESULTS=10
RESPONSE_TIMEOUT_SECONDS=30
```

### Required Azure App Registration:
- **Application Type**: Public client application
- **Redirect URI**: `http://localhost:8080/callback`
- **API Permissions**:
  - `Notes.Read` (OneNote notebooks read access)
  - `User.Read` (basic profile information)
- **Authentication**: Personal Microsoft accounts supported

### Installation & Setup:
```powershell
# Clone and setup
git clone https://github.com/shulgaalexey/onenote-copilot.git
cd onenote-copilot

# Virtual environment setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env.local
# Edit .env.local with your API keys

# Run the application
python -m src.main
```

### Project Structure:
```
src/
├── main.py                 # CLI entry point
├── agent/
│   ├── __init__.py
│   ├── onenote_agent.py   # Main AI agent
│   ├── tools.py           # OneNote API tools
│   └── prompts.py         # System prompts
├── auth/
│   ├── __init__.py
│   └── microsoft_auth.py  # OAuth2 authentication
├── cli/
│   ├── __init__.py
│   ├── interface.py       # Interactive CLI
│   └── formatting.py     # Output formatting
└── models/
    ├── __init__.py
    ├── onenote.py         # OneNote data models
    └── responses.py       # Response models

tests/
├── test_agent/
├── test_auth/
├── test_cli/
└── test_models/
```