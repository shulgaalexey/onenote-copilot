name: "Semantic Search Enhancement: Vector-Based Content Discovery for OneNote Copilot"
description: |
  A comprehensive PRP for implementing semantic search capabilities in the OneNote Copilot CLI to solve the
  problem of poor search relevance when users ask conceptual questions that don't match exact keywords.

## Purpose
Enhance the existing OneNote Copilot CLI with vector-based semantic search capabilities to find conceptually relevant content even when exact keywords aren't present. This addresses the critical issue where queries like "tell me what did I think about vibe coding?" return generic search suggestions instead of finding relevant content.

## Core Principles
1. **Semantic Understanding**: Use embeddings to understand conceptual relationships in content
2. **Autonomous Intelligence**: Agent should find relevant content without requiring user to rephrase queries
3. **Performance First**: Efficient vector storage and retrieval for responsive search
4. **Hybrid Approach**: Combine semantic search with keyword search for optimal recall
5. **User Experience**: Seamless integration that improves search without adding complexity
6. **Quality Over Speed**: Prioritize finding relevant content over fast but irrelevant results

---

## Goal
Transform the OneNote Copilot from a keyword-dependent search tool into an intelligent semantic search assistant that can:
- Find conceptually related content even without exact keyword matches
- Understand user intent from natural language queries
- Provide autonomous search expansion when initial results are limited
- Rank results by semantic relevance to user queries
- Maintain fast response times through efficient vector operations

## Why
- **Current Problem**: Users get generic search suggestions instead of their actual content
- **Business Value**: Dramatically improves search effectiveness and user satisfaction
- **Technical Innovation**: Demonstrates advanced AI search patterns with real-world data
- **User Experience**: Eliminates frustration of failed searches and manual query refinement

## What
A semantic search enhancement system with:
- Vector embedding generation and storage for OneNote content
- Semantic similarity search using cosine similarity
- Intelligent query processing and understanding
- Hybrid search combining keyword and vector approaches
- Relevance ranking and result optimization
- Efficient caching and incremental updates

### Success Criteria
- [ ] Users can find content using conceptual queries without exact keywords
- [ ] Search queries like "vibe coding" return relevant content about coding philosophy
- [ ] Agent autonomously expands searches when needed instead of suggesting user changes
- [ ] Semantic search integrates seamlessly with existing keyword search
- [ ] Vector storage is efficient and responsive (under 5 seconds search times)
- [ ] System handles large OneNote repositories without performance degradation

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- url: https://platform.openai.com/docs/guides/embeddings
  why: OpenAI embeddings API for generating text vectors with best practices

- url: https://docs.trychroma.com/getting-started
  why: ChromaDB vector database for efficient storage and similarity search

- url: https://python.langchain.com/docs/modules/data_connection/text_splitters/
  why: LangChain text splitters for optimal content chunking strategies

- url: https://learn.microsoft.com/en-us/graph/api/onenote-page-get
  why: OneNote page content retrieval for embedding generation

- url: https://numpy.org/doc/stable/reference/generated/numpy.dot.html
  why: Vector similarity calculations using cosine similarity

- url: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html
  why: Alternative cosine similarity implementation for relevance ranking

- file: prompts/INITIAL.md
  why: Original feature requirements and OneNote integration specifications

- file: prompts/PRPs/OneNote_Copilot_CLI.md
  why: Existing CLI implementation that semantic search will enhance
```

### Problem Analysis
The current OneNote Copilot CLI suffers from a critical limitation: when users ask conceptual questions like "tell me what did I think about vibe coding?", the system fails to find relevant content and instead provides generic search suggestions. This occurs because:

1. **Keyword Dependency**: Current search relies on exact keyword matching
2. **No Semantic Understanding**: System cannot understand conceptual relationships
3. **Poor User Experience**: Users get suggestions to rephrase instead of their actual content
4. **Limited Autonomy**: Agent cannot intelligently expand searches or find related content

### Current Codebase Integration Points
```powershell
# Existing structure that semantic search will enhance
src/
├── agents/
│   └── onenote_agent.py           # Main agent - needs semantic search tool integration
├── tools/
│   ├── onenote_search.py          # Current keyword search - needs semantic enhancement
│   └── onenote_content.py         # Content retrieval - needs embedding generation
└── models/
    ├── onenote.py                 # OneNote models - needs embedding metadata
    └── responses.py               # Response models - needs relevance scoring
```

### Target Architecture Addition
```powershell
# New components for semantic search
src/
├── search/
│   ├── __init__.py                # Search package initialization
│   ├── embeddings.py              # Embedding generation and management
│   ├── semantic_search.py         # Vector-based search implementation
│   ├── query_processor.py         # Query understanding and enhancement
│   ├── content_chunker.py         # Intelligent content segmentation
│   └── relevance_ranker.py        # Result ranking and filtering
├── storage/
│   ├── __init__.py                # Storage package initialization
│   ├── vector_store.py            # Vector database interface
│   ├── embedding_cache.py         # Embedding persistence and caching
│   └── content_indexer.py         # Content indexing and updates
└── config/
    └── search_settings.py         # Semantic search configuration
```

## Technical Requirements

### Core Dependencies
```toml
# Additional requirements for semantic search
openai = "^1.3.0"                  # Embeddings API
chromadb = "^0.4.18"               # Vector database
tiktoken = "^0.5.2"                # Token counting for chunking
numpy = "^1.24.0"                  # Vector operations
scikit-learn = "^1.3.0"            # Similarity calculations
langchain-text-splitters = "^0.0.1" # Content chunking
```

### Environment Configuration
```bash
# Semantic search settings for .env.local
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
VECTOR_DB_PATH=./data/vector_store
SEMANTIC_SEARCH_THRESHOLD=0.75
MAX_CHUNKS_PER_PAGE=5
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
ENABLE_HYBRID_SEARCH=true
CACHE_EMBEDDINGS=true
```

### Technical Performance Requirements
- Vector search response time: < 5 second for typical queries
- Embedding generation: Batch processing for efficiency
- Memory usage: < 500MB for moderate OneNote repositories
- Storage: Efficient compression for embedding vectors
- Scalability: Handle 1000+ OneNote pages without degradation

## Implementation Strategy

### Phase 1: Core Semantic Search Infrastructure
1. **Embedding Generation System**:
   - OpenAI embeddings API integration
   - Intelligent content chunking for OneNote pages
   - Batch processing for efficiency
   - Error handling for API limits

2. **Vector Storage Implementation**:
   - ChromaDB setup and configuration
   - Metadata storage for content attribution
   - Efficient indexing and retrieval
   - Persistence between sessions

3. **Basic Semantic Search**:
   - Query embedding generation
   - Cosine similarity search
   - Result filtering by relevance threshold
   - Integration with existing search tools

### Phase 2: Intelligent Query Processing
1. **Query Understanding**:
   - Intent detection from natural language
   - Query expansion for better recall
   - Synonym and concept mapping
   - Context-aware search strategies

2. **Hybrid Search Implementation**:
   - Combination of keyword and semantic search
   - Intelligent result merging
   - Relevance score calculation
   - Fallback strategies for edge cases

### Phase 3: Advanced Features
1. **Content Indexing Optimization**:
   - Incremental updates for new content
   - Smart chunking based on content structure
   - Metadata enrichment for better search
   - Background indexing processes

2. **Search Enhancement**:
   - Query suggestion based on content
   - Related content discovery
   - Historical query learning
   - Performance monitoring and optimization

## Detailed Implementation Plan

### 1. Embedding System (src/search/embeddings.py)
```python
# Key functions to implement
async def generate_embeddings(content: str) -> List[float]
async def batch_generate_embeddings(contents: List[str]) -> List[List[float]]
async def embed_onenote_page(page: OneNotePage) -> List[EmbeddedChunk]
async def update_page_embeddings(page_id: str) -> None
```

### 2. Vector Storage (src/storage/vector_store.py)
```python
# Key functions to implement
async def store_embeddings(chunks: List[EmbeddedChunk]) -> None
async def search_similar(query_embedding: List[float], limit: int) -> List[SearchResult]
async def delete_page_embeddings(page_id: str) -> None
async def get_storage_stats() -> StorageStats
```

### 3. Semantic Search (src/search/semantic_search.py)
```python
# Key functions to implement
async def semantic_search(query: str, limit: int) -> List[SearchResult]
async def hybrid_search(query: str, limit: int) -> List[SearchResult]
async def search_with_filters(query: str, filters: Dict) -> List[SearchResult]
async def rank_results(results: List[SearchResult], query: str) -> List[SearchResult]
```

### 4. Query Processing (src/search/query_processor.py)
```python
# Key functions to implement
async def process_query(query: str) -> ProcessedQuery
async def expand_query(query: str) -> List[str]
async def detect_intent(query: str) -> QueryIntent
async def suggest_alternatives(query: str, results: List) -> List[str]
```

## Testing Strategy

### Unit Tests
- Embedding generation accuracy and consistency
- Vector storage operations (CRUD)
- Similarity search correctness
- Query processing edge cases
- Result ranking algorithms

### Integration Tests
- End-to-end semantic search workflow
- OneNote API integration with embeddings
- Hybrid search combination accuracy
- Performance under load
- Error handling and recovery

### Performance Tests
- Large repository handling
- Search response times
- Memory usage patterns
- Concurrent user scenarios
- Batch processing efficiency

## Quality Gates

### Functional Requirements
- [ ] Semantic search finds relevant content for conceptual queries
- [ ] Hybrid search improves results over keyword-only search
- [ ] System handles OneNote API rate limits gracefully
- [ ] Vector storage persists between application restarts
- [ ] Query processing enhances user queries effectively

### Performance Requirements
- [ ] Search response time < 5 seconds for 95% of queries
- [ ] Embedding generation processes pages efficiently in batches
- [ ] Memory usage remains under 500MB for typical repositories
- [ ] Vector database scales to 10,000+ embedded chunks
- [ ] System recovers gracefully from API failures

### Code Quality Requirements
- [ ] All functions have comprehensive type hints
- [ ] Test coverage > 85% for semantic search components
- [ ] Code passes ruff linting and mypy type checking
- [ ] Functions follow single responsibility principle
- [ ] Error handling covers all identified failure modes

## Success Validation

### User Experience Tests
1. **Conceptual Query Test**: "tell me what did I think about vibe coding?"
   - Expected: Returns relevant content about coding philosophy/approaches
   - Current: Returns generic search suggestions
   - Success: User gets their actual thoughts on the topic

2. **Related Concept Test**: "show me my thoughts on developer productivity"
   - Expected: Finds content about efficiency, tools, workflows
   - Success: Discovers content even if exact phrase isn't used

3. **Intent Understanding Test**: "what was I researching about AI last month?"
   - Expected: Understands temporal and topical constraints
   - Success: Filters by timeframe and finds AI-related content

### Technical Validation
1. **Performance Benchmarks**:
   - Measure search response times across repository sizes
   - Monitor memory usage during embedding operations
   - Test concurrent user scenarios

2. **Accuracy Measurements**:
   - Compare semantic vs keyword search recall rates
   - Measure relevance of top-N results
   - Test query understanding accuracy

3. **Reliability Tests**:
   - API failure recovery scenarios
   - Large batch processing stability
   - Long-running session performance

## Implementation Notes

### Critical Success Factors
1. **Embedding Quality**: Use appropriate OpenAI model for domain
2. **Chunking Strategy**: Balance between context and granularity
3. **Similarity Threshold**: Tune for optimal precision/recall
4. **Hybrid Balance**: Weight semantic vs keyword appropriately
5. **Caching Strategy**: Minimize API calls while maintaining freshness

### Common Pitfalls to Avoid
1. **Over-chunking**: Too small chunks lose context
2. **Under-chunking**: Too large chunks reduce precision
3. **Threshold Too High**: Misses relevant but not perfect matches
4. **Threshold Too Low**: Returns too many irrelevant results
5. **API Rate Limits**: Batch operations without proper throttling

### Integration Considerations
1. **Backward Compatibility**: Maintain existing keyword search functionality
2. **Graceful Degradation**: Fall back to keyword search if semantic fails
3. **User Feedback**: Capture search effectiveness for continuous improvement
4. **Configuration**: Allow tuning of semantic search parameters
5. **Monitoring**: Track search performance and user satisfaction

This PRP provides a comprehensive roadmap for implementing semantic search that will transform the OneNote Copilot from a keyword-dependent tool into an intelligent content discovery assistant.
