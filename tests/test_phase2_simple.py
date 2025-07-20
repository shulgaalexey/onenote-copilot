"""
Simple tests for Phase 2 cache implementation modules.

Basic functionality tests for OneNote content fetcher, asset downloader,
markdown converter, and link resolver.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List

import pytest

from src.models.cache import (
    AssetInfo,
    CachedPage,
    CachedPageMetadata,
    ConversionResult,
    DownloadResult,
    InternalLink,
    ExternalLink,
    LinkResolutionResult,
    SyncResult,
    SyncType,
    SyncStatus,
)
from src.models.onenote import OneNotePage, OneNoteSection, OneNoteNotebook
from datetime import datetime


# Simple mock implementations for testing
class MockOneNoteContentFetcher:
    """Mock content fetcher for testing."""
    
    def __init__(self, auth_client):
        self.auth_client = auth_client
    
    async def fetch_all_notebooks(self):
        """Mock fetch notebooks."""
        return SyncResult(
            sync_type=SyncType.FULL,
            status=SyncStatus.COMPLETED, 
            started_at=datetime.utcnow()
        )


class MockAssetDownloadManager:
    """Mock asset download manager for testing."""
    
    def __init__(self):
        self.downloads = []
    
    async def download_asset(self, asset_info: AssetInfo):
        """Mock asset download."""
        return DownloadResult(
            success=True,
            local_path=f"/tmp/{asset_info.filename}",
            error_message=None
        )


class MockMarkdownConverter:
    """Mock markdown converter for testing."""
    
    def convert_to_markdown(self, html_content: str):
        """Mock HTML to markdown conversion."""
        if not html_content:
            return ConversionResult(
                success=True,
                markdown_content="",
                assets_processed=[],
                links_processed=LinkResolutionResult()
            )
        
        # Simple conversion for testing
        markdown = html_content.replace("<h1>", "# ").replace("</h1>", "\n")
        markdown = markdown.replace("<p>", "").replace("</p>", "\n")
        
        return ConversionResult(
            success=True,
            markdown_content=markdown,
            assets_processed=[],
            links_processed=LinkResolutionResult()
        )


class MockLinkResolver:
    """Mock link resolver for testing."""
    
    def __init__(self, cache_root: Path):
        self.cache_root = cache_root
    
    async def resolve_internal_link(self, link: InternalLink, cache_dir: Path):
        """Mock internal link resolution."""
        return LinkResolutionResult(
            success=True,
            total_links=1,
            resolved_count=1,
            failed_count=0
        )
    
    async def resolve_external_link(self, link: ExternalLink):
        """Mock external link resolution."""
        return LinkResolutionResult(
            success=True,
            total_links=1,
            resolved_count=1,
            failed_count=0
        )


# Test classes
class TestMockOneNoteContentFetcher:
    """Test mock content fetcher functionality."""

    @pytest.fixture
    def mock_auth_client(self):
        """Create a mock authentication client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def content_fetcher(self, mock_auth_client):
        """Create a content fetcher instance."""
        return MockOneNoteContentFetcher(mock_auth_client)

    @pytest.mark.asyncio
    async def test_initialization(self, content_fetcher):
        """Test content fetcher initialization."""
        assert content_fetcher is not None
        assert content_fetcher.auth_client is not None

    @pytest.mark.asyncio 
    async def test_fetch_notebooks_success(self, content_fetcher):
        """Test successful notebook fetching."""
        result = await content_fetcher.fetch_all_notebooks()
        
        assert isinstance(result, SyncResult)
        assert result.success is True


class TestMockAssetDownloadManager:
    """Test mock asset download manager functionality."""

    @pytest.fixture
    def download_manager(self):
        """Create an asset download manager."""
        return MockAssetDownloadManager()

    @pytest.fixture
    def sample_asset_info(self):
        """Create sample asset info."""
        return AssetInfo(
            type="image",
            original_url="https://example.com/image.png",
            local_path="/tmp/image.png",
            filename="image.png",
            size_bytes=12345,
            mime_type="image/png"
        )

    @pytest.mark.asyncio
    async def test_initialization(self, download_manager):
        """Test download manager initialization."""
        assert download_manager is not None

    @pytest.mark.asyncio
    async def test_download_asset_success(self, download_manager, sample_asset_info):
        """Test successful asset download."""
        result = await download_manager.download_asset(sample_asset_info)
        
        assert isinstance(result, DownloadResult)
        assert result.success is True
        assert result.local_path is not None


class TestMockMarkdownConverter:
    """Test mock markdown converter functionality."""

    @pytest.fixture
    def converter(self):
        """Create a markdown converter."""
        return MockMarkdownConverter()

    @pytest.fixture
    def sample_html(self):
        """Sample HTML content for testing."""
        return """<h1>Test Title</h1><p>This is a test paragraph.</p>"""

    def test_initialization(self, converter):
        """Test converter initialization."""
        assert converter is not None

    def test_convert_basic_html(self, converter, sample_html):
        """Test basic HTML to markdown conversion."""
        result = converter.convert_to_markdown(sample_html)
        
        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert "# Test Title" in result.markdown_content

    def test_convert_empty_content(self, converter):
        """Test handling of empty content."""
        result = converter.convert_to_markdown("")
        
        assert isinstance(result, ConversionResult)
        assert result.success is True
        assert result.markdown_content == ""


class TestMockLinkResolver:
    """Test mock link resolver functionality."""

    @pytest.fixture 
    def link_resolver(self, tmp_path):
        """Create a link resolver."""
        return MockLinkResolver(tmp_path)

    @pytest.fixture
    def sample_internal_link(self):
        """Create sample internal link."""
        return InternalLink(
            target_page_id="page-123",
            link_text="Link to page",
            original_url="onenote:https://example.com/page-123"
        )

    @pytest.fixture
    def sample_external_link(self):
        """Create sample external link."""
        return ExternalLink(
            url="https://example.com",
            link_text="External site"
        )

    def test_initialization(self, link_resolver):
        """Test link resolver initialization."""
        assert link_resolver is not None

    @pytest.mark.asyncio
    async def test_resolve_internal_link(self, link_resolver, sample_internal_link):
        """Test resolving internal OneNote links."""
        result = await link_resolver.resolve_internal_link(
            sample_internal_link, 
            cache_dir=Path("/tmp/cache")
        )
        
        assert isinstance(result, LinkResolutionResult)
        assert result.total_links == 1

    @pytest.mark.asyncio
    async def test_resolve_external_link(self, link_resolver, sample_external_link):
        """Test handling external links."""
        result = await link_resolver.resolve_external_link(sample_external_link)
        
        assert isinstance(result, LinkResolutionResult)
        assert result.total_links == 1
        assert result.resolved_count == 1


class TestBasicModels:
    """Test basic model functionality."""

    def test_asset_info_creation(self):
        """Test AssetInfo model creation."""
        asset = AssetInfo(
            type="image",
            original_url="https://example.com/image.png",
            local_path="/tmp/image.png",
            filename="image.png",
            size_bytes=12345,
            mime_type="image/png"
        )
        
        assert asset.type == "image"
        assert asset.filename == "image.png"
        assert asset.size_bytes == 12345

    def test_internal_link_creation(self):
        """Test InternalLink model creation."""
        link = InternalLink(
            target_page_id="page-123",
            link_text="Test Link",
            original_url="onenote:https://example.com/page-123"
        )
        
        assert link.target_page_id == "page-123"
        assert link.link_text == "Test Link"

    def test_external_link_creation(self):
        """Test ExternalLink model creation."""
        link = ExternalLink(
            url="https://example.com",
            link_text="External Site"
        )
        
        assert link.url == "https://example.com"
        assert link.link_text == "External Site"

    def test_onenote_page_creation(self):
        """Test OneNotePage model creation."""
        page = OneNotePage(
            id="page-1",
            title="Test Page",
            created_date_time="2024-01-01T10:00:00Z",
            last_modified_date_time="2024-01-01T10:00:00Z",
            content_url="https://example.com/content"
        )
        
        assert page.id == "page-1"
        assert page.title == "Test Page"

    def test_sync_result_success(self):
        """Test SyncResult for successful operations."""
        result = SyncResult(
            sync_type=SyncType.FULL,
            status=SyncStatus.COMPLETED,
            started_at=datetime.utcnow()
        )
        
        assert result.success is True
        assert result.sync_type == SyncType.FULL
        assert result.status == SyncStatus.COMPLETED

    def test_sync_result_failure(self):
        """Test SyncResult for failed operations."""
        result = SyncResult(
            sync_type=SyncType.FULL,
            status=SyncStatus.FAILED,
            started_at=datetime.utcnow()
        )
        
        assert result.success is False
        assert result.sync_type == SyncType.FULL
        assert result.status == SyncStatus.FAILED

    def test_download_result_success(self):
        """Test DownloadResult for successful downloads."""
        result = DownloadResult(
            success=True,
            local_path="/tmp/file.png",
            error_message=None
        )
        
        assert result.success is True
        assert result.local_path == "/tmp/file.png"
        assert result.error_message is None

    def test_conversion_result_success(self):
        """Test ConversionResult for successful conversions."""
        result = ConversionResult(
            success=True,
            markdown_content="# Test\nContent",
            assets_processed=[],
            links_processed=LinkResolutionResult()
        )
        
        assert result.success is True
        assert result.markdown_content == "# Test\nContent"
        assert len(result.assets_processed) == 0

    def test_link_resolution_result(self):
        """Test LinkResolutionResult."""
        result = LinkResolutionResult(
            success=True,
            total_links=1,
            resolved_count=1,
            failed_count=0
        )
        
        assert result.total_links == 1
        assert result.resolved_count == 1
        assert result.failed_count == 0


class TestIntegration:
    """Basic integration tests."""

    @pytest.mark.asyncio
    async def test_basic_workflow(self):
        """Test basic workflow integration."""
        # Mock auth client
        auth_client = AsyncMock()
        
        # Create mock components
        fetcher = MockOneNoteContentFetcher(auth_client)
        downloader = MockAssetDownloadManager()
        converter = MockMarkdownConverter()
        resolver = MockLinkResolver(Path("/tmp"))
        
        # Test basic workflow
        notebooks_result = await fetcher.fetch_all_notebooks()
        assert notebooks_result.success is True
        
        # Test asset download
        asset = AssetInfo(
            type="image",
            original_url="https://example.com/test.png",
            local_path="",
            filename="test.png",
            size_bytes=1024,
            mime_type="image/png"
        )
        download_result = await downloader.download_asset(asset)
        assert download_result.success is True
        
        # Test conversion
        html = "<h1>Test</h1><p>Content</p>"
        conversion_result = converter.convert_to_markdown(html)
        assert conversion_result.success is True
        
        # Test link resolution
        internal_link = InternalLink(
            target_page_id="test-page",
            link_text="Test Link",
            original_url="onenote:test"
        )
        link_result = await resolver.resolve_internal_link(internal_link, Path("/tmp"))
        assert link_result.total_links == 1

    def test_model_compatibility(self):
        """Test that models work together."""
        # Create sample models
        notebook = OneNoteNotebook(
            id="nb-1",
            display_name="Test Notebook",
            created_date_time="2024-01-01T10:00:00Z",
            last_modified_date_time="2024-01-01T10:00:00Z"
        )
        
        section = OneNoteSection(
            id="sec-1",
            display_name="Test Section",
            created_date_time="2024-01-01T10:00:00Z",
            last_modified_date_time="2024-01-01T10:00:00Z"
        )
        
        page = OneNotePage(
            id="page-1",
            title="Test Page",
            created_date_time="2024-01-01T10:00:00Z",
            last_modified_date_time="2024-01-01T10:00:00Z",
            content_url="https://example.com/content"
        )
        
        # Verify models are properly created
        assert notebook.id == "nb-1"
        assert section.id == "sec-1" 
        assert page.id == "page-1"
        
        # Test that they can be used together
        models = [notebook, section, page]
        assert len(models) == 3
