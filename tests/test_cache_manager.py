"""
Unit tests for OneNote cache manager.

Tests the core caching functionality including directory structure creation,
page storage/retrieval, search, and cleanup operations.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock

import pytest

from src.models.cache import (
    CachedPage,
    CachedPageMetadata,
    CacheMetadata,
    CacheStatistics,
    AssetInfo,
    InternalLink,
    ExternalLink,
    CleanupResult,
)
from src.storage.cache_manager import OneNoteCacheManager


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory for testing."""
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def cache_manager(temp_cache_dir):
    """Create a cache manager instance for testing."""
    mock_settings = Mock()
    mock_settings.onenote_cache_full_path = temp_cache_dir
    mock_settings.onenote_preserve_html = True
    
    return OneNoteCacheManager(settings=mock_settings, cache_root=temp_cache_dir)


@pytest.fixture
def sample_page_metadata():
    """Create sample page metadata for testing."""
    return CachedPageMetadata(
        id="page-123",
        title="Test Page",
        created_date_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        last_modified_date_time=datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
        parent_notebook={
            "id": "notebook-456",
            "displayName": "Test Notebook",
            "self_url": "https://graph.microsoft.com/v1.0/me/onenote/notebooks/notebook-456"
        },
        parent_section={
            "id": "section-789",
            "displayName": "Test Section",
            "self_url": "https://graph.microsoft.com/v1.0/me/onenote/sections/section-789"
        },
        content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/page-123/content",
        local_content_path="/tmp/page-123/content.md",
        local_html_path="/tmp/page-123/original.html",
        attachments=[
            AssetInfo(
                type="image",
                original_url="https://example.com/attachments/image-001",
                local_path="",  # Will be set during storage
                filename="test_image.png",
                size_bytes=12345,
                mime_type="image/png"
            )
        ],
        internal_links=[
            InternalLink(
                target_page_id="page-456",
                link_text="See related page",
                original_url="onenote:https://example.com/page-456",
                markdown_link="[See related page](page-456)"
            )
        ],
        external_links=[
            ExternalLink(
                url="https://example.com",
                link_text="Example Site"
            )
        ],
        content_preview="This is a test page with some content..."
    )


@pytest.fixture
def sample_cached_page(sample_page_metadata):
    """Create a sample cached page for testing."""
    return CachedPage(
        metadata=sample_page_metadata,
        content="<html><body><h1>Test Page</h1><p>This is test content.</p></body></html>",
        markdown_content="# Test Page\n\nThis is test content.\n",
        text_content="Test Page This is test content."
    )


class TestOneNoteCacheManager:
    """Test cases for OneNote cache manager."""

    @pytest.mark.asyncio
    async def test_initialize_user_cache(self, cache_manager, temp_cache_dir):
        """Test user cache initialization."""
        user_id = "test-user-123"
        
        await cache_manager.initialize_user_cache(user_id)
        
        # Check directory structure
        user_dir = temp_cache_dir / "users" / user_id
        assert user_dir.exists()
        assert (user_dir / "notebooks").exists()
        assert (user_dir / "global").exists()
        
        # Check metadata file
        metadata_file = user_dir / "cache_metadata.json"
        assert metadata_file.exists()
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
            assert metadata["user_id"] == user_id
            assert metadata["cache_root_path"] == str(temp_cache_dir)
        
        # Check sync status file
        sync_file = user_dir / "sync_status.json"
        assert sync_file.exists()
        
        with open(sync_file, 'r') as f:
            sync_status = json.load(f)
            assert sync_status["sync_in_progress"] is False

    @pytest.mark.asyncio
    async def test_store_page_content(self, cache_manager, sample_cached_page):
        """Test storing page content."""
        user_id = "test-user-123"
        
        # Initialize cache first
        await cache_manager.initialize_user_cache(user_id)
        
        # Store the page
        await cache_manager.store_page_content(user_id, sample_cached_page)
        
        # Check page directory structure
        page_dir = (cache_manager.cache_root / "users" / user_id / 
                   "notebooks" / "notebook-456" / "sections" / "section-789" / 
                   "pages" / "page-123")
        assert page_dir.exists()
        
        # Check files
        assert (page_dir / "metadata.json").exists()
        assert (page_dir / "content.md").exists()
        assert (page_dir / "original.html").exists()
        assert (page_dir / "attachments" / "images").exists()
        assert (page_dir / "attachments" / "files").exists()
        
        # Verify content
        with open(page_dir / "content.md", 'r') as f:
            content = f.read()
            assert "# Test Page" in content
        
        with open(page_dir / "original.html", 'r') as f:
            html = f.read()
            assert "<h1>Test Page</h1>" in html

    @pytest.mark.asyncio
    async def test_get_cached_page(self, cache_manager, sample_cached_page):
        """Test retrieving cached page."""
        user_id = "test-user-123"
        
        # Initialize and store page
        await cache_manager.initialize_user_cache(user_id)
        await cache_manager.store_page_content(user_id, sample_cached_page)
        
        # Retrieve page
        retrieved_page = await cache_manager.get_cached_page(user_id, "page-123")
        
        assert retrieved_page is not None
        assert retrieved_page.metadata.id == "page-123"
        assert retrieved_page.metadata.title == "Test Page"
        assert "# Test Page" in retrieved_page.markdown_content
        assert "Test Page" in retrieved_page.text_content

    @pytest.mark.asyncio
    async def test_get_cached_page_not_found(self, cache_manager):
        """Test retrieving non-existent page."""
        user_id = "test-user-123"
        
        await cache_manager.initialize_user_cache(user_id)
        
        retrieved_page = await cache_manager.get_cached_page(user_id, "nonexistent-page")
        assert retrieved_page is None

    @pytest.mark.asyncio
    async def test_search_cached_pages(self, cache_manager, sample_cached_page):
        """Test searching cached pages."""
        user_id = "test-user-123"
        
        # Initialize and store page
        await cache_manager.initialize_user_cache(user_id)
        await cache_manager.store_page_content(user_id, sample_cached_page)
        
        # Search by title
        results = await cache_manager.search_cached_pages(user_id, "Test Page")
        assert len(results) == 1
        assert results[0].metadata.id == "page-123"
        
        # Search by content
        results = await cache_manager.search_cached_pages(user_id, "test content")
        assert len(results) == 1
        
        # Search with no matches
        results = await cache_manager.search_cached_pages(user_id, "nonexistent content")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_cache_statistics(self, cache_manager, sample_cached_page):
        """Test cache statistics generation."""
        user_id = "test-user-123"
        
        # Empty cache statistics
        stats = await cache_manager.get_cache_statistics(user_id)
        assert stats.user_id == user_id
        assert stats.total_notebooks == 0
        assert stats.total_sections == 0
        assert stats.total_pages == 0
        
        # Initialize and store page
        await cache_manager.initialize_user_cache(user_id)
        await cache_manager.store_page_content(user_id, sample_cached_page)
        
        # Check statistics with content
        stats = await cache_manager.get_cache_statistics(user_id)
        assert stats.total_notebooks == 1
        assert stats.total_sections == 1
        assert stats.total_pages == 1
        assert stats.total_size_bytes > 0

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_assets(self, cache_manager, sample_cached_page, temp_cache_dir):
        """Test cleanup of orphaned assets."""
        user_id = "test-user-123"
        
        # Initialize and store page
        await cache_manager.initialize_user_cache(user_id)
        await cache_manager.store_page_content(user_id, sample_cached_page)
        
        # Create an orphaned asset file
        page_dir = (cache_manager.cache_root / "users" / user_id / 
                   "notebooks" / "notebook-456" / "sections" / "section-789" / 
                   "pages" / "page-123")
        orphaned_file = page_dir / "attachments" / "images" / "orphaned.jpg"
        orphaned_file.write_text("fake image content")
        
        # Run cleanup
        result = await cache_manager.cleanup_orphaned_assets(user_id)
        
        assert result.orphaned_assets_removed == 1
        assert result.space_freed_bytes > 0
        assert not orphaned_file.exists()

    @pytest.mark.asyncio
    async def test_cache_metadata_operations(self, cache_manager):
        """Test cache metadata save/load/update operations."""
        user_id = "test-user-123"
        
        await cache_manager.initialize_user_cache(user_id)
        
        # Update metadata
        await cache_manager.update_cache_metadata(
            user_id, 
            last_full_sync=datetime.utcnow(),
            total_pages=5
        )
        
        # Load and verify
        metadata = await cache_manager._load_cache_metadata(user_id)
        assert metadata is not None
        assert metadata.user_id == user_id
        assert metadata.last_full_sync is not None
        assert metadata.total_pages == 5

    @pytest.mark.asyncio
    async def test_delete_user_cache(self, cache_manager, sample_cached_page):
        """Test deleting user cache."""
        user_id = "test-user-123"
        
        # Initialize and store page
        await cache_manager.initialize_user_cache(user_id)
        await cache_manager.store_page_content(user_id, sample_cached_page)
        
        # Verify cache exists
        assert cache_manager.cache_exists(user_id)
        
        # Delete cache
        success = await cache_manager.delete_user_cache(user_id)
        assert success
        assert not cache_manager.cache_exists(user_id)

    def test_cache_exists(self, cache_manager):
        """Test cache existence check."""
        user_id = "test-user-123"
        
        # Cache doesn't exist initially
        assert not cache_manager.cache_exists(user_id)

    def test_directory_path_methods(self, cache_manager):
        """Test internal directory path generation methods."""
        user_id = "test-user-123"
        notebook_id = "notebook-456"
        section_id = "section-789"
        page_id = "page-123"
        
        # Test path generation
        user_dir = cache_manager._get_user_cache_dir(user_id)
        expected_user_dir = cache_manager.cache_root / "users" / user_id
        assert user_dir == expected_user_dir
        
        notebook_dir = cache_manager._get_notebook_dir(user_id, notebook_id)
        expected_notebook_dir = expected_user_dir / "notebooks" / notebook_id
        assert notebook_dir == expected_notebook_dir
        
        section_dir = cache_manager._get_section_dir(user_id, notebook_id, section_id)
        expected_section_dir = expected_notebook_dir / "sections" / section_id
        assert section_dir == expected_section_dir
        
        page_dir = cache_manager._get_page_dir(user_id, notebook_id, section_id, page_id)
        expected_page_dir = expected_section_dir / "pages" / page_id
        assert page_dir == expected_page_dir

    def test_user_id_sanitization(self, cache_manager):
        """Test user ID sanitization for filesystem safety."""
        # Test with special characters
        user_id_with_special = "user@example.com/with\\unsafe:chars*"
        user_dir = cache_manager._get_user_cache_dir(user_id_with_special)
        
        # Should contain only safe characters
        safe_user_id = user_dir.name
        assert "/" not in safe_user_id
        assert "\\" not in safe_user_id
        assert ":" not in safe_user_id
        assert "*" not in safe_user_id
        assert "user" in safe_user_id  # Should keep valid parts

    @pytest.mark.asyncio
    async def test_store_page_missing_parent_ids(self, cache_manager, sample_page_metadata):
        """Test error handling when parent IDs are missing."""
        user_id = "test-user-123"
        
        # Create page with missing notebook ID
        bad_metadata = sample_page_metadata.model_copy()
        bad_metadata.parent_notebook = {"displayName": "Test", "self_url": "test"}  # Missing ID
        
        bad_page = CachedPage(
            metadata=bad_metadata,
            content="test",
            markdown_content="test",
            text_content="test"
        )
        
        await cache_manager.initialize_user_cache(user_id)
        
        with pytest.raises(ValueError, match="Missing parent IDs"):
            await cache_manager.store_page_content(user_id, bad_page)

    @pytest.mark.asyncio
    async def test_load_page_missing_files(self, cache_manager, temp_cache_dir):
        """Test error handling when required files are missing."""
        # Create a page directory without metadata file
        page_dir = temp_cache_dir / "test_page"
        page_dir.mkdir(parents=True)
        
        with pytest.raises(FileNotFoundError):
            await cache_manager._load_page_from_directory(page_dir)

    @pytest.mark.asyncio
    async def test_search_nonexistent_user(self, cache_manager):
        """Test search for nonexistent user cache."""
        results = await cache_manager.search_cached_pages("nonexistent-user", "test")
        assert len(results) == 0


class TestCacheManagerIntegration:
    """Integration tests for cache manager with multiple operations."""

    @pytest.mark.asyncio
    async def test_full_cache_workflow(self, cache_manager, sample_cached_page):
        """Test complete cache workflow from initialization to cleanup."""
        user_id = "integration-test-user"
        
        # Step 1: Initialize cache
        await cache_manager.initialize_user_cache(user_id)
        assert cache_manager.cache_exists(user_id)
        
        # Step 2: Store multiple pages
        page1 = sample_cached_page
        
        # Create a second page
        page2_metadata = sample_cached_page.metadata.model_copy()
        page2_metadata.id = "page-456"
        page2_metadata.title = "Second Test Page"
        page2 = CachedPage(
            metadata=page2_metadata,
            content="<html><body><h1>Second Page</h1></body></html>",
            markdown_content="# Second Page\n",
            text_content="Second Page"
        )
        
        await cache_manager.store_page_content(user_id, page1)
        await cache_manager.store_page_content(user_id, page2)
        
        # Step 3: Search and retrieve
        search_results = await cache_manager.search_cached_pages(user_id, "Test")
        assert len(search_results) == 2
        
        retrieved_page = await cache_manager.get_cached_page(user_id, "page-123")
        assert retrieved_page is not None
        assert retrieved_page.metadata.title == "Test Page"
        
        # Step 4: Check statistics
        stats = await cache_manager.get_cache_statistics(user_id)
        assert stats.total_pages == 2
        assert stats.total_notebooks == 1
        assert stats.total_sections == 1
        
        # Step 5: Clean up
        success = await cache_manager.delete_user_cache(user_id)
        assert success
        assert not cache_manager.cache_exists(user_id)

    @pytest.mark.asyncio
    async def test_multiple_users_isolation(self, cache_manager, sample_cached_page):
        """Test that multiple users' caches are properly isolated."""
        user1_id = "user-1"
        user2_id = "user-2"
        
        # Initialize both users
        await cache_manager.initialize_user_cache(user1_id)
        await cache_manager.initialize_user_cache(user2_id)
        
        # Store pages for both users
        page1 = sample_cached_page
        
        page2_metadata = sample_cached_page.metadata.model_copy()
        page2_metadata.title = "User 2 Page"
        page2 = CachedPage(
            metadata=page2_metadata,
            content="User 2 content",
            markdown_content="# User 2 Page\n",
            text_content="User 2 Page"
        )
        
        await cache_manager.store_page_content(user1_id, page1)
        await cache_manager.store_page_content(user2_id, page2)
        
        # Verify isolation
        user1_results = await cache_manager.search_cached_pages(user1_id, "Test")
        user2_results = await cache_manager.search_cached_pages(user2_id, "User 2")
        
        assert len(user1_results) == 1
        assert len(user2_results) == 1
        assert user1_results[0].metadata.title == "Test Page"
        assert user2_results[0].metadata.title == "User 2 Page"
        
        # User 1 shouldn't see User 2's content
        user1_search_user2 = await cache_manager.search_cached_pages(user1_id, "User 2")
        assert len(user1_search_user2) == 0
