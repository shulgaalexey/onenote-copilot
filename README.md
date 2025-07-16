# OneNote Copilot 🤖📚

> **AI-powered natural language search for your OneNote content**

OneNote Copilot brings the power of conversational AI to your OneNote notebooks, allowing you to search and interact with your notes using natural language queries. Built with LangGraph for intelligent conversation flow and Rich for beautiful terminal interfaces.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Quality](https://img.shields.io/badge/code%20quality-ruff-black.svg)](https://github.com/astral-sh/ruff)

## ✨ Features

- 🔍 **Natural Language Search**: Ask questions like "Show me notes about project planning from last month"
- 🤖 **AI-Powered Responses**: Uses OpenAI GPT models for intelligent query processing
- 📖 **OneNote Integration**: Seamless access to your Microsoft OneNote content via Graph API
- 🎨 **Beautiful CLI**: Rich terminal interface with markdown rendering and streaming responses
- 🔐 **Secure Authentication**: OAuth2 flow with secure token caching
- ⚡ **Fast & Responsive**: Streaming responses with real-time feedback
- 🛠️ **Extensible**: Built on LangGraph for easy customization and extension

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Microsoft Account** with OneNote content
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd onenote-copilot
   ```

2. **Create and activate virtual environment:**
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # macOS/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   # Windows (PowerShell)
   $env:OPENAI_API_KEY = "your-openai-api-key-here"

   # macOS/Linux
   export OPENAI_API_KEY="your-openai-api-key-here"
   ```

### First Run

1. **Authenticate with Microsoft:**
   ```bash
   python -m src.main --auth-only
   ```
   This will open your browser for secure Microsoft authentication.

2. **Start chatting:**
   ```bash
   python -m src.main
   ```

## 💬 Usage Examples

Once authenticated, you can ask natural language questions about your OneNote content:

```
📝 What did I write about vacation planning?
🔍 Show me meeting notes from last week
📊 Find my project timeline notes
✏️ What are my action items from yesterday?
📚 Search for notes about Python programming
```

### Available Commands

- `/help` - Show help and available commands
- `/notebooks` - List your OneNote notebooks
- `/recent` - Show recently modified pages
- `/starters` - Display conversation starter examples
- `/clear` - Clear conversation history
- `/quit` or `/exit` - Exit the application

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) | - |
| `AZURE_CLIENT_ID` | Custom Azure app client ID | Built-in default |
| `OPENAI_MODEL`    | OpenAI model to use         | `gpt-4o-mini`    |
| `ONENOTE_DEBUG` | Enable debug logging | `false` |
| `CLI_COLOR_ENABLED` | Enable colored output | `true` |

### Obtaining Your Azure Client ID

To use a custom Azure app with OneNote Copilot, you must register an application in the Azure Portal and copy its Client (Application) ID:

1. Sign in to the Azure Portal: https://portal.azure.com
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Enter a name (e.g., `OneNote Copilot`)
5. Under **Redirect URI**, select **Public client (mobile & desktop)** and enter `http://localhost`
6. Click **Register**
7. From the **Overview** page, copy the **Application (client) ID**
8. Set the `AZURE_CLIENT_ID` environment variable to this value

**Or use the automated PowerShell script (easiest):**

```powershell
# Run the setup script with default settings
.\setup-azure-app.ps1

# Or with automatic environment variable setup
.\setup-azure-app.ps1 -SetEnvironmentVariable

# Or to persist the environment variable across sessions
.\setup-azure-app.ps1 -PersistEnvironmentVariable

# If you have multiple tenants (specify your organizational tenant)
.\setup-azure-app.ps1 -TenantId "8da79306-87d0-41ba-b20c-f4f4d2963ff9" -SetEnvironmentVariable

# Custom app name
.\setup-azure-app.ps1 -AppName "My Custom OneNote App" -SetEnvironmentVariable
```

> **💡 Tip for Multiple Tenants**: If you see "Default Directory" errors, use your organizational tenant ID instead. Personal Microsoft accounts often can't create app registrations.

**Or register manually via Azure CLI in PowerShell:**

```powershell
# Sign in to Azure
az login

# Method 1: Using properly escaped JSON (recommended)
$AZURE_CLIENT_ID = az ad app create `
   --display-name "OneNote Copilot" `
   --public-client-redirect-uris "http://localhost" `
   --required-resource-accesses '[{\"resourceAppId\":\"00000003-0000-0000-c000-000000000000\",\"resourceAccess\":[{\"id\":\"37f7f235-527c-4136-accd-4a02d197296e\",\"type\":\"Scope\"}]}]' `
   --query appId -o tsv

# Method 2: Alternative using here-string (if Method 1 fails)
$ResourceAccess = @'
[{"resourceAppId":"00000003-0000-0000-c000-000000000000","resourceAccess":[{"id":"37f7f235-527c-4136-accd-4a02d197296e","type":"Scope"}]}]
'@

$AZURE_CLIENT_ID = az ad app create `
   --display-name "OneNote Copilot" `
   --public-client-redirect-uris "http://localhost" `
   --required-resource-accesses $ResourceAccess `
   --query appId -o tsv

Write-Host "Application (client) ID: $AZURE_CLIENT_ID"

# Set environment variable for current session
$env:AZURE_CLIENT_ID = $AZURE_CLIENT_ID

# (Optional) Persist across sessions:
#   Set-Item -Path Env:AZURE_CLIENT_ID -Value $AZURE_CLIENT_ID
```

### Advanced Configuration

Create a settings file at `~/.config/onenote-copilot/settings.toml`:

```toml
[openai]
model = "gpt-4o-mini"
api_key = "your-key-here"

[microsoft]
client_id = "8a58e817-6d2f-4355-96e8-82695c48c4b7"  # Your app's Client ID

[cli]
color_enabled = true
markdown_enabled = true
welcome_enabled = true

[debug]
enabled = false
```

### Configuration Verification

Run the verification script to check your setup:

```powershell
.\verify-config.ps1
```

This will verify:
- ✅ Environment variables are set correctly
- ✅ Azure CLI authentication status
- ✅ Python virtual environment
- ✅ App registration configuration

## 🏗️ Architecture

OneNote Copilot is built with a modern, extensible architecture:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Rich CLI      │───▶│   LangGraph      │───▶│   OneNote API   │
│   Interface     │    │   Agent          │    │   Integration   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Typer CLI     │    │   OpenAI GPT     │    │   MSAL Auth     │
│   Framework     │    │   Models         │    │   OAuth2        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Key Components

- **LangGraph Agent**: Stateful conversation management with tool integration
- **OneNote Search Tool**: Microsoft Graph API integration with content extraction
- **MSAL Authentication**: Secure OAuth2 flow with token caching
- **Rich CLI Interface**: Beautiful terminal UI with streaming responses
- **Pydantic Models**: Type-safe data validation and configuration management

## 🧪 Testing

### 🚨 MANDATORY: TEST_RUN.md Approach
**All test execution must use this pattern to ensure proper completion tracking:**

```powershell
# Required test command with output redirection
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

#### Why Use TEST_RUN.md?
- **Prevents premature actions**: Ensures tests complete before next steps
- **Progress tracking**: Monitor test execution in real-time
- **Completion verification**: Clear `%TESTS FINISHED%` marker indicates completion
- **Debugging support**: Full test output captured for failure analysis

#### Testing Workflow
1. **Execute**: Run the command above to start tests
2. **Monitor**: Check `TEST_RUN.md` contents to see progress
3. **Wait**: Look for `%TESTS FINISHED%` marker at file end
4. **Analyze**: Review results only after completion marker appears
5. **Fix**: Address any failures and re-run using same pattern

### Alternative Test Commands
```bash
# Run all tests (legacy - use TEST_RUN.md approach instead)
python run_tests.py all

# Run only unit tests
python run_tests.py unit

# Run with coverage
python run_tests.py coverage

# Run linting and type checking
python run_tests.py check
```

### Development Testing Best Practices
- **Never skip TEST_RUN.md pattern** for pytest execution
- **Always wait for completion marker** before proceeding
- **Monitor file contents** to track progress
- **Maximum wait time**: 5 minutes before investigating issues
- **Use same pattern** for all test types (unit, integration, coverage)

## 🔒 Security & Privacy

- **OAuth2 Authentication**: Uses Microsoft's secure OAuth2 flow
- **Token Caching**: Encrypted local token storage with automatic refresh
- **No Data Storage**: Your OneNote content is never stored locally
- **API Rate Limiting**: Respects Microsoft Graph API rate limits
- **Minimal Permissions**: Only requests read access to OneNote content

## 🛠️ Development

### Project Structure

```
onenote-copilot/
├── src/
│   ├── agents/          # LangGraph agent implementation
│   ├── auth/            # Microsoft authentication
│   ├── cli/             # Rich-based CLI interface
│   ├── config/          # Settings and configuration
│   ├── models/          # Pydantic data models
│   └── tools/           # OneNote API integration
├── tests/               # Comprehensive test suite
├── prompts/             # Development prompts and examples
└── requirements.txt     # Python dependencies
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes with tests
4. Run the test suite: `python run_tests.py check`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

### 🗂️ File Deletion Policy

**🚨 IMPORTANT**: This project maintains strict file deletion tracking for audit and recovery purposes.

#### Before Deleting Any File:
- **MANDATORY**: Log deletion in `DEL_FILES.md` before removing the file
- **Include**: Full file path, reason, context, and date
- **Follow**: Template format provided in `DEL_FILES.md`
- **Purpose**: Maintain project history and enable file recovery

#### Example Entry:
```markdown
**File Path**: `src/deprecated/old_module.py`
- **Reason**: Replaced by new implementation
- **Context**: Functionality moved to src/new/improved_module.py
- **Deleted by**: [Your name]
- **Date**: YYYY-MM-DD
```

**This applies to all contributors and automated processes. No exceptions.**

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Microsoft Graph API** for OneNote integration
- **OpenAI** for powerful language models
- **LangGraph** for intelligent agent framework
- **Rich** for beautiful terminal interfaces
- **MSAL** for secure authentication

## 🆘 Support

- **Documentation**: Check this README and inline code documentation
- **Issues**: [GitHub Issues](../../issues) for bug reports and feature requests
- **Discussions**: [GitHub Discussions](../../discussions) for questions and community

---

**Made with ❤️ for OneNote users who love AI-powered productivity tools**

