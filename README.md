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
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o-mini` |
| `ONENOTE_DEBUG` | Enable debug logging | `false` |
| `CLI_COLOR_ENABLED` | Enable colored output | `true` |

### Advanced Configuration

Create a settings file at `~/.config/onenote-copilot/settings.toml`:

```toml
[openai]
model = "gpt-4o-mini"
api_key = "your-key-here"

[microsoft]
client_id = "your-custom-client-id"

[cli]
color_enabled = true
markdown_enabled = true
welcome_enabled = true

[debug]
enabled = false
```

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

Run the test suite:

```bash
# Run all tests
python run_tests.py all

# Run only unit tests
python run_tests.py unit

# Run with coverage
python run_tests.py coverage

# Run linting and type checking
python run_tests.py check
```

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

