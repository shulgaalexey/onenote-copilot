name: "Web Search Integration: Enhance OneNote Responses with Brave Search"
description: |
  Integrate Brave Search API to enhance OneNote responses with external web search capabilities,
  allowing users to supplement their notes with real-time web information.

## Purpose
Add web search functionality to OneNote Copilot using available mcp_brave tools to provide comprehensive answers combining OneNote content with current web information.

## Goal
Enhance the OneNote agent to intelligently decide when to supplement note searches with web search, providing users with:
- OneNote content combined with related web information
- Recent updates on topics found in their notes
- External validation of information stored in notes

## Success Criteria
- [ ] Agent intelligently determines when to use web search
- [ ] Brave Search API integrated with proper rate limiting
- [ ] Combined responses show both OneNote and web sources clearly
- [ ] Web search respects user privacy preferences
- [ ] Performance remains optimal with web search addition

## Tasks
```yaml
Task 1: Web Search Tool Integration
INTEGRATE mcp_brave tools:
  - ADD: Brave web search capability to OneNote agent
  - CONFIGURE: API rate limiting and error handling
  - IMPLEMENT: Search decision logic (when to search web vs notes only)

Task 2: Enhanced Agent Logic
UPDATE src/agents/onenote_agent.py:
  - ADD: Web search tool to agent toolkit
  - IMPLEMENT: Decision tree for web search triggers
  - HANDLE: Combined response formatting

Task 3: Response Enhancement
UPDATE src/models/responses.py:
  - ADD: WebSearchResult model for external results
  - EXTEND: OneNoteSearchResponse to include web sources
  - IMPLEMENT: Source attribution for web vs note content

Task 4: CLI Integration
UPDATE src/cli/formatting.py:
  - ADD: Web search result formatting
  - IMPLEMENT: Clear source distinction (Notes vs Web)
  - STYLE: Consistent presentation of combined results
```

## Integration Points
```yaml
BRAVE_SEARCH:
  - tools: ["mcp_brave_brave_web_search", "mcp_brave_brave_local_search"]
  - rate_limits: "Respect API limits in tool calls"
  
DECISION_LOGIC:
  - triggers: ["recent info", "current events", "verify information"]
  - user_control: "Allow disabling web search per query"
```

## Validation
```powershell
# Test web search integration
python -c "
from src.agents.onenote_agent import OneNoteAgent
agent = OneNoteAgent()
# Test query that should trigger web search
result = agent.process_query('What are recent developments in AI that relate to my Python notes?')
print(result)
"
```

## Confidence Score: 8/10
Clear integration path with existing tools, main complexity in decision logic for when to search web.
