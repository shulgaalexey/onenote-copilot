"""
Integration tests for MarkdownConverter.

Tests the real MarkdownConverter implementation with various HTML content
and validates conversion accuracy, asset linking, and link resolution.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.storage.markdown_converter import MarkdownConverter
from src.models.cache import AssetInfo, LinkInfo, MarkdownConversionResult


class TestMarkdownConverterIntegration:
    """Integration tests for MarkdownConverter functionality."""

    @pytest.fixture
    def converter(self):
        """Create a markdown converter instance."""
        return MarkdownConverter(preserve_whitespace=True, include_metadata=True)

    @pytest.fixture
    def simple_converter(self):
        """Create a simple markdown converter without metadata."""
        return MarkdownConverter(preserve_whitespace=False, include_metadata=False)

    @pytest.fixture
    def sample_assets(self):
        """Create sample asset information."""
        return [
            AssetInfo(
                type="image",
                original_url="https://example.com/image1.png",
                local_path=str(Path("/cache/attachments/image1.png")),
                filename="image1.png",
                size_bytes=1024,
                mime_type="image/png",
                download_status="completed"
            ),
            AssetInfo(
                type="file",
                original_url="https://example.com/document.pdf",
                local_path=str(Path("/cache/attachments/document.pdf")),
                filename="document.pdf",
                size_bytes=2048,
                mime_type="application/pdf",
                download_status="completed"
            )
        ]

    @pytest.fixture
    def sample_links(self):
        """Create sample internal link information."""
        return [
            LinkInfo(
                original_url="https://contoso.sharepoint.com/sites/notebook/page1",
                resolved_path="../section1/page1.md",
                link_text="Page 1",
                link_type="page",
                resolution_status="resolved"
            ),
            LinkInfo(
                original_url="https://contoso.sharepoint.com/sites/notebook/section2",
                resolved_path="../section2/",
                link_text="Section 2",
                link_type="section",
                resolution_status="resolved"
            )
        ]

    def test_initialization(self, converter, simple_converter):
        """Test converter initialization with different settings."""
        # Test default converter
        assert converter.preserve_whitespace is True
        assert converter.include_metadata is True
        assert converter.stats['elements_converted'] == 0
        
        # Test simple converter
        assert simple_converter.preserve_whitespace is False
        assert simple_converter.include_metadata is False

    def test_convert_empty_content(self, converter):
        """Test conversion of empty content."""
        result = converter.convert_to_markdown("", [], [], "Test Page")
        
        assert result.success is True
        assert result.markdown_content.strip() == "# Test Page"
        assert result.elements_converted == 0
        assert result.assets_linked == 0

    def test_convert_simple_html(self, converter):
        """Test conversion of simple HTML content."""
        html = "<p>This is a <strong>bold</strong> paragraph with <em>italic</em> text.</p>"
        
        result = converter.convert_to_markdown(html, [], [], "Simple Test")
        
        assert result.success is True
        assert "# Simple Test" in result.markdown_content
        assert "This is a **bold** paragraph with *italic* text." in result.markdown_content
        assert result.elements_converted > 0

    def test_convert_headings(self, converter):
        """Test conversion of heading elements."""
        html = """
        <h1>Heading 1</h1>
        <h2>Heading 2</h2>
        <h3>Heading 3</h3>
        <p>Some content.</p>
        """
        
        result = converter.convert_to_markdown(html, [], [], "")
        
        assert result.success is True
        markdown = result.markdown_content
        assert "# Heading 1" in markdown
        assert "## Heading 2" in markdown
        assert "### Heading 3" in markdown
        assert "Some content." in markdown

    def test_convert_lists(self, converter):
        """Test conversion of list elements."""
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
        
        result = converter.convert_to_markdown(html, [], [], "")
        
        assert result.success is True
        markdown = result.markdown_content
        assert "- Unordered item 1" in markdown
        assert "- Unordered item 2" in markdown
        assert "1. Ordered item 1" in markdown
        assert "2. Ordered item 2" in markdown

    def test_convert_images_with_assets(self, converter, sample_assets):
        """Test conversion of images with asset linking."""
        html = """
        <p>Here is an image:</p>
        <img src="https://example.com/image1.png" alt="Test Image" />
        <p>And another:</p>
        <img src="https://example.com/missing.jpg" alt="Missing Image" />
        """
        
        result = converter.convert_to_markdown(html, sample_assets, [], "")
        
        assert result.success is True
        markdown = result.markdown_content
        assert "![Test Image](../attachments/image1.png)" in markdown
        assert "![Missing Image](https://example.com/missing.jpg)" in markdown
        assert result.assets_linked == 1

    def test_convert_links_with_resolution(self, converter, sample_links):
        """Test conversion of links with resolution."""
        html = """
        <p>Here are some links:</p>
        <a href="https://contoso.sharepoint.com/sites/notebook/page1">Page 1</a>
        <a href="https://contoso.sharepoint.com/sites/notebook/section2">Section 2</a>
        <a href="https://external.com">External Link</a>
        """
        
        result = converter.convert_to_markdown(html, [], sample_links, "")
        
        assert result.success is True
        markdown = result.markdown_content
        assert "[Page 1](../section1/page1.md)" in markdown
        assert "[Section 2](../section2/)" in markdown
        assert "[External Link](https://external.com)" in markdown
        assert result.internal_links_resolved == 2
        assert result.external_links_preserved == 1

    def test_convert_table(self, converter):
        """Test conversion of table elements."""
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
            <tr>
                <td>Cell 3</td>
                <td>Cell 4</td>
            </tr>
        </table>
        """
        
        result = converter.convert_to_markdown(html, [], [], "")
        
        assert result.success is True
        markdown = result.markdown_content
        assert "| **Header 1** | **Header 2** |" in markdown
        assert "| --- | --- |" in markdown
        assert "| Cell 1 | Cell 2 |" in markdown
        assert "| Cell 3 | Cell 4 |" in markdown

    def test_convert_code_blocks(self, converter):
        """Test conversion of code elements."""
        html = """
        <p>Inline code: <code>print('hello')</code></p>
        <pre><code class="language-python">
def hello():
    print("Hello, World!")
        </code></pre>
        """
        
        result = converter.convert_to_markdown(html, [], [], "")
        
        assert result.success is True
        markdown = result.markdown_content
        assert "`print('hello')`" in markdown
        assert "```python" in markdown
        assert "def hello():" in markdown

    def test_convert_onenote_specific_elements(self, converter):
        """Test conversion of OneNote-specific HTML structures."""
        html = """
        <div class="OutlineElement">
            <p>This is an outline element.</p>
        </div>
        <div class="normal">
            <p>This is a normal div.</p>
        </div>
        """
        
        result = converter.convert_to_markdown(html, [], [], "")
        
        assert result.success is True
        markdown = result.markdown_content
        assert "This is an outline element." in markdown
        assert "This is a normal div." in markdown

    def test_convert_with_metadata(self, converter):
        """Test conversion with metadata inclusion."""
        html = "<p>Content with metadata.</p>"
        
        result = converter.convert_to_markdown(html, [], [], "Test Page Title")
        
        assert result.success is True
        assert result.markdown_content.startswith("# Test Page Title")
        assert "Content with metadata." in result.markdown_content

    def test_convert_without_metadata(self, simple_converter):
        """Test conversion without metadata inclusion."""
        html = "<p>Content without metadata.</p>"
        
        result = simple_converter.convert_to_markdown(html, [], [], "Test Page Title")
        
        assert result.success is True
        assert not result.markdown_content.startswith("# Test Page Title")
        assert "Content without metadata." in result.markdown_content

    def test_conversion_statistics(self, converter):
        """Test that conversion statistics are properly tracked."""
        html = """
        <h1>Title</h1>
        <p>Paragraph with <strong>bold</strong> and <em>italic</em>.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        <img src="https://example.com/image.png" alt="Image" />
        """
        assets = [AssetInfo(
            type="image",
            original_url="https://example.com/image.png",
            local_path="/cache/attachments/image.png",
            filename="image.png",
            size_bytes=1024,
            mime_type="image/png",
            download_status="completed"
        )]
        
        result = converter.convert_to_markdown(html, assets, [], "")
        
        assert result.success is True
        assert result.elements_converted > 5  # Multiple elements converted
        assert result.assets_linked == 1
        assert result.internal_links_resolved == 0
        assert result.external_links_preserved == 0
        assert len(result.warnings) == 0

    def test_conversion_error_handling(self, converter):
        """Test error handling during conversion."""
        # Test with malformed HTML
        malformed_html = "<p>Unclosed paragraph<div><span>Nested without closing"
        
        result = converter.convert_to_markdown(malformed_html, [], [], "")
        
        # Should still succeed with BeautifulSoup's error recovery
        assert result.success is True

    def test_get_conversion_stats(self, converter):
        """Test getting conversion statistics."""
        initial_stats = converter.get_conversion_stats()
        assert initial_stats['elements_converted'] == 0
        
        html = "<p>Test <strong>content</strong>.</p>"
        converter.convert_to_markdown(html, [], [], "")
        
        final_stats = converter.get_conversion_stats()
        assert final_stats['elements_converted'] > 0

    def test_estimate_conversion_time(self, converter):
        """Test conversion time estimation."""
        # Small content
        small_html = "<p>Small content.</p>"
        small_time = converter.estimate_conversion_time(small_html)
        assert small_time >= 0.1
        
        # Large content with complex elements
        large_html = """
        <table>
            <tr><th>Col1</th><th>Col2</th></tr>
            <tr><td>Data1</td><td>Data2</td></tr>
        </table>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        """ * 100  # Repeat to make it large
        
        large_time = converter.estimate_conversion_time(large_html)
        assert large_time > small_time

    def test_relative_asset_path_calculation(self, converter):
        """Test relative asset path calculation."""
        # Test the internal method
        asset_path = "/cache/attachments/subfolder/image.png"
        rel_path = converter._get_relative_asset_path(asset_path)
        
        # Should create a relative path to attachments
        assert "attachments" in rel_path
        assert rel_path.endswith("image.png")

    def test_markdown_cleaning(self, converter):
        """Test markdown content cleaning."""
        # Test with content that needs cleaning
        dirty_content = "Text with ** ** empty bold and   \n\n\n\n   multiple newlines"
        
        cleaned = converter._clean_markdown(dirty_content)
        
        # Should remove empty formatting and excessive whitespace
        assert "** **" not in cleaned
        assert "\n\n\n" not in cleaned

    def test_text_escaping_utilities(self):
        """Test utility functions for text escaping."""
        from src.storage.markdown_converter import clean_text_for_markdown, extract_text_content
        
        # Test markdown escaping
        dirty_text = "Text with * and _ and # special chars"
        clean_text = clean_text_for_markdown(dirty_text)
        assert "\\*" in clean_text
        assert "\\_" in clean_text
        assert "\\#" in clean_text
        
        # Test text extraction
        html = "<p>Extract <strong>this</strong> text.</p>"
        text = extract_text_content(html)
        assert text == "Extract this text."

    def test_filename_validation(self):
        """Test markdown filename validation."""
        from src.storage.markdown_converter import is_valid_markdown_filename
        
        assert is_valid_markdown_filename("valid_file.md") is True
        assert is_valid_markdown_filename("invalid_file.txt") is False
        assert is_valid_markdown_filename("no-extension") is False

    def test_complex_nested_content(self, converter, sample_assets, sample_links):
        """Test conversion of complex nested HTML content."""
        html = """
        <div class="OutlineElement">
            <h2>Project Overview</h2>
            <p>This project contains <strong>important</strong> information about:</p>
            <ul>
                <li>Feature specifications with <a href="https://contoso.sharepoint.com/sites/notebook/page1">detailed requirements</a></li>
                <li>Technical architecture</li>
                <li>Implementation timeline</li>
            </ul>
            <p>Reference image: <img src="https://example.com/image1.png" alt="Architecture Diagram" /></p>
            <table>
                <tr>
                    <th>Phase</th>
                    <th>Duration</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>Planning</td>
                    <td>2 weeks</td>
                    <td><em>Complete</em></td>
                </tr>
                <tr>
                    <td>Development</td>
                    <td>6 weeks</td>
                    <td><strong>In Progress</strong></td>
                </tr>
            </table>
            <blockquote>
                <p>Note: All deliverables must be completed by the end of Q1.</p>
            </blockquote>
        </div>
        """
        
        result = converter.convert_to_markdown(html, sample_assets, sample_links, "Project Status")
        
        assert result.success is True
        markdown = result.markdown_content
        
        # Check all elements are converted
        assert "# Project Status" in markdown
        assert "## Project Overview" in markdown
        assert "**important**" in markdown
        assert "- Feature specifications" in markdown
        assert "[detailed requirements](../section1/page1.md)" in markdown
        assert "![Architecture Diagram](../attachments/image1.png)" in markdown
        assert "| **Phase** | **Duration** | **Status** |" in markdown
        assert "> Note: All deliverables" in markdown
        
        # Check statistics
        assert result.elements_converted > 10
        assert result.assets_linked == 1
        assert result.internal_links_resolved == 1
        assert result.external_links_preserved == 0

    def test_error_recovery_and_warnings(self, converter):
        """Test that converter recovers from errors and logs warnings."""
        # Create HTML with problematic elements that might cause conversion issues
        html = """
        <customtag>Unknown element</customtag>
        <p>Valid paragraph</p>
        <img />
        <a>Link without href</a>
        """
        
        result = converter.convert_to_markdown(html, [], [], "")
        
        # Should still succeed despite issues
        assert result.success is True
        assert "Valid paragraph" in result.markdown_content
        
        # May have generated warnings
        # Note: warnings depend on specific implementation behavior
