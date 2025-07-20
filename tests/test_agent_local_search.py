"""
Integration tests for OneNote Agent with local search capabilities.

Tests the agent's ability to use local search when available and fallback
to API search when needed, ensuring seamless operation.
"""

import asyncio
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.onenote_agent import OneNoteAgent
from src.models.cache import CachedPage, CachedPageMetadata
from src.models.onenote import OneNotePage, SemanticSearchResult, ContentChunk
from src.models.responses import OneNoteSearchResponse
from src.storage.local_search import LocalOneNoteSearch


class TestOneNoteAgentLocalSearch:
    """Integration tests for OneNote Agent with local search."""

    @pytest.fixture
    async def temp_cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_settings(self, temp_cache_dir):
        """Mock settings with temporary cache directory."""
        settings = MagicMock()
        settings.onenote_cache_full_path = temp_cache_dir
        settings.semantic_search_limit = 10
        settings.enable_hybrid_search = True
        settings.openai_api_key = "test-key"
        settings.openai_model = "gpt-4"
        settings.openai_temperature = 0.1
        return settings

    @pytest.fixture
    def sample_cached_page(self):
        """Create sample cached page for testing."""
        return CachedPage(
            metadata=CachedPageMetadata(
                id="test-page-001",
                title="Test Page Title",
                created_date_time=datetime(2024, 1, 1, 12, 0, 0),
                last_modified_date_time=datetime(2024, 1, 2, 14, 30, 0),
                parent_section={"id": "section-001", "name": "Test Section"},
                parent_notebook={"id": "notebook-001", "name": "Test Notebook"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/test-page-001/content",
                local_content_path="cache/test-page-001.md",
                local_html_path="cache/test-page-001.html",
                cached_at=datetime.now(),
                last_synced=datetime.now()
            ),
            markdown_content="# Test Page Content\\n\\nThis is a test page with **bold** and *italic* text."
        )

    @pytest.fixture
    async def agent_with_mocks(self, mock_settings, sample_cached_page):
        """Create agent with mocked dependencies."""
        agent = OneNoteAgent(mock_settings)
        
        # Mock authenticator
        agent.authenticator.get_valid_token = AsyncMock(return_value="mock-token")
        agent.authenticator.validate_token = AsyncMock(return_value=True)
        
        # Mock cache manager
        agent._cache_manager = MagicMock()
        agent._cache_manager.cache_root = mock_settings.onenote_cache_full_path
        agent._cache_manager.get_all_cached_pages = AsyncMock(return_value=[sample_cached_page])
        
        # Mock LLM response - patch the private _llm attribute instead of property
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Test AI response based on cached content"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        agent._llm = mock_llm
        
        yield agent

    async def test_agent_initialization_with_cache(self, agent_with_mocks):
        """Test agent initialization when cache is available."""
        agent = agent_with_mocks
        
        # Ensure cache directory exists
        agent.cache_manager.cache_root.mkdir(parents=True, exist_ok=True)
        
        await agent.initialize()
        
        # Verify local search was initialized
        assert agent._local_search_available is True
        assert agent.local_search is not None

    async def test_agent_initialization_without_cache(self, mock_settings):
        """Test agent initialization when no cache is available."""
        agent = OneNoteAgent(mock_settings)
        
        # Mock authenticator
        agent.authenticator.get_valid_token = AsyncMock(return_value="mock-token")
        agent.authenticator.validate_token = AsyncMock(return_value=True)
        
        # Mock empty cache
        agent._cache_manager = MagicMock()
        agent._cache_manager.cache_root = mock_settings.onenote_cache_full_path
        agent._cache_manager.get_all_cached_pages = AsyncMock(return_value=[])
        
        await agent.initialize()
        
        # Verify local search was not initialized
        assert agent._local_search_available is False

    async def test_search_with_local_results(self, agent_with_mocks, sample_cached_page):
        """Test search when local search returns results."""
        agent = agent_with_mocks
        
        # Initialize agent
        agent.cache_manager.cache_root.mkdir(parents=True, exist_ok=True)
        await agent.initialize()
        
        # Mock local search results
        mock_local_result = SemanticSearchResult(
            chunk=ContentChunk(
                id="chunk-1",
                page_id="test-page-001",
                page_title="Test Page Title",
                content="Test page content",
                chunk_index=0,
                start_position=0,
                end_position=100
            ),
            similarity_score=0.9,
            search_type="local_cache_fts",
            rank=1,
            page=OneNotePage(
                id="test-page-001",
                title="Test Page Title",
                content="Test page content",
                createdDateTime=datetime(2024, 1, 1, 12, 0, 0),
                lastModifiedDateTime=datetime(2024, 1, 2, 14, 30, 0)
            )
        )
        
        agent.local_search.search = AsyncMock(return_value=[mock_local_result])
        
        # Perform search
        response = await agent.search_pages("test query", 5)
        
        # Verify response
        assert isinstance(response, OneNoteSearchResponse)
        assert response.search_query_used == "test query"
        assert len(response.sources) == 1
        assert response.sources[0].id == "test-page-001"
        assert response.metadata["search_method"] == "local_cache"
        assert response.metadata["api_calls"] == 0
        
        # Verify local search was called
        agent.local_search.search.assert_called_once_with("test query", limit=5)

    async def test_search_fallback_to_api(self, agent_with_mocks):
        """Test search fallback to API when local search fails or returns no results."""
        agent = agent_with_mocks
        
        # Initialize agent
        agent.cache_manager.cache_root.mkdir(parents=True, exist_ok=True)
        await agent.initialize()
        
        # Mock local search to return no results
        agent.local_search.search = AsyncMock(return_value=[])
        
        # Mock API search tool
        from src.models.onenote import SearchResult
        mock_api_result = SearchResult(
            query="test query",
            pages=[OneNotePage(
                id="api-page-001",
                title="API Result Page",
                content="API search result content",
                createdDateTime=datetime.now(),
                lastModifiedDateTime=datetime.now()
            )],
            total_count=1,
            execution_time=0.5,
            api_calls_made=1
        )
        
        agent.search_tool.search_pages = AsyncMock(return_value=mock_api_result)
        
        # Perform search
        response = await agent.search_pages("test query", 5)
        
        # Verify response uses API results
        assert isinstance(response, OneNoteSearchResponse)
        assert len(response.sources) == 1
        assert response.sources[0].id == "api-page-001"
        assert response.metadata["search_method"] == "api"
        assert response.metadata["api_calls"] == 1
        
        # Verify both searches were called
        agent.local_search.search.assert_called_once_with("test query", limit=5)
        agent.search_tool.search_pages.assert_called_once_with("test query", 5)

    async def test_search_without_local_search_available(self, mock_settings):
        """Test search when local search is not available."""
        agent = OneNoteAgent(mock_settings)
        
        # Mock authenticator
        agent.authenticator.get_valid_token = AsyncMock(return_value="mock-token")
        agent.authenticator.validate_token = AsyncMock(return_value=True)
        
        # Mock empty cache (no local search available)
        agent._cache_manager = MagicMock()
        agent._cache_manager.cache_root = mock_settings.onenote_cache_full_path
        agent._cache_manager.get_all_cached_pages = AsyncMock(return_value=[])
        
        # Mock API search tool
        from src.models.onenote import SearchResult
        mock_api_result = SearchResult(
            query="test query",
            pages=[OneNotePage(
                id="api-page-001",
                title="API Result Page",
                content="API search result content",
                createdDateTime=datetime.now(),
                lastModifiedDateTime=datetime.now()
            )],
            total_count=1,
            execution_time=0.5,
            api_calls_made=1
        )
        
        agent.search_tool.search_pages = AsyncMock(return_value=mock_api_result)
        
        # Mock LLM response - patch the private _llm attribute
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Test AI response from API search"
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        agent._llm = mock_llm
        
        await agent.initialize()
        
        # Perform search
        response = await agent.search_pages("test query", 5)
        
        # Verify response uses API results only
        assert isinstance(response, OneNoteSearchResponse)
        assert response.metadata["search_method"] == "api"
        assert agent._local_search_available is False
        
        # Verify only API search was called
        agent.search_tool.search_pages.assert_called_once_with("test query", 5)

    async def test_get_cache_status(self, agent_with_mocks, sample_cached_page):
        """Test cache status reporting."""
        agent = agent_with_mocks
        
        # Initialize agent
        agent.cache_manager.cache_root.mkdir(parents=True, exist_ok=True)
        await agent.initialize()
        
        # Get cache status
        status = await agent.get_cache_status()
        
        # Verify status
        assert status["local_search_available"] is True
        assert status["cache_directory_exists"] is True
        assert status["cached_pages_count"] == 1
        assert status["search_mode"] == "hybrid"
        assert "last_sync" in status

    async def test_get_cache_status_no_cache(self, mock_settings):
        """Test cache status when no cache is available."""
        agent = OneNoteAgent(mock_settings)
        
        # Mock empty cache
        agent._cache_manager = MagicMock()
        agent._cache_manager.cache_root = mock_settings.onenote_cache_full_path
        agent._cache_manager.get_all_cached_pages = AsyncMock(return_value=[])
        
        # Get cache status
        status = await agent.get_cache_status()
        
        # Verify status
        assert status["local_search_available"] is False
        assert status["cached_pages_count"] == 0
        assert status["search_mode"] == "api"

    async def test_local_search_error_fallback(self, agent_with_mocks):
        """Test fallback to API when local search encounters an error."""
        agent = agent_with_mocks
        
        # Initialize agent
        agent.cache_manager.cache_root.mkdir(parents=True, exist_ok=True)
        await agent.initialize()
        
        # Mock local search to raise error
        from src.storage.local_search import LocalSearchError
        agent.local_search.search = AsyncMock(side_effect=LocalSearchError("Database error"))
        
        # Mock API search tool
        from src.models.onenote import SearchResult
        mock_api_result = SearchResult(
            query="test query",
            pages=[OneNotePage(
                id="api-page-001",
                title="API Fallback Result",
                content="Fallback search result",
                createdDateTime=datetime.now(),
                lastModifiedDateTime=datetime.now()
            )],
            total_count=1,
            execution_time=0.5,
            api_calls_made=1
        )
        
        agent.search_tool.search_pages = AsyncMock(return_value=mock_api_result)
        
        # Perform search
        response = await agent.search_pages("test query", 5)
        
        # Verify fallback worked
        assert isinstance(response, OneNoteSearchResponse)
        assert len(response.sources) == 1
        assert response.sources[0].id == "api-page-001" 
        assert response.metadata["search_method"] == "api"
        
        # Verify both searches were attempted
        agent.local_search.search.assert_called_once()
        agent.search_tool.search_pages.assert_called_once()
