# OneNote Copilot CLI - QA Testing Guide 🧪

> **Comprehensive Testing Guide for QA Engineers**
> Last Updated: July 21, 2025
> Application Version: 1.0.0

## 📋 Overview

OneNote Copilot is an AI-powered CLI application that provides natural language search capabilities for Microsoft OneNote content. The application features a revolutionary local cache system, semantic search with vector embeddings, and a beautiful Rich-based terminal interface.

### Key Features to Test
- ✅ **Local Cache System** - Lightning-fast search with <500ms response times
- ✅ **Semantic Search** - Vector-based search using OpenAI embeddings
- ✅ **Microsoft Authentication** - OAuth2 flow with secure token caching
- ✅ **Rich CLI Interface** - Interactive chat with streaming responses
- ✅ **Hybrid Search Strategy** - Local-first with API fallback
- ✅ **Content Indexing** - Full-text search with SQLite FTS5

---

## 🔧 Test Environment Setup

### Prerequisites
- **Windows 11** with PowerShell 7
- **Python 3.11+** installed
- **Microsoft Account** with OneNote content
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))
- **Internet Connection** for initial setup and authentication

### Installation Steps

1. **Clone and Setup Environment:**
   ```powershell
   git clone <repository-url>
   cd onenote-copilot
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   ```powershell
   $env:OPENAI_API_KEY = "sk-your-openai-api-key-here"
   ```

3. **Verify Installation:**
   ```powershell
   python -m src.main --info
   ```

---

## 🎯 Critical Test Areas

## 1. Authentication Testing 🔐

### Test Case: First-Time Authentication
**Priority**: P0 (Critical)
**Expected Result**: Successful OAuth2 flow and token caching

```powershell
# Test authentication only
python -m src.main --auth-only
```

**Validation Points:**
- [ ] Browser opens automatically for Microsoft login
- [ ] User can log in with Microsoft credentials
- [ ] Success message: "✅ Authentication successful!"
- [ ] Token file created: `data/token_cache.bin`
- [ ] No error messages displayed

### Test Case: Token Reuse
**Priority**: P1 (High)
**Expected Result**: Application uses cached token without re-authentication

```powershell
# Run again - should not prompt for login
python -m src.main --auth-only
```

**Validation Points:**
- [ ] No browser window opens
- [ ] Immediate success message
- [ ] Token cache file unchanged

### Test Case: Invalid Token Handling
**Priority**: P1 (High)
**Expected Result**: Graceful re-authentication when token expires

```powershell
# Delete token cache to simulate expiration
Remove-Item -Path "data\token_cache.bin" -ErrorAction SilentlyContinue
python -m src.main --auth-only
```

---

## 2. CLI Interface Testing 💻

### Test Case: Application Startup
**Priority**: P0 (Critical)
**Expected Result**: Clean startup with welcome message

```powershell
python -m src.main
```

**Validation Points:**
- [ ] Rich-formatted welcome message displays
- [ ] Application version shown (1.0.0)
- [ ] Authentication occurs automatically
- [ ] Chat prompt appears: `>`
- [ ] No error messages or warnings

### Test Case: Help System
**Priority**: P1 (High)
**Expected Result**: Comprehensive help information

```powershell
# In the interactive CLI
/help
```

**Validation Points:**
- [ ] All available commands listed:
  - `/help` - Show help information
  - `/notebooks` - List OneNote notebooks
  - `/recent` - Show recent pages
  - `/content <title>` - Display page content
  - `/index [recent]` - Index content for search
  - `/semantic <query>` - Semantic search
  - `/starters` - Show conversation starters
  - `/clear` - Clear conversation history
  - `/quit` or `/exit` - Exit application
- [ ] Command descriptions are clear and accurate
- [ ] Examples provided where helpful

### Test Case: Command Recognition
**Priority**: P1 (High)
**Expected Result**: Correct identification of commands vs. queries

```powershell
# Test various inputs in CLI
/help        # Should execute help command
help         # Should be treated as search query
/unknown     # Should show unknown command error
hello world  # Should be treated as search query
```

---

## 3. Local Cache System Testing 🗄️

### Test Case: Initial Cache Setup
**Priority**: P0 (Critical)
**Expected Result**: Cache directory created and populated

```powershell
# Check if cache directory exists
ls data/onenote_cache/

# View cache status
python -m src.main --info
```

**Validation Points:**
- [ ] `data/onenote_cache/` directory exists
- [ ] Cache database files created
- [ ] System info shows cache statistics
- [ ] Cache size reported (typically 10-100MB)

### Test Case: Cache Performance
**Priority**: P0 (Critical)
**Expected Result**: Sub-500ms search response times

**Test Method:**
1. Start interactive CLI
2. Perform search query: `Find my meeting notes`
3. Measure response time from query submission to first result

**Validation Points:**
- [ ] Search completes in <500ms
- [ ] Results display immediately
- [ ] No timeout or performance warnings
- [ ] Local cache is used (verify in logs)

### Test Case: Cache Synchronization
**Priority**: P1 (High)
**Expected Result**: Cache stays updated with OneNote changes

```powershell
# Test cache sync (if implemented)
python -m src.main --sync-cache
```

**Note**: This feature may be in development. Verify current implementation status.

---

## 4. Search Functionality Testing 🔍

### Test Case: Natural Language Search
**Priority**: P0 (Critical)
**Expected Result**: Relevant results for conversational queries

**Test Queries:**
```
> What did I write about project planning last week?
> Show me all my meeting notes from December
> Find notes about Python development
> Tell me about my research on AI agents
```

**Validation Points:**
- [ ] Results returned within 5 seconds
- [ ] Relevant content found and displayed
- [ ] Page titles and content previews shown
- [ ] Source links provided to OneNote pages
- [ ] Search type indicated (local/semantic/API)

### Test Case: Semantic Search Command
**Priority**: P1 (High)
**Expected Result**: Vector-based conceptual search

```powershell
# In interactive CLI
/semantic vibe coding
/semantic my thoughts on AI
/semantic project management ideas
```

**Validation Points:**
- [ ] Semantic search engine available
- [ ] Similarity scores displayed (0.0-1.0)
- [ ] Content chunks shown with previews
- [ ] Results ranked by relevance
- [ ] Search type marked as "semantic"

### Test Case: Content Display Command
**Priority**: P1 (High)
**Expected Result**: Full page content retrieval

```powershell
# In interactive CLI
/content Meeting Notes
/content Project Planning
/content "Page Title with Spaces"
```

**Validation Points:**
- [ ] Page content displays in full
- [ ] Markdown formatting preserved
- [ ] Error handling for non-existent pages
- [ ] Case-insensitive title matching
- [ ] Clear error messages for missing pages

---

## 5. Indexing System Testing 📚

### Test Case: Content Indexing
**Priority**: P1 (High)
**Expected Result**: Content successfully indexed for search

```powershell
# Test indexing commands
python -m src.main index --status
python -m src.main index --initial --limit 10
python -m src.main index --sync --recent-days 7
```

**Validation Points:**
- [ ] Status command shows current index state
- [ ] Initial indexing processes pages successfully
- [ ] Progress indicators work correctly
- [ ] Success/failure counts accurate
- [ ] Index statistics updated

### Test Case: Interactive Indexing
**Priority**: P1 (High)
**Expected Result**: Indexing available from CLI chat

```powershell
# In interactive CLI
/index
/index recent
```

**Validation Points:**
- [ ] Command executes without errors
- [ ] Progress shown during indexing
- [ ] Results summary displayed
- [ ] Index statistics updated

---

## 6. Error Handling Testing ⚠️

### Test Case: Network Connectivity Issues
**Priority**: P1 (High)
**Expected Result**: Graceful degradation to offline mode

**Test Method:**
1. Disconnect internet connection
2. Start application
3. Attempt search queries

**Validation Points:**
- [ ] Application starts successfully
- [ ] Local cache search still works
- [ ] Clear error messages for API failures
- [ ] No crashes or hangs
- [ ] Offline capabilities clearly communicated

### Test Case: Invalid API Key
**Priority**: P1 (High)
**Expected Result**: Clear error message and guidance

```powershell
$env:OPENAI_API_KEY = "invalid-key"
python -m src.main
```

**Validation Points:**
- [ ] Clear error message about invalid API key
- [ ] Instructions for obtaining valid key
- [ ] Application exits gracefully
- [ ] No sensitive information leaked

### Test Case: Corrupted Cache
**Priority**: P2 (Medium)
**Expected Result**: Cache rebuild or clear error handling

**Test Method:**
1. Corrupt cache files manually
2. Start application
3. Attempt search operations

**Validation Points:**
- [ ] Corruption detected automatically
- [ ] Option to rebuild cache presented
- [ ] Fallback to API search works
- [ ] No data loss or crashes

---

## 7. Data Management Testing 💾

### Test Case: Multi-User Support
**Priority**: P1 (High)
**Expected Result**: User data isolation and cleanup

```powershell
# Test logout functionality
python -m src.main logout
```

**Validation Points:**
- [ ] User data cleared securely
- [ ] Cache directories cleaned
- [ ] Token cache removed
- [ ] Vector index cleared
- [ ] No residual user data remains

### Test Case: Data Storage Limits
**Priority**: P2 (Medium)
**Expected Result**: Appropriate handling of large datasets

**Test Method:**
1. Test with large OneNote account (100+ pages)
2. Monitor disk usage and performance
3. Verify search still works efficiently

**Validation Points:**
- [ ] Disk usage reasonable (<500MB typical)
- [ ] Search performance maintained
- [ ] Memory usage stable
- [ ] No storage warnings or errors

---

## 8. Integration Testing 🔗

### Test Case: Microsoft Graph API Integration
**Priority**: P0 (Critical)
**Expected Result**: Successful data retrieval from OneNote

```powershell
# In interactive CLI
/notebooks
/recent
```

**Validation Points:**
- [ ] Notebooks list displays correctly
- [ ] Recent pages shown with dates
- [ ] API rate limits respected
- [ ] Error handling for API failures
- [ ] Authentication tokens refreshed as needed

### Test Case: OpenAI API Integration
**Priority**: P1 (High)
**Expected Result**: Semantic search and AI responses work

**Test Method:**
1. Perform queries requiring AI processing
2. Use semantic search features
3. Verify embedding generation works

**Validation Points:**
- [ ] AI responses generated successfully
- [ ] Embeddings created for new content
- [ ] API usage optimized with caching
- [ ] Rate limiting handled gracefully

---

## 9. Performance Testing ⚡

### Test Case: Search Response Times
**Priority**: P0 (Critical)
**Expected Result**: Fast search across different scenarios

**Performance Targets:**
- Local cache search: <500ms
- Semantic search: <5 seconds
- API fallback search: <15 seconds
- Application startup: <10 seconds

**Test Scenarios:**
- Small queries (1-3 words)
- Complex queries (10+ words)
- No results queries
- Large result sets (20+ matches)

### Test Case: Memory Usage
**Priority**: P1 (High)
**Expected Result**: Stable memory consumption

**Test Method:**
1. Monitor memory usage during extended session
2. Perform multiple search operations
3. Check for memory leaks

**Validation Points:**
- [ ] Memory usage <500MB typically
- [ ] No significant memory leaks
- [ ] Stable performance over time
- [ ] Garbage collection working properly

---

## 10. User Experience Testing 👤

### Test Case: First-Time User Experience
**Priority**: P0 (Critical)
**Expected Result**: Smooth onboarding for new users

**Test Scenario:**
1. Fresh installation with no prior configuration
2. Follow setup instructions in README
3. Complete first authentication
4. Perform first search

**Validation Points:**
- [ ] Setup instructions clear and complete
- [ ] Authentication flow intuitive
- [ ] Welcome message helpful
- [ ] First search succeeds
- [ ] No confusing error messages

### Test Case: Conversation Flow
**Priority**: P1 (High)
**Expected Result**: Natural chat-like interaction

**Test Method:**
1. Start conversation with greeting
2. Ask follow-up questions
3. Use various command types
4. Test conversation history

**Validation Points:**
- [ ] Context maintained across queries
- [ ] History accessible with `/clear`
- [ ] Responses feel conversational
- [ ] Commands blend naturally with chat

---

## 🚨 Critical Bug Categories

### P0 Bugs (Stop Ship)
- Application crashes or fails to start
- Authentication completely broken
- Search returns no results when content exists
- Data corruption or loss
- Security vulnerabilities

### P1 Bugs (High Priority)
- Significant performance degradation
- Features not working as documented
- Poor error messages or user experience
- Memory leaks or resource issues

### P2 Bugs (Medium Priority)
- Minor UI/formatting issues
- Edge case handling problems
- Documentation inconsistencies
- Non-critical feature gaps

---

## 📊 Test Execution Tracking

### Environment Information
- **Windows Version**: _______________
- **Python Version**: _______________
- **PowerShell Version**: _______________
- **OpenAI API Access**: ✅/❌
- **Microsoft Account Type**: _______________
- **OneNote Content Volume**: _______________ pages

### Test Execution Log

| Test Case | Status | Notes | Date | Tester |
|-----------|--------|-------|------|--------|
| Authentication - First Time | ⏳ | | | |
| Authentication - Token Reuse | ⏳ | | | |
| CLI Startup | ⏳ | | | |
| Help System | ⏳ | | | |
| Local Cache Performance | ⏳ | | | |
| Natural Language Search | ⏳ | | | |
| Semantic Search | ⏳ | | | |
| Content Indexing | ⏳ | | | |
| Error Handling | ⏳ | | | |
| Multi-User Support | ⏳ | | | |
| Performance Targets | ⏳ | | | |

**Legend**: ✅ Pass | ❌ Fail | ⏳ Pending | 🔄 In Progress | ⚠️ Issue

---

## 📝 Bug Reporting Template

### Bug Report Format

**Title**: [Component] Brief description of issue

**Priority**: P0/P1/P2

**Environment**:
- Windows Version:
- Python Version:
- Application Version:

**Steps to Reproduce**:
1.
2.
3.

**Expected Behavior**:
...

**Actual Behavior**:
...

**Screenshots/Logs**:
...

**Workaround** (if any):
...

---

## 🔍 Testing Tools and Commands

### Useful Testing Commands

```powershell
# System information
python -m src.main --info

# Version check
python -m src.main --version

# Debug mode (verbose logging)
python -m src.main --debug

# Authentication only
python -m src.main --auth-only

# Index status
python -m src.main index --status

# Run all tests (for developers)
python -m pytest tests/ -v --cov=src --cov-report=term-missing > TEST_RUN.md 2>&1; Add-Content -Path "TEST_RUN.md" -Value "%TESTS FINISHED%"
```

### Log File Locations
- **Application Logs**: `logs/onenote_copilot.log`
- **Test Results**: `TEST_RUN.md` (temporary)
- **Cache Data**: `data/onenote_cache/`
- **Vector Store**: `data/vector_store/`

---

## 📚 Additional Resources

### Documentation Files
- `README.md` - Setup and usage instructions
- `PROGRESS.md` - Development progress tracking
- `docs/PYTEST_STARTUP_OPTIMIZATION.md` - Testing optimization guide
- `prompts/PLANNING.md` - Project architecture overview

### Support Commands
```powershell
# Get help
python -m src.main --help

# Check dependencies
pip check

# View logs
Get-Content logs/onenote_copilot.log -Tail 50

# Monitor cache size
Get-ChildItem -Recurse data/ | Measure-Object -Property Length -Sum
```

---

## ✅ Final Testing Checklist

Before approving the release, ensure:

- [ ] All P0 test cases pass
- [ ] Performance targets met
- [ ] Authentication flow works smoothly
- [ ] Search functionality reliable
- [ ] Error handling graceful
- [ ] Documentation accurate
- [ ] Multi-user support functional
- [ ] No data corruption or loss
- [ ] Resource usage reasonable
- [ ] User experience positive

---

**🎯 Success Criteria**: OneNote Copilot should provide a fast, reliable, and intuitive natural language search experience for OneNote content, with sub-500ms local search performance and seamless Microsoft integration.

**📞 Contact**: For testing questions or issues, refer to the project documentation or create issues in the repository.
