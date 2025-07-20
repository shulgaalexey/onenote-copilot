"""
Integration tests for OneNoteContentFetcher.

Tests the real implementation with proper initialization and basic functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.storage.onenote_fetcher import OneNoteContentFetcher
from src.storage.cache_manager import OneNoteCacheManager
from src.tools.onenote_search import OneNoteSearchTool
from src.models.cache import SyncType, SyncStatus


class TestOneNoteContentFetcherIntegration:
    """Test real OneNoteContentFetcher integration."""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create a mock cache manager."""
        cache_manager = MagicMock(spec=OneNoteCacheManager)
        cache_manager.cache_exists = MagicMock(return_value=False)  # Sync method, not async
        cache_manager.initialize_user_cache = AsyncMock()
        cache_manager.update_cache_metadata = AsyncMock()
        cache_manager.store_page_content = AsyncMock()
        cache_manager.get_cached_page = AsyncMock(return_value=None)
        return cache_manager

    @pytest.fixture
    def mock_onenote_search(self):
        """Create a mock OneNoteSearchTool."""
        search_tool = MagicMock(spec=OneNoteSearchTool)
        
        # Mock authenticator
        mock_authenticator = MagicMock()
        mock_authenticator.get_valid_token = AsyncMock(return_value="fake_token")
        search_tool.authenticator = mock_authenticator
        
        # Mock methods
        search_tool.get_notebooks = AsyncMock(return_value=[
            {"id": "nb1", "displayName": "Test Notebook 1"},
            {"id": "nb2", "displayName": "Test Notebook 2"}
        ])
        
        search_tool._get_all_sections = AsyncMock(return_value=[
            {"id": "sec1", "displayName": "Section 1", "parentNotebook": {"id": "nb1"}},
            {"id": "sec2", "displayName": "Section 2", "parentNotebook": {"id": "nb1"}}
        ])
        
        search_tool._get_pages_from_section = AsyncMock(return_value=[])
        
        # Mock properties
        search_tool.base_url = "https://graph.microsoft.com/v1.0"
        search_tool.timeout = 30
        
        return search_tool

    def test_initialization(self, mock_cache_manager):
        """Test that OneNoteContentFetcher can be initialized."""
        fetcher = OneNoteContentFetcher(cache_manager=mock_cache_manager)
        
        assert fetcher is not None
        assert fetcher.cache_manager == mock_cache_manager
        assert fetcher.onenote_search is None  # Initially None, injected later

    def test_initialization_with_search(self, mock_cache_manager, mock_onenote_search):
        """Test initialization with both dependencies."""
        fetcher = OneNoteContentFetcher(
            cache_manager=mock_cache_manager,
            onenote_search=mock_onenote_search
        )
        
        assert fetcher is not None
        assert fetcher.cache_manager == mock_cache_manager
        assert fetcher.onenote_search == mock_onenote_search

    @pytest.mark.asyncio
    async def test_get_all_notebooks(self, mock_cache_manager, mock_onenote_search):
        """Test _get_all_notebooks method."""
        fetcher = OneNoteContentFetcher(
            cache_manager=mock_cache_manager,
            onenote_search=mock_onenote_search
        )
        
        notebooks = await fetcher._get_all_notebooks()
        
        assert len(notebooks) == 2
        assert notebooks[0]["displayName"] == "Test Notebook 1"
        mock_onenote_search.get_notebooks.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_sections(self, mock_cache_manager, mock_onenote_search):
        """Test _get_all_sections method."""
        fetcher = OneNoteContentFetcher(
            cache_manager=mock_cache_manager,
            onenote_search=mock_onenote_search
        )
        
        sections = await fetcher._get_all_sections("nb1")
        
        assert len(sections) == 2  # Both sections belong to nb1
        assert sections[0]["displayName"] == "Section 1"
        mock_onenote_search._get_all_sections.assert_called_once_with("fake_token")

    @pytest.mark.asyncio 
    async def test_get_pages_from_section(self, mock_cache_manager, mock_onenote_search):
        """Test _get_pages_from_section method."""
        fetcher = OneNoteContentFetcher(
            cache_manager=mock_cache_manager,
            onenote_search=mock_onenote_search
        )
        
        pages = await fetcher._get_pages_from_section("sec1")
        
        assert isinstance(pages, list)  # Should return empty list from mock
        mock_onenote_search._get_pages_from_section.assert_called_once_with("sec1", "fake_token")

    @pytest.mark.asyncio
    async def test_fetch_all_content_basic(self, mock_cache_manager, mock_onenote_search):
        """Test basic fetch_all_content flow."""
        fetcher = OneNoteContentFetcher(
            cache_manager=mock_cache_manager,
            onenote_search=mock_onenote_search
        )
        
        result = await fetcher.fetch_all_content("test_user")
        
        # Verify basic structure
        assert result.sync_type == SyncType.FULL
        assert result.status in [SyncStatus.COMPLETED, SyncStatus.PARTIAL]
        assert result.statistics.total_time_seconds >= 0

        # Verify cache operations were called
        mock_cache_manager.initialize_user_cache.assert_called_once_with("test_user")
        assert mock_cache_manager.update_cache_metadata.call_count >= 2  # Start and end

    @pytest.mark.asyncio
    async def test_error_handling_no_search(self, mock_cache_manager):
        """Test error handling when no OneNoteSearch is provided."""
        fetcher = OneNoteContentFetcher(cache_manager=mock_cache_manager)
        
        result = await fetcher.fetch_all_content("test_user")
        
        assert result.status == SyncStatus.FAILED
        assert len(result.errors) > 0
        assert "OneNoteSearch instance not provided" in str(result.errors)

    def test_extract_text_from_html(self, mock_cache_manager):
        """Test HTML text extraction."""
        fetcher = OneNoteContentFetcher(cache_manager=mock_cache_manager)
        
        html = "<h1>Title</h1><p>This is a paragraph with <strong>bold</strong> text.</p>"
        text = fetcher._extract_text_from_html(html)
        
        assert "Title" in text
        assert "This is a paragraph with bold text." in text
        assert "<h1>" not in text
        assert "<p>" not in text

    def test_extract_text_from_empty_html(self, mock_cache_manager):
        """Test HTML text extraction with empty input."""
        fetcher = OneNoteContentFetcher(cache_manager=mock_cache_manager)
        
        assert fetcher._extract_text_from_html("") == ""
        assert fetcher._extract_text_from_html(None) == ""
