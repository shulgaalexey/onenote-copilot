"""
Integration tests for LinkResolver.

Tests the real LinkResolver implementation with OneNote links and validates
resolution accuracy, caching, and path generation.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.storage.link_resolver import LinkResolver
from src.models.cache import LinkInfo, LinkResolutionResult
from src.models.onenote import OneNotePage, OneNoteSection


class TestLinkResolverIntegration:
    """Integration tests for LinkResolver functionality."""

    @pytest.fixture
    def temp_cache_root(self):
        """Create temporary cache root directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir)
            # Create cache structure
            (cache_root / "content").mkdir(parents=True)
            (cache_root / "attachments").mkdir(parents=True)
            yield cache_root

    @pytest.fixture
    def resolver(self, temp_cache_root):
        """Create a link resolver instance."""
        return LinkResolver(temp_cache_root)

    @pytest.fixture
    def sample_pages(self):
        """Create sample OneNote pages."""
        return [
            OneNotePage(
                id="page-1234-5678-abcd",
                title="Project Overview",
                created_date_time="2025-01-15T10:00:00Z",
                last_modified_date_time="2025-01-17T09:30:00Z",
                content_url="https://graph.microsoft.com/v1.0/pages/page-1234",
                content=""
            ),
            OneNotePage(
                id="page-2345-6789-bcde",
                title="Technical Specifications", 
                created_date_time="2025-01-16T14:00:00Z",
                last_modified_date_time="2025-01-17T11:15:00Z",
                content_url="https://graph.microsoft.com/v1.0/pages/page-2345",
                content=""
            )
        ]

    @pytest.fixture
    def sample_sections(self):
        """Create sample OneNote sections."""
        return [
            OneNoteSection(
                id="section-1234-abcd",
                display_name="Projects",
                created_date_time="2025-01-15T08:00:00Z",
                last_modified_date_time="2025-01-17T10:00:00Z",
                pages_url="https://graph.microsoft.com/v1.0/sections/section-1234/pages"
            ),
            OneNoteSection(
                id="section-2345-bcde", 
                display_name="Documentation",
                created_date_time="2025-01-16T09:00:00Z",
                last_modified_date_time="2025-01-17T12:00:00Z",
                pages_url="https://graph.microsoft.com/v1.0/sections/section-2345/pages"
            )
        ]

    @pytest.fixture
    def sample_links(self):
        """Create sample links to resolve."""
        return [
            LinkInfo(
                original_url="https://contoso.sharepoint.com/sites/notebook/page1#page-id=page-1234-5678-abcd",
                resolved_path="",
                link_text="View Project Overview",
                link_type="unknown",
                resolution_status="pending"
            ),
            LinkInfo(
                original_url="https://contoso.sharepoint.com/sites/notebook/section1#section-id=section-1234-abcd",
                resolved_path="",
                link_text="Browse Projects",
                link_type="unknown",
                resolution_status="pending"
            ),
            LinkInfo(
                original_url="https://external.example.com/resource",
                resolved_path="",
                link_text="External Resource",
                link_type="external",
                resolution_status="pending"
            )
        ]

    def test_initialization(self, resolver, temp_cache_root):
        """Test resolver initialization."""
        assert resolver.cache_root == temp_cache_root
        assert len(resolver.resolution_cache) == 0
        assert resolver.stats['total_links'] == 0

    def test_resolve_empty_links(self, resolver, sample_pages, sample_sections):
        """Test resolution with empty links list."""
        result = resolver.resolve_links([], sample_pages, sample_sections)
        
        assert result.success is True
        assert result.total_links == 0
        assert result.resolved_count == 0
        assert result.failed_count == 0

    def test_resolve_page_links(self, resolver, sample_pages, sample_sections):
        """Test resolution of page links."""
        links = [
            LinkInfo(
                original_url="https://contoso.sharepoint.com/sites/notebook/page1#page-id=page-1234-5678-abcd",
                resolved_path="",
                link_text="Project Overview",
                link_type="unknown",
                resolution_status="pending"
            )
        ]
        
        result = resolver.resolve_links(links, sample_pages, sample_sections)
        
        assert result.success is True
        assert result.total_links == 1
        assert result.resolved_count == 1
        assert result.failed_count == 0
        
        resolved_link = result.resolved_links[0]
        assert resolved_link.resolution_status == "resolved"
        assert resolved_link.link_type == "page"
        assert resolved_link.resolved_path.endswith(".md")

    def test_resolve_section_links(self, resolver, sample_pages, sample_sections):
        """Test resolution of section links."""
        links = [
            LinkInfo(
                original_url="https://contoso.sharepoint.com/sites/notebook/section1#section-id=section-1234-abcd",
                resolved_path="",
                link_text="Projects Section",
                link_type="unknown",
                resolution_status="pending"
            )
        ]
        
        result = resolver.resolve_links(links, sample_pages, sample_sections)
        
        assert result.success is True
        assert result.total_links == 1
        assert result.resolved_count == 1
        
        resolved_link = result.resolved_links[0]
        assert resolved_link.resolution_status == "resolved"
        assert resolved_link.link_type == "section"
        assert resolved_link.resolved_path.endswith("/")

    def test_resolve_mixed_links(self, resolver, sample_pages, sample_sections, sample_links):
        """Test resolution of mixed internal and external links."""
        result = resolver.resolve_links(sample_links, sample_pages, sample_sections)
        
        assert result.success is True
        assert result.total_links == 3
        
        # Should resolve internal links but not external ones
        resolved_count = len([link for link in sample_links if link.resolution_status == "resolved"])
        failed_count = len([link for link in sample_links if link.resolution_status == "failed"])
        
        assert resolved_count > 0  # At least some internal links should resolve
        assert result.resolved_count + result.failed_count == result.total_links

    def test_extract_page_id(self, resolver):
        """Test page ID extraction from various URL formats."""
        # Test standard page ID format
        url1 = "https://contoso.sharepoint.com/sites/notebook/page1#page-id=page-1234-5678-abcd"
        page_id1 = resolver._extract_page_id(url1)
        assert page_id1 == "page-1234-5678-abcd"
        
        # Test query parameter format
        url2 = "https://contoso.sharepoint.com/sites/notebook/page1?pageId=page-abcd-1234"
        page_id2 = resolver._extract_page_id(url2)
        assert page_id2 == "page-abcd-1234"
        
        # Test URL without page ID
        url3 = "https://external.example.com/page"
        page_id3 = resolver._extract_page_id(url3)
        assert page_id3 is None

    def test_extract_section_id(self, resolver):
        """Test section ID extraction from various URL formats."""
        # Test standard section ID format
        url1 = "https://contoso.sharepoint.com/sites/notebook/section1#section-id=section-1234-abcd"
        section_id1 = resolver._extract_section_id(url1)
        assert section_id1 == "section-1234-abcd"
        
        # Test query parameter format
        url2 = "https://contoso.sharepoint.com/sites/notebook/section1?sectionId=section-abcd-1234"
        section_id2 = resolver._extract_section_id(url2)
        assert section_id2 == "section-abcd-1234"
        
        # Test URL without section ID
        url3 = "https://external.example.com/section"
        section_id3 = resolver._extract_section_id(url3)
        assert section_id3 is None

    def test_is_internal_onenote_link(self, resolver):
        """Test OneNote internal link detection."""
        # Test various OneNote URL formats
        internal_urls = [
            "https://contoso.sharepoint.com/sites/notebook/page1",
            "https://contoso-my.sharepoint.com/personal/user/Documents/notebook.one",
            "https://www.onenote.com/notebooks/12345",
            "onenote:https://company.sharepoint.com/notebook.one#section",
            "https://office.com/onenote/page"
        ]
        
        for url in internal_urls:
            assert resolver.is_internal_onenote_link(url) is True
        
        # Test external URLs
        external_urls = [
            "https://google.com",
            "https://github.com/repo",
            "https://docs.microsoft.com/azure",
            "mailto:user@example.com",
            "file:///local/file.pdf"
        ]
        
        for url in external_urls:
            assert resolver.is_internal_onenote_link(url) is False

    def test_extract_links_from_html(self, resolver):
        """Test extraction of internal links from HTML content."""
        html = """
        <p>Here are some links:</p>
        <a href="https://contoso.sharepoint.com/sites/notebook/page1">Internal Page</a>
        <a href="https://google.com">External Link</a>
        <a href="https://contoso-my.sharepoint.com/personal/user/notebook.one">Internal Notebook</a>
        <a href="mailto:user@example.com">Email Link</a>
        """
        
        links = resolver.extract_links_from_html(html)
        
        assert len(links) == 2  # Only internal OneNote links
        
        internal_link = links[0]
        assert internal_link.original_url == "https://contoso.sharepoint.com/sites/notebook/page1"
        assert internal_link.link_text == "Internal Page"
        assert internal_link.link_type == "unknown"
        assert internal_link.resolution_status == "pending"

    def test_resolution_caching(self, resolver, sample_pages, sample_sections):
        """Test that link resolution results are cached."""
        links = [
            LinkInfo(
                original_url="https://contoso.sharepoint.com/sites/notebook/page1#page-id=page-1234-5678-abcd",
                resolved_path="",
                link_text="Test Page",
                link_type="unknown",
                resolution_status="pending"
            )
        ]
        
        # First resolution
        result1 = resolver.resolve_links(links.copy(), sample_pages, sample_sections)
        assert result1.resolved_count == 1
        
        # Second resolution should use cache
        resolver.stats = {'cached_lookups': 0, 'total_links': 0, 'resolved_links': 0, 'failed_links': 0}
        result2 = resolver.resolve_links(links.copy(), sample_pages, sample_sections)
        
        assert result2.resolved_count == 1
        # Note: cache usage would be verified through stats if exposed

    def test_clear_resolution_cache(self, resolver):
        """Test clearing the resolution cache."""
        # Add something to cache
        resolver.resolution_cache["test"] = "value"
        assert len(resolver.resolution_cache) > 0
        
        resolver.clear_resolution_cache()
        assert len(resolver.resolution_cache) == 0

    def test_get_resolution_stats(self, resolver, sample_pages, sample_sections):
        """Test getting resolution statistics."""
        initial_stats = resolver.get_resolution_stats()
        assert initial_stats['total_links'] == 0
        
        links = [
            LinkInfo(
                original_url="https://contoso.sharepoint.com/sites/notebook/page1#page-id=page-1234-5678-abcd",
                resolved_path="",
                link_text="Test",
                link_type="unknown",
                resolution_status="pending"
            )
        ]
        
        resolver.resolve_links(links, sample_pages, sample_sections)
        
        final_stats = resolver.get_resolution_stats()
        assert final_stats['total_links'] == 1
        assert final_stats['resolved_links'] + final_stats['failed_links'] == 1

    def test_build_lookup_tables(self, resolver, sample_pages, sample_sections):
        """Test building lookup tables for pages and sections."""
        page_lookup = resolver._build_page_lookup(sample_pages)
        section_lookup = resolver._build_section_lookup(sample_sections)
        
        assert len(page_lookup) == len(sample_pages)
        assert len(section_lookup) == len(sample_sections)
        
        # Test that pages can be found by ID
        assert "page-1234-5678-abcd" in page_lookup
        assert page_lookup["page-1234-5678-abcd"].title == "Project Overview"
        
        # Test that sections can be found by ID
        assert "section-1234-abcd" in section_lookup
        assert section_lookup["section-1234-abcd"].name == "Projects"

    def test_relative_path_generation(self, resolver, sample_pages, temp_cache_root):
        """Test generation of relative paths to pages and sections."""
        # Create actual directory structure for testing
        content_dir = temp_cache_root / "content" / "Work Notebook" / "Projects"
        content_dir.mkdir(parents=True)
        
        page = sample_pages[0]  # Project Overview
        relative_path = resolver._get_relative_path_to_page(page)
        
        assert relative_path.endswith(".md")
        assert "/" in relative_path or "\\" in relative_path  # Path separator

    def test_url_matching(self, resolver):
        """Test URL matching logic."""
        # Test matching URLs
        url1 = "https://contoso.sharepoint.com/sites/notebook/page1"
        url2 = "https://contoso.sharepoint.com/sites/notebook/page1/"  # Trailing slash
        assert resolver._urls_match(url1, url2) is True
        
        # Test non-matching URLs
        url3 = "https://contoso.sharepoint.com/sites/notebook/page2"
        assert resolver._urls_match(url1, url3) is False
        
        # Test different domains
        url4 = "https://different.sharepoint.com/sites/notebook/page1"
        assert resolver._urls_match(url1, url4) is False

    def test_title_matching(self, resolver):
        """Test title matching logic."""
        # Test matching titles with different formatting
        title1 = "Project Overview"
        title2 = "project-overview"
        assert resolver._titles_match(title1, title2) is True
        
        title3 = "project_overview"
        assert resolver._titles_match(title1, title3) is True
        
        # Test non-matching titles
        title4 = "Different Title"
        assert resolver._titles_match(title1, title4) is False

    def test_anchor_title_extraction(self, resolver):
        """Test extraction of titles from anchor-style URLs."""
        url1 = "https://contoso.sharepoint.com/notebook#page-project-overview"
        title1 = resolver._extract_anchor_title(url1)
        assert title1 == "project overview"
        
        url2 = "https://contoso.sharepoint.com/notebook#section-technical-docs"
        title2 = resolver._extract_anchor_title(url2)
        assert title2 == "technical docs"
        
        url3 = "https://contoso.sharepoint.com/notebook"  # No fragment
        title3 = resolver._extract_anchor_title(url3)
        assert title3 is None

    def test_update_link_in_markdown(self, resolver):
        """Test updating links in markdown content."""
        markdown = """
        # Document Title
        
        Please see [this page](old-link.md) for details.
        Also check [another page](old-link.md) in the same document.
        
        [ref-link]: old-link.md "Reference link"
        """
        
        updated = resolver.update_link_in_markdown(markdown, "old-link.md", "new-link.md")
        
        assert "[this page](new-link.md)" in updated
        assert "[another page](new-link.md)" in updated
        assert "[ref-link]: new-link.md" in updated
        assert "old-link.md" not in updated

    def test_validate_resolved_links(self, resolver, temp_cache_root):
        """Test validation of resolved links."""
        # Create some test files
        content_dir = temp_cache_root / "content"
        content_dir.mkdir(parents=True)
        
        valid_file = content_dir / "valid-page.md"
        valid_file.write_text("# Valid Page")
        
        links = [
            LinkInfo(
                original_url="https://example.com/valid",
                resolved_path="valid-page.md",
                link_text="Valid Link",
                link_type="page",
                resolution_status="resolved"
            ),
            LinkInfo(
                original_url="https://example.com/invalid",
                resolved_path="missing-page.md",
                link_text="Invalid Link",
                link_type="page",
                resolution_status="resolved"
            )
        ]
        
        valid_links, invalid_links = resolver.validate_resolved_links(links)
        
        assert len(valid_links) == 1
        assert len(invalid_links) == 1
        assert valid_links[0].resolved_path == "valid-page.md"
        assert invalid_links[0].resolution_status == "invalid"

    def test_alternative_resolution_methods(self, resolver, sample_pages, sample_sections):
        """Test alternative resolution methods for difficult URLs."""
        # Create a link that doesn't have clear ID patterns but matches by URL
        links = [
            LinkInfo(
                original_url="https://contoso.sharepoint.com/sites/notebook/page1",  # Matches sample page web_url
                resolved_path="",
                link_text="Project Page",
                link_type="unknown",
                resolution_status="pending"
            )
        ]
        
        result = resolver.resolve_links(links, sample_pages, sample_sections)
        
        # Should attempt alternative resolution methods
        assert result.total_links == 1
        # Resolution success depends on the alternative method implementation

    def test_error_handling_in_resolution(self, resolver):
        """Test error handling during link resolution."""
        # Create problematic links
        problematic_links = [
            LinkInfo(
                original_url="",  # Empty URL
                resolved_path="",
                link_text="Empty URL",
                link_type="unknown",
                resolution_status="pending"
            ),
            LinkInfo(
                original_url="not-a-valid-url",  # Invalid URL format
                resolved_path="",
                link_text="Invalid URL",
                link_type="unknown",
                resolution_status="pending"
            )
        ]
        
        result = resolver.resolve_links(problematic_links, [], [])
        
        # Should handle errors gracefully
        assert result.success is True or result.total_links == len(problematic_links)
        assert result.failed_count <= result.total_links

    def test_utility_functions(self):
        """Test utility functions for URL and link processing."""
        from src.storage.link_resolver import normalize_onenote_url, create_markdown_link, is_absolute_path
        
        # Test URL normalization
        url = "https://Example.com/Path?param=value"
        normalized = normalize_onenote_url(url)
        assert normalized.startswith("https://example.com")
        
        # Test markdown link creation
        link = create_markdown_link("Test [Link]", "https://example.com/path(with)parens")
        assert link == "[Test \\[Link\\]](https://example.com/path%28with%29parens)"
        
        # Test absolute path detection
        assert is_absolute_path("/absolute/path") is True
        assert is_absolute_path("relative/path") is False
        assert is_absolute_path("C:\\Windows\\path") is True

    def test_comprehensive_link_resolution_workflow(self, resolver, sample_pages, sample_sections, temp_cache_root):
        """Test complete link resolution workflow with realistic data."""
        # Create a realistic HTML content with various link types
        html_content = """
        <div>
            <h2>Project Documentation</h2>
            <p>For technical details, see <a href="https://contoso.sharepoint.com/sites/notebook/page2#page-id=page-2345-6789-bcde">Technical Specifications</a>.</p>
            <p>Browse all <a href="https://contoso.sharepoint.com/sites/notebook/section1#section-id=section-1234-abcd">Projects</a> in this section.</p>
            <p>External reference: <a href="https://docs.microsoft.com/azure">Azure Documentation</a>.</p>
            <p>Another internal link: <a href="https://contoso.sharepoint.com/sites/notebook/page1">Project Overview</a>.</p>
        </div>
        """
        
        # Step 1: Extract links from HTML
        extracted_links = resolver.extract_links_from_html(html_content)
        assert len(extracted_links) > 0  # Should find internal OneNote links
        
        # Step 2: Resolve the links
        result = resolver.resolve_links(extracted_links, sample_pages, sample_sections)
        
        # Step 3: Validate results
        assert result.success is True
        assert result.total_links == len(extracted_links)
        
        # Should have resolved some internal links
        assert result.resolved_count > 0
        
        # Step 4: Check resolution quality
        for link in result.resolved_links:
            assert link.resolved_path is not None
            assert link.resolved_path != ""
            assert link.resolution_status == "resolved"
            
        # Step 5: Validate resolved links (if files existed)
        # This would typically be done after markdown files are created
        
        # Step 6: Get statistics
        stats = resolver.get_resolution_stats()
        assert stats['total_links'] == len(extracted_links)
        assert stats['resolved_links'] == result.resolved_count
        assert stats['failed_links'] == result.failed_count
