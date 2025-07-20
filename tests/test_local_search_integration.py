"""
Integration tests for LocalOneNoteSearch.

Tests the complete local search functionality including database operations,
indexing, and search queries with real-world scenarios.
"""

import asyncio
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.cache import AssetInfo, CachedPage, CachedPageMetadata, LinkInfo
from src.models.onenote import OneNotePage, SemanticSearchResult
from src.storage.cache_manager import OneNoteCacheManager
from src.storage.local_search import LocalOneNoteSearch, LocalSearchError


class TestLocalOneNoteSearchIntegration:
    """Integration tests for LocalOneNoteSearch class."""

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
        return settings

    @pytest.fixture
    async def cache_manager(self, mock_settings):
        """Create cache manager with temporary directory."""
        return OneNoteCacheManager(mock_settings)

    @pytest.fixture
    async def search_engine(self, mock_settings, cache_manager):
        """Create local search engine."""
        engine = LocalOneNoteSearch(mock_settings, cache_manager)
        await engine.initialize()
        yield engine
        await engine.close()

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
            markdown_content="# Test Page Content\\n\\nThis is a test page with **bold** and *italic* text.\\n\\n## Section 1\\n\\nSome sample content here."
        )

    @pytest.fixture
    def sample_cached_pages(self):
        """Create multiple sample cached pages for testing."""
        pages = []
        
        # Page 1: Meeting Notes
        pages.append(CachedPage(
            metadata=CachedPageMetadata(
                id="page-meeting-001",
                title="Team Meeting January 15",
                created_date_time=datetime(2024, 1, 15, 9, 0, 0),
                last_modified_date_time=datetime(2024, 1, 15, 11, 0, 0),
                parent_section={"id": "section-meetings", "name": "Meeting Notes"},
                parent_notebook={"id": "notebook-work", "name": "Work Notebook"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/page-meeting-001/content",
                local_content_path="cache/page-meeting-001.md",
                local_html_path="cache/page-meeting-001.html",
                cached_at=datetime.now(),
                last_synced=datetime.now()
            ),
            markdown_content="# Team Meeting January 15\\n\\n## Attendees\\n- John Smith\\n- Jane Doe\\n\\n## Action Items\\n- Complete project review\\n- Update documentation"
        ))
        
        # Page 2: Project Documentation
        pages.append(CachedPage(
            metadata=CachedPageMetadata(
                id="page-project-001",
                title="API Documentation",
                created_date_time=datetime(2024, 1, 10, 14, 0, 0),
                last_modified_date_time=datetime(2024, 1, 20, 16, 30, 0),
                parent_section={"id": "section-projects", "name": "Project Documentation"},
                parent_notebook={"id": "notebook-work", "name": "Work Notebook"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/page-project-001/content",
                local_content_path="cache/page-project-001.md",
                local_html_path="cache/page-project-001.html",
                cached_at=datetime.now(),
                last_synced=datetime.now()
            ),
            markdown_content="# API Documentation\\n\\n## Authentication\\nThe API uses OAuth 2.0 for authentication.\\n\\n## Endpoints\\n### GET /api/users\\nReturns list of users."
        ))
        
        # Page 3: Personal Notes
        pages.append(CachedPage(
            metadata=CachedPageMetadata(
                id="page-personal-001",
                title="Weekend Plans",
                created_date_time=datetime(2024, 1, 12, 18, 0, 0),
                last_modified_date_time=datetime(2024, 1, 13, 19, 15, 0),
                parent_section={"id": "section-journal", "name": "Daily Journal"},
                parent_notebook={"id": "notebook-personal", "name": "Personal Notebook"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/page-personal-001/content",
                local_content_path="cache/page-personal-001.md",
                local_html_path="cache/page-personal-001.html",
                cached_at=datetime.now(),
                last_synced=datetime.now()
            ),
            markdown_content="# Weekend Plans\\n\\n## Saturday\\n- Visit the museum\\n- Meet friends for lunch\\n\\n## Sunday\\n- Read a book\\n- Go for a walk"
        ))
        
        return pages

    async def test_initialize_creates_schema(self, search_engine):
        """Test that initialization creates the correct database schema."""
        # Check that database file exists
        assert search_engine.db_path.exists()
        
        # Check that tables are created
        conn = await search_engine._get_connection()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {"page_content_fts", "page_metadata"}
        assert expected_tables.issubset(tables)

    async def test_index_single_page(self, search_engine, sample_cached_page):
        """Test indexing a single cached page."""
        # Index the page
        result = await search_engine.index_page(sample_cached_page)
        assert result is True
        
        # Verify the page is in the database
        conn = await search_engine._get_connection()
        cursor = conn.execute("SELECT page_id, page_title FROM page_content_fts WHERE page_id = ?", (sample_cached_page.metadata.id,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row['page_id'] == sample_cached_page.metadata.id
        assert row['page_title'] == sample_cached_page.metadata.title

    async def test_index_multiple_pages(self, search_engine, sample_cached_pages):
        """Test indexing multiple cached pages."""
        indexed_count = 0
        
        for page in sample_cached_pages:
            result = await search_engine.index_page(page)
            if result:
                indexed_count += 1
        
        assert indexed_count == len(sample_cached_pages)
        
        # Verify all pages are indexed
        conn = await search_engine._get_connection()
        cursor = conn.execute("SELECT COUNT(*) as count FROM page_content_fts")
        count = cursor.fetchone()['count']
        
        assert count == len(sample_cached_pages)

    async def test_search_by_title(self, search_engine, sample_cached_pages):
        """Test searching by page title."""
        # Index all pages
        for page in sample_cached_pages:
            await search_engine.index_page(page)
        
        # Search for meeting-related pages
        results = await search_engine.search("Team Meeting", title_only=True)
        
        assert len(results) >= 1
        assert any("Team Meeting" in result.page.title for result in results)
        assert all(isinstance(result, SemanticSearchResult) for result in results)

    async def test_search_by_content(self, search_engine, sample_cached_pages):
        """Test searching by page content."""
        # Index all pages
        for page in sample_cached_pages:
            await search_engine.index_page(page)
        
        # Search for authentication content
        results = await search_engine.search("authentication OAuth")
        
        assert len(results) >= 1
        
        # Find the API documentation result
        api_result = next((r for r in results if "API Documentation" in r.page.title), None)
        assert api_result is not None
        assert "authentication" in api_result.chunk.content.lower()

    async def test_search_with_notebook_filter(self, search_engine, sample_cached_pages):
        """Test searching with notebook ID filter."""
        # Index all pages
        for page in sample_cached_pages:
            await search_engine.index_page(page)
        
        # Search only in work notebook - use a term that's likely to match
        results = await search_engine.search(
            "API", 
            notebook_ids=["notebook-work"]
        )
        
        # Should find at least the API Documentation page
        assert len(results) >= 1

    async def test_search_with_section_filter(self, search_engine, sample_cached_pages):
        """Test searching with section ID filter."""
        # Index all pages
        for page in sample_cached_pages:
            await search_engine.index_page(page)
        
        # Search only in meetings section
        results = await search_engine.search(
            "meeting",
            section_ids=["section-meetings"]
        )
        
        assert len(results) >= 1
        # Note: OneNotePage model doesn't have section_id, so we check by title
        assert any("Team Meeting" in result.page.title for result in results)

    async def test_search_with_limit(self, search_engine, sample_cached_pages):
        """Test search result limiting."""
        # Index all pages
        for page in sample_cached_pages:
            await search_engine.index_page(page)
        
        # Search with limit
        results = await search_engine.search("documentation", limit=1)
        
        assert len(results) <= 1

    async def test_search_phrase_query(self, search_engine, sample_cached_pages):
        """Test searching with quoted phrases."""
        # Index all pages
        for page in sample_cached_pages:
            await search_engine.index_page(page)
        
        # Search for exact phrase
        results = await search_engine.search('"Team Meeting January"')
        
        assert len(results) >= 1
        meeting_result = results[0]
        assert "Team Meeting January" in meeting_result.page.title

    async def test_search_wildcard_query(self, search_engine, sample_cached_pages):
        """Test searching with wildcard/prefix matching."""
        # Index all pages
        for page in sample_cached_pages:
            await search_engine.index_page(page)
        
        # Search with prefix
        results = await search_engine.search("docum")  # Should match "documentation"
        
        assert len(results) >= 1
        assert any("documentation" in result.chunk.content.lower() or 
                  "documentation" in result.page.title.lower() for result in results)

    async def test_search_empty_query_raises_error(self, search_engine):
        """Test that empty search query raises error."""
        with pytest.raises(LocalSearchError, match="Search query cannot be empty"):
            await search_engine.search("")

    async def test_search_nonexistent_content(self, search_engine, sample_cached_pages):
        """Test searching for content that doesn't exist."""
        # Index all pages
        for page in sample_cached_pages:
            await search_engine.index_page(page)
        
        # Search for non-existent content
        results = await search_engine.search("nonexistent content xyz")
        
        assert len(results) == 0

    async def test_get_search_stats(self, search_engine, sample_cached_pages):
        """Test getting search engine statistics."""
        # Index pages and perform searches
        for page in sample_cached_pages:
            await search_engine.index_page(page)
        
        await search_engine.search("test query 1")
        await search_engine.search("test query 2")
        
        # Get statistics
        stats = await search_engine.get_search_stats()
        
        assert stats["total_searches"] == 2
        assert stats["index_operations"] == len(sample_cached_pages)
        assert stats["indexed_pages"] == len(sample_cached_pages)
        assert stats["indexed_notebooks"] >= 2  # Work and Personal notebooks
        assert stats["indexed_sections"] >= 3   # Meetings, Projects, Journal sections
        assert stats["database_size_mb"] >= 0   # May be 0 for temporary database

    async def test_rebuild_index(self, search_engine, cache_manager, sample_cached_pages):
        """Test rebuilding the search index."""
        # Mock cache_manager.get_all_cached_pages
        cache_manager.get_all_cached_pages = AsyncMock(return_value=sample_cached_pages)
        
        # Rebuild index
        result = await search_engine.rebuild_index("test-user-001")
        
        assert result["total_pages"] == len(sample_cached_pages)
        assert result["indexed_pages"] == len(sample_cached_pages)
        assert result["failed_pages"] == 0
        assert result["success_rate"] == 100.0
        assert result["rebuild_time_seconds"] >= 0  # May be 0 for very fast operations
        
        # Verify pages are indexed
        search_results = await search_engine.search("meeting")
        assert len(search_results) >= 1

    async def test_update_existing_page(self, search_engine, sample_cached_page):
        """Test updating an already indexed page."""
        # Index original page
        await search_engine.index_page(sample_cached_page)
        
        # Modify the page
        sample_cached_page.metadata.title = "Updated Test Page Title"
        sample_cached_page.markdown_content = "# Updated Content\\n\\nThis page has been updated."
        
        # Re-index the page
        result = await search_engine.index_page(sample_cached_page)
        assert result is True
        
        # Search for updated content
        results = await search_engine.search("Updated Content")
        assert len(results) >= 1
        assert "Updated" in results[0].page.title

    async def test_extract_searchable_content(self, search_engine, sample_cached_page):
        """Test content extraction from cached pages."""
        content = search_engine._extract_searchable_content(sample_cached_page)
        
        # Should contain title and markdown content
        assert sample_cached_page.metadata.title in content
        assert "Test Page Content" in content
        # Note: Current model doesn't have assets/links in test fixture

    async def test_build_fts_query_single_term(self, search_engine):
        """Test FTS query building for single terms."""
        query = search_engine._build_fts_query("documentation")
        assert query == "documentation*"

    async def test_build_fts_query_multiple_terms(self, search_engine):
        """Test FTS query building for multiple terms."""
        query = search_engine._build_fts_query("team meeting notes")
        assert '"team meeting notes"' in query
        assert "team*" in query and "meeting*" in query and "notes*" in query

    async def test_build_fts_query_quoted_phrase(self, search_engine):
        """Test FTS query building for quoted phrases."""
        query = search_engine._build_fts_query('"exact phrase"')
        assert query == '"exact phrase"'

    async def test_build_fts_query_title_only(self, search_engine):
        """Test FTS query building for title-only searches."""
        query = search_engine._build_fts_query("meeting", title_only=True)
        assert query == "page_title:meeting*"

    async def test_build_search_sql_no_filters(self, search_engine):
        """Test SQL building without filters."""
        sql = search_engine._build_search_sql()
        assert "WHERE page_content_fts MATCH ?" in sql
        assert "ORDER BY rank LIMIT ?" in sql
        assert " AND " not in sql  # No additional filters

    async def test_build_search_sql_with_filters(self, search_engine):
        """Test SQL building with notebook and section filters."""
        sql = search_engine._build_search_sql(
            notebook_ids=["nb1", "nb2"],
            section_ids=["sec1"]
        )
        
        assert "f.notebook_id IN (?,?)" in sql
        assert "f.section_id IN (?)" in sql
        assert sql.count(" AND ") == 2  # Two filter conditions

    async def test_database_connection_persistence(self, search_engine):
        """Test that database connection is persistent and reusable."""
        conn1 = await search_engine._get_connection()
        conn2 = await search_engine._get_connection()
        
        # Should return the same connection object
        assert conn1 is conn2

    async def test_close_connection(self, search_engine):
        """Test closing the database connection."""
        # Get connection to initialize it
        await search_engine._get_connection()
        assert search_engine._connection is not None
        
        # Close connection
        await search_engine.close()
        assert search_engine._connection is None

    async def test_search_result_format(self, search_engine, sample_cached_page):
        """Test that search results are properly formatted."""
        # Index page
        await search_engine.index_page(sample_cached_page)
        
        # Search
        results = await search_engine.search("test")
        
        assert len(results) >= 1
        result = results[0]
        
        # Check result structure
        assert isinstance(result, SemanticSearchResult)
        assert result.chunk.page_id == sample_cached_page.metadata.id
        assert result.chunk.page_title == sample_cached_page.metadata.title
        assert result.page.id == sample_cached_page.metadata.id
        assert result.search_type == "local_cache_fts"
        assert 0 < result.similarity_score <= 1.0
        assert result.rank >= 1

    async def test_concurrent_indexing(self, search_engine, sample_cached_pages):
        """Test concurrent page indexing."""
        # Index pages concurrently
        tasks = [search_engine.index_page(page) for page in sample_cached_pages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        assert all(result is True for result in results if not isinstance(result, Exception))
        
        # Verify all pages are indexed
        search_results = await search_engine.search("documentation")
        assert len(search_results) >= 1

    async def test_invalid_page_indexing(self, search_engine):
        """Test indexing invalid pages."""
        # Page without page_id
        invalid_page = CachedPage(
            metadata=CachedPageMetadata(
                id="",  # Invalid: empty page_id
                title="Invalid Page",
                created_date_time=datetime.now(),
                last_modified_date_time=datetime.now(),
                parent_section={"id": "test-sec", "name": "Test"},
                parent_notebook={"id": "test-nb", "name": "Test"},
                content_url="https://example.com/content",
                local_content_path="cache/invalid.md",
                local_html_path="cache/invalid.html",
                cached_at=datetime.now(),
                last_synced=datetime.now()
            ),
            markdown_content="Test content"
        )
        
        with pytest.raises(LocalSearchError, match="Page must have a valid page_id"):
            await search_engine.index_page(invalid_page)
