# Phase 5 Plan: OneNote Agent Integration with Local Search

## Overview
**Goal**: Integrate the completed LocalOneNoteSearch engine with the OneNoteAgent to enable fast, local search capabilities instead of slow API calls.

**Current Status**: Phase 4 completed LocalOneNoteSearch with 27/27 tests passing, but agent integration is missing.

## Implementation Strategy

### 5.1 Agent Search Integration
**Priority**: P-0 (Critical)  
**Time Estimate**: 2-3 hours  

#### Tasks:
1. **Modify OneNoteAgent** to optionally use LocalOneNoteSearch
2. **Update OneNoteSearchTool** to use local cache when available  
3. **Add fallback mechanism** - use API if local cache is empty
4. **Preserve existing interfaces** - no breaking changes to CLI or agent APIs

#### Implementation Details:

```python
class OneNoteAgent:
    def __init__(self):
        self.local_search = None  # Will be initialized if cache is available
        self.search_tool = OneNoteSearchTool()  # Keep existing API search
        
    async def initialize(self):
        """Initialize with local search if cache is available."""
        try:
            # Check if cache exists and has content
            if await self._has_cached_content():
                self.local_search = LocalOneNoteSearch()
                await self.local_search.initialize()
                logger.info("Local search engine initialized")
            else:
                logger.info("No cached content - using API search")
        except Exception as e:
            logger.warning(f"Local search init failed, using API: {e}")
```

### 5.2 Smart Search Strategy
**Priority**: P-0 (Critical)  
**Time Estimate**: 1-2 hours

#### Hybrid Search Approach:
1. **Primary**: Use local search if available and has relevant content
2. **Fallback**: Use API search if local search fails or returns no results  
3. **Performance**: Log and compare response times between methods

#### Implementation:
```python
async def search_pages(self, query: str, max_results: int = 10) -> OneNoteSearchResponse:
    """Enhanced search using local cache + API fallback."""
    start_time = time.time()
    
    # Try local search first
    if self.local_search:
        try:
            local_results = await self.local_search.search(query, limit=max_results)
            if local_results:
                logger.info(f"Local search found {len(local_results)} results in {time.time() - start_time:.2f}s")
                return self._convert_local_to_response(local_results, query)
        except Exception as e:
            logger.warning(f"Local search failed, falling back to API: {e}")
    
    # Fallback to API search
    logger.info("Using API search (no local results or local search unavailable)")
    return await self._api_search_pages(query, max_results)
```

### 5.3 Cache Status Integration  
**Priority**: P-1 (High)  
**Time Estimate**: 30 minutes

#### Add cache status to agent:
- **Cache size**: Number of indexed pages
- **Last sync**: When cache was last updated  
- **Search mode**: "local", "api", or "hybrid"

### 5.4 Testing & Validation
**Priority**: P-0 (Critical)  
**Time Estimate**: 1 hour

#### Test Coverage:
1. **Unit Tests**: Agent initialization with/without cache
2. **Integration Tests**: Local search + API fallback behavior  
3. **Performance Tests**: Response time comparisons
4. **Regression Tests**: Ensure existing functionality works

## Success Criteria
- ✅ **Performance**: Local search responses under 500ms (vs 5+ seconds API)
- ✅ **Reliability**: Graceful fallback to API when local search fails
- ✅ **Compatibility**: No breaking changes to existing CLI or agent interfaces  
- ✅ **Coverage**: All existing search scenarios work with local cache

## Files to Modify
1. **src/agents/onenote_agent.py** - Add local search integration
2. **src/tools/onenote_search.py** - Optional local search usage
3. **tests/test_agent_local_search.py** - New integration tests
4. **src/config/settings.py** - Add cache preference settings

## Implementation Phases

### Phase 5.1: Basic Integration (1-2 hours)
- Add LocalOneNoteSearch to OneNoteAgent
- Implement basic local search with API fallback
- Test with existing search scenarios

### Phase 5.2: Optimization & Polish (1-2 hours)  
- Performance monitoring and logging
- Cache status integration
- Error handling improvements
- Comprehensive testing

This represents the missing piece from Phase 4 - the actual integration of our excellent local search engine with the agent that users interact with.
