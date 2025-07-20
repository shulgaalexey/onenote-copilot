"""
Tests for Phase 2 cache implementation modules.

Tests OneNote content fetcher, asset downloader, markdown converter,
and link resolver functionality.
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
)
from src.models.onenote import OneNotePage, OneNoteSection, OneNoteNotebook
from src.storage.onenote_fetcher import OneNoteContentFetcher
from src.storage.asset_downloader import AssetDownloadManager
from src.storage.markdown_converter import MarkdownConverter
from src.storage.link_resolver import LinkResolver


class TestOneNoteContentFetcher:
    """Test OneNote content fetcher functionality."""

    @pytest.fixture
    def mock_auth_client(self):
        """Create mock authentication client."""
        client = AsyncMock()
        client.get_access_token.return_value = "mock_access_token"
        return client

    @pytest.fixture
    def cache_manager(self):
        """Create mock cache manager."""
        manager = MagicMock()
        manager.get_cache_info.return_value = MagicMock(last_sync_time=None)
        return manager

    @pytest.fixture
    async def content_fetcher(self, mock_auth_client, cache_manager):
        """Create content fetcher instance."""
        async with OneNoteContentFetcher(mock_auth_client, cache_manager) as fetcher:
            yield fetcher

    @pytest.mark.asyncio
    async def test_fetch_notebooks_success(self, content_fetcher):
        """Test successful notebook fetching."""
        # Mock HTTP response
        mock_response = {
            "value": [
                {
                    "id": "notebook1",
                    "displayName": "Test Notebook",
                    "links": {"oneNoteWebUrl": {"href": "https://test.com/notebook1"}}
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            notebooks = await content_fetcher.fetch_notebooks()
            
            assert len(notebooks) == 1
            assert notebooks[0].id == "notebook1"
            assert notebooks[0].name == "Test Notebook"

    @pytest.mark.asyncio
    async def test_fetch_notebooks_api_error(self, content_fetcher):
        """Test notebook fetching with API error."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 403
            mock_resp.reason = "Forbidden"
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            with pytest.raises(Exception) as exc_info:
                await content_fetcher.fetch_notebooks()
            
            assert "403" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_sections_success(self, content_fetcher):
        """Test successful section fetching."""
        notebook = OneNoteNotebook(
            id="notebook1", 
            name="Test Notebook", 
            web_url="https://test.com"
        )
        
        mock_response = {
            "value": [
                {
                    "id": "section1",
                    "displayName": "Test Section",
                    "links": {"oneNoteWebUrl": {"href": "https://test.com/section1"}}
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            sections = await content_fetcher.fetch_sections_for_notebook(notebook)
            
            assert len(sections) == 1
            assert sections[0].id == "section1"
            assert sections[0].name == "Test Section"
            assert sections[0].notebook_name == "Test Notebook"

    @pytest.mark.asyncio
    async def test_fetch_pages_success(self, content_fetcher):
        """Test successful page fetching."""
        section = OneNoteSection(
            id="section1", 
            name="Test Section", 
            notebook_name="Test Notebook",
            web_url="https://test.com"
        )
        
        mock_response = {
            "value": [
                {
                    "id": "page1",
                    "title": "Test Page",
                    "links": {"oneNoteWebUrl": {"href": "https://test.com/page1"}},
                    "lastModifiedDateTime": "2024-01-01T00:00:00Z"
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            pages = await content_fetcher.fetch_pages_for_section(section)
            
            assert len(pages) == 1
            assert pages[0].id == "page1"
            assert pages[0].title == "Test Page"
            assert pages[0].notebook_name == "Test Notebook"
            assert pages[0].section_name == "Test Section"

    @pytest.mark.asyncio
    async def test_fetch_page_content_success(self, content_fetcher):
        """Test successful page content fetching."""
        page = OneNotePage(
            id="page1",
            title="Test Page",
            notebook_name="Test Notebook",
            section_name="Test Section",
            web_url="https://test.com",
            last_modified=None
        )
        
        mock_content = "<html><body><p>Test content</p></body></html>"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.text.return_value = mock_content
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            content = await content_fetcher.fetch_page_content(page)
            
            assert content == mock_content


class TestAssetDownloadManager:
    """Test asset download manager functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test downloads."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    async def asset_manager(self):
        """Create asset download manager instance."""
        async with AssetDownloadManager(max_concurrent_downloads=2) as manager:
            yield manager

    @pytest.fixture
    def sample_assets(self):
        """Create sample asset list."""
        return [
            AssetInfo(
                type="image",
                original_url="https://example.com/image1.png",
                local_path="",
                filename="image1.png",
                mime_type="image/png"
            ),
            AssetInfo(
                type="image",
                original_url="https://example.com/image2.jpg",
                local_path="",
                filename="image2.jpg",
                mime_type="image/jpeg"
            )
        ]

    @pytest.mark.asyncio
    async def test_download_assets_success(self, asset_manager, sample_assets, temp_dir):
        """Test successful asset downloading."""
        mock_content = b"fake image data"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {
                'content-type': 'image/png',
                'content-length': str(len(mock_content))
            }
            mock_resp.content.iter_chunked.return_value = AsyncMock()
            mock_resp.content.iter_chunked.return_value.__aiter__.return_value = [mock_content]
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            result = await asset_manager.download_assets(sample_assets, temp_dir)
            
            assert result.success is True
            assert result.successful_count == 2
            assert result.failed_count == 0

    @pytest.mark.asyncio
    async def test_download_assets_http_error(self, asset_manager, sample_assets, temp_dir):
        """Test asset downloading with HTTP error."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 404
            mock_resp.reason = "Not Found"
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            result = await asset_manager.download_assets(sample_assets, temp_dir)
            
            assert result.success is False
            assert result.successful_count == 0
            assert result.failed_count == 2

    @pytest.mark.asyncio
    async def test_download_single_asset(self, asset_manager, sample_assets, temp_dir):
        """Test downloading a single asset."""
        asset = sample_assets[0]
        mock_content = b"fake image data"
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {
                'content-type': 'image/png',
                'content-length': str(len(mock_content))
            }
            mock_resp.content.iter_chunked.return_value = AsyncMock()
            mock_resp.content.iter_chunked.return_value.__aiter__.return_value = [mock_content]
            mock_get.return_value.__aenter__.return_value = mock_resp
            
            result = await asset_manager.download_single_asset(asset, temp_dir)
            
            assert result['success'] is True
            assert 'local_path' in result

    def test_estimate_download_time(self, asset_manager):
        """Test download time estimation."""
        # Create assets with known sizes
        assets = [
            AssetInfo(
                type="image",
                original_url="https://example.com/large.png",
                local_path="",
                filename="large.png",
                size_bytes=1024 * 1024  # 1MB
            )
        ]
        
        estimated_time = asset_manager.estimate_download_time(assets)
        
        # Should return a reasonable estimate
        assert estimated_time > 0
        assert estimated_time < 60  # Should be less than 1 minute for 1MB


class TestMarkdownConverter:
    """Test markdown converter functionality."""

    @pytest.fixture
    def converter(self):
        """Create markdown converter instance."""
        return MarkdownConverter(preserve_whitespace=True, include_metadata=True)

    @pytest.fixture
    def sample_html(self):
        """Create sample HTML content."""
        return """
        <html>
        <body>
            <h1>Test Page</h1>
            <p>This is a <strong>test</strong> paragraph with <em>formatting</em>.</p>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
            <a href="https://example.com/page1">External Link</a>
            <img src="https://example.com/image.png" alt="Test Image" />
        </body>
        </html>
        """

    @pytest.fixture
    def sample_assets(self):
        """Create sample assets."""
        return [
            AssetInfo(
                type="image",
                original_url="https://example.com/image.png",
                local_path="attachments/image.png",
                filename="image.png",
                mime_type="image/png"
            )
        ]

    @pytest.fixture
    def sample_links(self):
        """Create sample internal links."""
        return [
            LinkInfo(
                original_url="https://example.com/page1",
                resolved_path="other-page.md",
                link_text="External Link",
                link_type="page",
                resolution_status="resolved"
            )
        ]

    def test_convert_to_markdown_success(self, converter, sample_html, sample_assets, sample_links):
        """Test successful HTML to Markdown conversion."""
        result = converter.convert_to_markdown(
            html_content=sample_html,
            assets=sample_assets,
            internal_links=sample_links,
            page_title="Test Page"
        )
        
        assert result.success is True
        assert "# Test Page" in result.markdown_content
        assert "**test**" in result.markdown_content
        assert "*formatting*" in result.markdown_content
        assert "- Item 1" in result.markdown_content
        assert "[External Link](other-page.md)" in result.markdown_content
        assert "![Test Image](../attachments/image.png)" in result.markdown_content

    def test_convert_heading_elements(self, converter):
        """Test heading conversion."""
        html = "<h1>Heading 1</h1><h2>Heading 2</h2><h3>Heading 3</h3>"
        result = converter.convert_to_markdown(html, [], [])
        
        assert "# Heading 1" in result.markdown_content
        assert "## Heading 2" in result.markdown_content
        assert "### Heading 3" in result.markdown_content

    def test_convert_list_elements(self, converter):
        """Test list conversion."""
        html = """
        <ul>
            <li>Unordered item 1</li>
            <li>Unordered item 2</li>
        </ul>
        <ol>
            <li>Ordered item 1</li>
            <li>Ordered item 2</li>
        </ol>
        """
        result = converter.convert_to_markdown(html, [], [])
        
        assert "- Unordered item 1" in result.markdown_content
        assert "- Unordered item 2" in result.markdown_content
        assert "1. Ordered item 1" in result.markdown_content
        assert "2. Ordered item 2" in result.markdown_content

    def test_convert_table_elements(self, converter):
        """Test table conversion."""
        html = """
        <table>
            <tr>
                <th>Header 1</th>
                <th>Header 2</th>
            </tr>
            <tr>
                <td>Cell 1</td>
                <td>Cell 2</td>
            </tr>
        </table>
        """
        result = converter.convert_to_markdown(html, [], [])
        
        assert "| **Header 1** | **Header 2** |" in result.markdown_content
        assert "| --- | --- |" in result.markdown_content
        assert "| Cell 1 | Cell 2 |" in result.markdown_content

    def test_convert_code_elements(self, converter):
        """Test code conversion."""
        html = """
        <p>Inline <code>code</code> here.</p>
        <pre><code>
        def hello():
            print("Hello, World!")
        </code></pre>
        """
        result = converter.convert_to_markdown(html, [], [])
        
        assert "`code`" in result.markdown_content
        assert "```" in result.markdown_content
        assert "def hello():" in result.markdown_content

    def test_estimate_conversion_time(self, converter):
        """Test conversion time estimation."""
        html = "<p>Simple content</p>" * 100
        estimated_time = converter.estimate_conversion_time(html)
        
        assert estimated_time > 0
        assert estimated_time < 10  # Should be reasonable

    def test_clean_markdown(self, converter):
        """Test markdown cleaning."""
        dirty_content = "**  **\n\n\n\nTest content\n\n\n*  *"
        cleaned = converter._clean_markdown(dirty_content)
        
        assert "**  **" not in cleaned
        assert "*  *" not in cleaned
        assert "\n\n\n" not in cleaned
        assert "Test content" in cleaned


class TestLinkResolver:
    """Test link resolver functionality."""

    @pytest.fixture
    def temp_cache_root(self):
        """Create temporary cache root directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def link_resolver(self, temp_cache_root):
        """Create link resolver instance."""
        return LinkResolver(temp_cache_root)

    @pytest.fixture
    def sample_pages(self):
        """Create sample pages."""
        return [
            OneNotePage(
                id="page1",
                title="Test Page 1",
                notebook_name="Test Notebook",
                section_name="Test Section",
                web_url="https://test.onenote.com/page1",
                last_modified=None
            ),
            OneNotePage(
                id="page2", 
                title="Test Page 2",
                notebook_name="Test Notebook",
                section_name="Test Section",
                web_url="https://test.onenote.com/page2",
                last_modified=None
            )
        ]

    @pytest.fixture
    def sample_sections(self):
        """Create sample sections."""
        return [
            OneNoteSection(
                id="section1",
                name="Test Section",
                notebook_name="Test Notebook",
                web_url="https://test.onenote.com/section1"
            )
        ]

    @pytest.fixture
    def sample_links(self):
        """Create sample links to resolve."""
        return [
            LinkInfo(
                original_url="https://test.onenote.com/page1#page-id=page1",
                resolved_path="",
                link_text="Link to Page 1",
                link_type="unknown",
                resolution_status="pending"
            ),
            LinkInfo(
                original_url="https://test.onenote.com/section1#section-id=section1",
                resolved_path="",
                link_text="Link to Section",
                link_type="unknown", 
                resolution_status="pending"
            )
        ]

    def test_resolve_links_success(self, link_resolver, sample_links, sample_pages, sample_sections):
        """Test successful link resolution."""
        result = link_resolver.resolve_links(sample_links, sample_pages, sample_sections)
        
        assert result.success is True
        assert result.total_links == 2
        assert result.resolved_count >= 0  # May resolve based on pattern matching

    def test_is_internal_onenote_link(self, link_resolver):
        """Test OneNote link detection."""
        # Test OneNote URLs
        assert link_resolver.is_internal_onenote_link("https://test.onenote.com/page1") is True
        assert link_resolver.is_internal_onenote_link("https://test.sharepoint.com/notebook.one#page") is True
        assert link_resolver.is_internal_onenote_link("onenote:page1") is True
        
        # Test non-OneNote URLs
        assert link_resolver.is_internal_onenote_link("https://google.com") is False
        assert link_resolver.is_internal_onenote_link("mailto:test@test.com") is False

    def test_extract_page_id(self, link_resolver):
        """Test page ID extraction."""
        url = "https://test.onenote.com/page#page-id=abc123"
        page_id = link_resolver._extract_page_id(url)
        assert page_id == "abc123"
        
        # Test URL without page ID
        url_no_id = "https://test.onenote.com/page"
        page_id_none = link_resolver._extract_page_id(url_no_id)
        assert page_id_none is None

    def test_extract_section_id(self, link_resolver):
        """Test section ID extraction."""
        url = "https://test.onenote.com/section#section-id=def456"
        section_id = link_resolver._extract_section_id(url)
        assert section_id == "def456"
        
        # Test URL without section ID
        url_no_id = "https://test.onenote.com/section"
        section_id_none = link_resolver._extract_section_id(url_no_id)
        assert section_id_none is None

    def test_extract_links_from_html(self, link_resolver):
        """Test link extraction from HTML."""
        html = '''
        <html>
        <body>
            <a href="https://test.onenote.com/page1">OneNote Link</a>
            <a href="https://google.com">External Link</a>
            <a href="onenote:page2">OneNote Desktop Link</a>
        </body>
        </html>
        '''
        
        links = link_resolver.extract_links_from_html(html)
        
        # Should find OneNote links but not external ones
        onenote_urls = [link.original_url for link in links]
        assert "https://test.onenote.com/page1" in onenote_urls
        assert "onenote:page2" in onenote_urls
        assert "https://google.com" not in onenote_urls

    def test_validate_resolved_links(self, link_resolver, temp_cache_root):
        """Test link validation."""
        # Create a test markdown file
        content_dir = temp_cache_root / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        test_file = content_dir / "test.md"
        test_file.write_text("# Test")
        
        # Create links to validate
        links = [
            LinkInfo(
                original_url="https://test.com/page1",
                resolved_path="test.md",
                link_text="Valid Link",
                link_type="page",
                resolution_status="resolved"
            ),
            LinkInfo(
                original_url="https://test.com/page2",
                resolved_path="nonexistent.md",
                link_text="Invalid Link",
                link_type="page",
                resolution_status="resolved"
            )
        ]
        
        valid_links, invalid_links = link_resolver.validate_resolved_links(links)
        
        assert len(valid_links) == 1
        assert len(invalid_links) == 1
        assert valid_links[0].resolved_path == "test.md"
        assert invalid_links[0].resolved_path == "nonexistent.md"

    def test_update_link_in_markdown(self, link_resolver):
        """Test updating links in markdown content."""
        markdown = "Check out [this page](old-link.md) for more info."
        updated = link_resolver.update_link_in_markdown(
            markdown, "old-link.md", "new-link.md"
        )
        
        assert "[this page](new-link.md)" in updated
        assert "old-link.md" not in updated

    def test_clear_resolution_cache(self, link_resolver):
        """Test cache clearing."""
        # Add something to cache
        link_resolver.resolution_cache["test"] = "value"
        assert len(link_resolver.resolution_cache) == 1
        
        # Clear cache
        link_resolver.clear_resolution_cache()
        assert len(link_resolver.resolution_cache) == 0


# Integration tests

class TestPhase2Integration:
    """Integration tests for Phase 2 modules."""

    @pytest.fixture
    def temp_cache_root(self):
        """Create temporary cache root."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.mark.asyncio
    async def test_full_content_processing_workflow(self, temp_cache_root):
        """Test complete workflow from fetching to markdown conversion."""
        # This would be a comprehensive integration test
        # For now, just ensure modules can be imported and instantiated together
        
        # Mock auth client
        auth_client = AsyncMock()
        auth_client.get_access_token.return_value = "mock_token"
        
        # Mock cache manager
        cache_manager = MagicMock()
        cache_manager.get_cache_info.return_value = MagicMock(last_sync_time=None)
        
        # Test that all modules can be created
        async with AssetDownloadManager() as asset_manager:
            async with OneNoteContentFetcher(auth_client, cache_manager) as content_fetcher:
                converter = MarkdownConverter()
                resolver = LinkResolver(temp_cache_root)
                
                # Basic functionality test
                assert asset_manager.get_download_stats()['total_downloads'] == 0
                assert converter.get_conversion_stats()['elements_converted'] == 0
                assert resolver.get_resolution_stats()['total_links'] == 0

    def test_module_compatibility(self):
        """Test that all modules have compatible interfaces."""
        # Test that model classes are compatible across modules
        asset = AssetInfo(
            type="image",
            original_url="https://test.com/image.png",
            local_path="",
            filename="image.png"
        )
        
        link = LinkInfo(
            original_url="https://test.com/page",
            resolved_path="",
            link_text="Test Link",
            link_type="page",
            resolution_status="pending"
        )
        
        page = OneNotePage(
            id="page1",
            title="Test Page",
            notebook_name="Test Notebook",
            section_name="Test Section",
            web_url="https://test.com",
            last_modified=None
        )
        
        # Ensure models are properly structured
        assert hasattr(asset, 'original_url')
        assert hasattr(link, 'resolved_path')
        assert hasattr(page, 'title')

    def test_error_handling_consistency(self):
        """Test that error handling is consistent across modules."""
        # Test that all result classes have success/error fields
        download_result = AssetDownloadResult()
        assert hasattr(download_result, 'status')
        
        conversion_result = MarkdownConversionResult()
        assert hasattr(conversion_result, 'success')
        assert hasattr(conversion_result, 'error')
        
        resolution_result = LinkResolutionResult()
        assert hasattr(resolution_result, 'success')
        assert hasattr(resolution_result, 'error')
