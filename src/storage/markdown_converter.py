"""
Markdown converter for OneNote cache system.

Converts OneNote HTML content to clean, readable Markdown with proper
formatting, asset linking, and internal link resolution.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup, Tag, NavigableString

from ..models.cache import AssetInfo, LinkInfo, MarkdownConversionResult
from .directory_utils import sanitize_filename

logger = logging.getLogger(__name__)


class MarkdownConverter:
    """
    Converts OneNote HTML content to Markdown format.
    
    Handles HTML parsing, element conversion, asset linking,
    and internal link resolution for clean Markdown output.
    """

    def __init__(self, preserve_whitespace: bool = True, 
                 include_metadata: bool = True):
        """
        Initialize the markdown converter.

        Args:
            preserve_whitespace: Whether to preserve original whitespace
            include_metadata: Whether to include OneNote metadata in output
        """
        self.preserve_whitespace = preserve_whitespace
        self.include_metadata = include_metadata
        
        # Conversion statistics
        self.stats = {
            'elements_converted': 0,
            'assets_linked': 0,
            'internal_links_resolved': 0,
            'external_links_preserved': 0,
            'warnings': []
        }
        
        # Element handlers mapping
        self.element_handlers = {
            'h1': self._convert_heading,
            'h2': self._convert_heading,
            'h3': self._convert_heading,
            'h4': self._convert_heading,
            'h5': self._convert_heading,
            'h6': self._convert_heading,
            'p': self._convert_paragraph,
            'div': self._convert_div,
            'span': self._convert_span,
            'strong': self._convert_strong,
            'b': self._convert_strong,
            'em': self._convert_emphasis,
            'i': self._convert_emphasis,
            'u': self._convert_underline,
            'a': self._convert_link,
            'img': self._convert_image,
            'ul': self._convert_unordered_list,
            'ol': self._convert_ordered_list,
            'li': self._convert_list_item,
            'br': self._convert_line_break,
            'hr': self._convert_horizontal_rule,
            'blockquote': self._convert_blockquote,
            'code': self._convert_inline_code,
            'pre': self._convert_code_block,
            'table': self._convert_table,
            'tr': self._convert_table_row,
            'td': self._convert_table_cell,
            'th': self._convert_table_header,
        }

        logger.debug("Initialized markdown converter")

    def convert_to_markdown(self, html_content: str, assets: List[AssetInfo],
                          internal_links: List[LinkInfo],
                          page_title: str = "") -> MarkdownConversionResult:
        """
        Convert OneNote HTML content to Markdown.

        Args:
            html_content: HTML content to convert
            assets: List of assets referenced in the content
            internal_links: List of internal links to resolve
            page_title: Title of the page for metadata

        Returns:
            Conversion result with markdown content and statistics
        """
        result = MarkdownConversionResult()
        result.original_html = html_content
        
        try:
            # Reset statistics
            self.stats = {
                'elements_converted': 0,
                'assets_linked': 0,
                'internal_links_resolved': 0,
                'external_links_preserved': 0,
                'warnings': []
            }

            # Parse HTML content
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Build asset lookup for quick reference
            asset_lookup = {asset.original_url: asset for asset in assets}
            
            # Build internal link lookup
            link_lookup = {link.original_url: link for link in internal_links}

            # Convert to markdown
            markdown_lines = []
            
            # Add title if provided and metadata enabled
            if self.include_metadata and page_title:
                markdown_lines.append(f"# {page_title}")
                markdown_lines.append("")

            # Process body content
            body = soup.find('body') or soup
            converted_content = self._convert_element(body, asset_lookup, link_lookup)
            
            # Clean up the converted content
            cleaned_content = self._clean_markdown(converted_content)
            markdown_lines.append(cleaned_content)

            # Join lines and finalize
            result.markdown_content = '\n'.join(markdown_lines).strip()
            
            # Copy statistics
            result.elements_converted = self.stats['elements_converted']
            result.assets_linked = self.stats['assets_linked']
            result.internal_links_resolved = self.stats['internal_links_resolved']
            result.external_links_preserved = self.stats['external_links_preserved']
            result.warnings = self.stats['warnings'].copy()
            
            result.success = True
            
            logger.debug(f"Converted HTML to Markdown: {result.elements_converted} elements, "
                        f"{result.assets_linked} assets, {result.internal_links_resolved} internal links")

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error(f"Markdown conversion failed: {e}")

        return result

    def _convert_element(self, element, asset_lookup: Dict[str, AssetInfo], 
                        link_lookup: Dict[str, LinkInfo]) -> str:
        """
        Convert a single HTML element to Markdown.

        Args:
            element: BeautifulSoup element to convert
            asset_lookup: Dictionary of assets by URL
            link_lookup: Dictionary of internal links by URL

        Returns:
            Markdown representation of the element
        """
        if isinstance(element, NavigableString):
            return str(element).strip()

        if not isinstance(element, Tag):
            return ""

        tag_name = element.name.lower() if element.name else ""
        
        # Get handler for this element type
        handler = self.element_handlers.get(tag_name)
        
        if handler:
            try:
                self.stats['elements_converted'] += 1
                return handler(element, asset_lookup, link_lookup)
            except Exception as e:
                warning = f"Failed to convert {tag_name} element: {e}"
                self.stats['warnings'].append(warning)
                logger.warning(warning)
                # Fallback to processing children
                return self._process_children(element, asset_lookup, link_lookup)
        else:
            # No specific handler, process children
            return self._process_children(element, asset_lookup, link_lookup)

    def _process_children(self, element, asset_lookup: Dict[str, AssetInfo], 
                         link_lookup: Dict[str, LinkInfo]) -> str:
        """Process child elements of an element."""
        parts = []
        for child in element.children:
            converted = self._convert_element(child, asset_lookup, link_lookup)
            if converted.strip():
                parts.append(converted)
        return ''.join(parts)

    def _convert_heading(self, element, asset_lookup: Dict[str, AssetInfo], 
                        link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert heading elements."""
        level = int(element.name[1])  # h1 -> 1, h2 -> 2, etc.
        content = self._process_children(element, asset_lookup, link_lookup)
        return f"\n{'#' * level} {content.strip()}\n\n"

    def _convert_paragraph(self, element, asset_lookup: Dict[str, AssetInfo], 
                          link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert paragraph elements."""
        content = self._process_children(element, asset_lookup, link_lookup)
        if not content.strip():
            return ""
        return f"{content.strip()}\n\n"

    def _convert_div(self, element, asset_lookup: Dict[str, AssetInfo], 
                    link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert div elements."""
        # Check for special OneNote div classes
        classes = element.get('class', [])
        
        if 'OutlineElement' in classes:
            # OneNote outline element
            content = self._process_children(element, asset_lookup, link_lookup)
            return f"{content.strip()}\n\n"
        else:
            # Regular div - process children without adding extra formatting
            return self._process_children(element, asset_lookup, link_lookup)

    def _convert_span(self, element, asset_lookup: Dict[str, AssetInfo], 
                     link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert span elements."""
        # Check for special formatting in span styles
        style = element.get('style', '')
        content = self._process_children(element, asset_lookup, link_lookup)
        
        # Apply formatting based on style
        if 'font-weight:bold' in style or 'font-weight: bold' in style:
            return f"**{content}**"
        elif 'font-style:italic' in style or 'font-style: italic' in style:
            return f"*{content}*"
        else:
            return content

    def _convert_strong(self, element, asset_lookup: Dict[str, AssetInfo], 
                       link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert strong/b elements."""
        content = self._process_children(element, asset_lookup, link_lookup)
        return f"**{content}**"

    def _convert_emphasis(self, element, asset_lookup: Dict[str, AssetInfo], 
                         link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert em/i elements."""
        content = self._process_children(element, asset_lookup, link_lookup)
        return f"*{content}*"

    def _convert_underline(self, element, asset_lookup: Dict[str, AssetInfo], 
                          link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert u elements."""
        content = self._process_children(element, asset_lookup, link_lookup)
        # Markdown doesn't have native underline, use HTML
        return f"<u>{content}</u>"

    def _convert_link(self, element, asset_lookup: Dict[str, AssetInfo], 
                     link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert anchor/link elements."""
        href = element.get('href', '')
        content = self._process_children(element, asset_lookup, link_lookup)
        
        if not href:
            return content
        
        # Check if this is an internal link that should be resolved
        if href in link_lookup:
            link_info = link_lookup[href]
            if link_info.resolved_path:
                self.stats['internal_links_resolved'] += 1
                return f"[{content}]({link_info.resolved_path})"
        
        # External link or unresolved internal link
        self.stats['external_links_preserved'] += 1
        return f"[{content}]({href})"

    def _convert_image(self, element, asset_lookup: Dict[str, AssetInfo], 
                      link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert image elements."""
        src = element.get('src', '')
        alt = element.get('alt', '')
        
        if not src:
            return f"![{alt}]()"
        
        # Check if this image is in our assets
        if src in asset_lookup:
            asset = asset_lookup[src]
            if asset.local_path:
                self.stats['assets_linked'] += 1
                # Use relative path from markdown file to asset
                rel_path = self._get_relative_asset_path(asset.local_path)
                return f"![{alt or asset.filename}]({rel_path})"
        
        # Fallback to original URL
        return f"![{alt}]({src})"

    def _convert_unordered_list(self, element, asset_lookup: Dict[str, AssetInfo], 
                               link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert ul elements."""
        items = []
        for li in element.find_all('li', recursive=False):
            item_content = self._convert_element(li, asset_lookup, link_lookup)
            items.append(f"- {item_content.strip()}")
        
        if items:
            return '\n' + '\n'.join(items) + '\n\n'
        return ""

    def _convert_ordered_list(self, element, asset_lookup: Dict[str, AssetInfo], 
                             link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert ol elements."""
        items = []
        for i, li in enumerate(element.find_all('li', recursive=False), 1):
            item_content = self._convert_element(li, asset_lookup, link_lookup)
            items.append(f"{i}. {item_content.strip()}")
        
        if items:
            return '\n' + '\n'.join(items) + '\n\n'
        return ""

    def _convert_list_item(self, element, asset_lookup: Dict[str, AssetInfo], 
                          link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert li elements."""
        return self._process_children(element, asset_lookup, link_lookup)

    def _convert_line_break(self, element, asset_lookup: Dict[str, AssetInfo], 
                           link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert br elements."""
        return "\n"

    def _convert_horizontal_rule(self, element, asset_lookup: Dict[str, AssetInfo], 
                                link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert hr elements."""
        return "\n---\n\n"

    def _convert_blockquote(self, element, asset_lookup: Dict[str, AssetInfo], 
                           link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert blockquote elements."""
        content = self._process_children(element, asset_lookup, link_lookup)
        lines = content.strip().split('\n')
        quoted_lines = [f"> {line}" for line in lines]
        return '\n' + '\n'.join(quoted_lines) + '\n\n'

    def _convert_inline_code(self, element, asset_lookup: Dict[str, AssetInfo], 
                            link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert inline code elements."""
        content = element.get_text()
        return f"`{content}`"

    def _convert_code_block(self, element, asset_lookup: Dict[str, AssetInfo], 
                           link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert pre/code block elements."""
        content = element.get_text()
        language = ""
        
        # Try to detect language from class
        if element.name == 'pre':
            code_element = element.find('code')
            if code_element:
                classes = code_element.get('class', [])
                for cls in classes:
                    if cls.startswith('language-'):
                        language = cls[9:]
                        break
        
        return f"\n```{language}\n{content}\n```\n\n"

    def _convert_table(self, element, asset_lookup: Dict[str, AssetInfo], 
                      link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert table elements."""
        rows = []
        
        # Process table rows
        for row in element.find_all('tr'):
            row_content = self._convert_element(row, asset_lookup, link_lookup)
            if row_content.strip():
                rows.append(row_content.strip())
        
        if not rows:
            return ""
        
        # Add header separator if first row contains th elements
        first_row = element.find('tr')
        if first_row and first_row.find('th'):
            # Count columns for separator
            col_count = len(first_row.find_all(['th', 'td']))
            separator = '| ' + ' | '.join(['---'] * col_count) + ' |'
            rows.insert(1, separator)
        
        return '\n' + '\n'.join(rows) + '\n\n'

    def _convert_table_row(self, element, asset_lookup: Dict[str, AssetInfo], 
                          link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert tr elements."""
        cells = []
        for cell in element.find_all(['td', 'th']):
            cell_content = self._convert_element(cell, asset_lookup, link_lookup)
            cells.append(cell_content.strip().replace('|', '\\|'))  # Escape pipes
        
        return '| ' + ' | '.join(cells) + ' |'

    def _convert_table_cell(self, element, asset_lookup: Dict[str, AssetInfo], 
                           link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert td elements."""
        return self._process_children(element, asset_lookup, link_lookup)

    def _convert_table_header(self, element, asset_lookup: Dict[str, AssetInfo], 
                             link_lookup: Dict[str, LinkInfo]) -> str:
        """Convert th elements."""
        content = self._process_children(element, asset_lookup, link_lookup)
        return f"**{content}**"  # Make headers bold in markdown tables

    def _get_relative_asset_path(self, asset_local_path: str) -> str:
        """
        Get relative path from markdown file to asset.

        Args:
            asset_local_path: Absolute path to the asset

        Returns:
            Relative path suitable for markdown links
        """
        try:
            # For now, use relative path assuming markdown is in content directory
            # and assets are in attachments directory
            asset_path = Path(asset_local_path)
            
            # Create relative path from content to attachments
            # This assumes structure: cache/content/... and cache/attachments/...
            if 'attachments' in asset_path.parts:
                # Find the attachments part and construct relative path
                parts = asset_path.parts
                attachments_index = parts.index('attachments')
                rel_parts = ['..', 'attachments'] + list(parts[attachments_index + 1:])
                return '/'.join(rel_parts)
            else:
                # Fallback to just the filename
                return asset_path.name

        except Exception as e:
            logger.warning(f"Failed to create relative asset path: {e}")
            return Path(asset_local_path).name

    def _clean_markdown(self, content: str) -> str:
        """
        Clean up converted markdown content.

        Args:
            content: Raw converted content

        Returns:
            Cleaned markdown content
        """
        try:
            # Remove excessive whitespace
            cleaned = re.sub(r'\n{3,}', '\n\n', content)
            
            # Remove leading/trailing whitespace from lines
            lines = [line.rstrip() for line in cleaned.split('\n')]
            cleaned = '\n'.join(lines)
            
            # Remove empty formatting
            cleaned = re.sub(r'\*\*\s*\*\*', '', cleaned)  # Empty bold
            cleaned = re.sub(r'\*\s*\*', '', cleaned)      # Empty italic
            cleaned = re.sub(r'`\s*`', '', cleaned)        # Empty code
            
            # Clean up list spacing
            cleaned = re.sub(r'\n-\s*\n', '\n- \n', cleaned)
            cleaned = re.sub(r'\n\d+\.\s*\n', lambda m: m.group(0).replace('\n', ' '), cleaned)
            
            # Normalize link formatting
            cleaned = re.sub(r'\[([^\]]*)\]\(\s*\)', r'\1', cleaned)  # Remove empty links
            
            return cleaned.strip()

        except Exception as e:
            logger.warning(f"Failed to clean markdown: {e}")
            return content

    def get_conversion_stats(self) -> Dict[str, any]:
        """
        Get current conversion statistics.

        Returns:
            Dictionary with conversion statistics
        """
        return self.stats.copy()

    def estimate_conversion_time(self, html_content: str) -> float:
        """
        Estimate conversion time for HTML content.

        Args:
            html_content: HTML content to estimate for

        Returns:
            Estimated conversion time in seconds
        """
        try:
            # Rough estimate based on content length and complexity
            base_time = len(html_content) / 10000  # 0.1s per 10KB
            
            # Add time for complex elements
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Count complex elements that take more processing
            tables = len(soup.find_all('table'))
            images = len(soup.find_all('img'))
            lists = len(soup.find_all(['ul', 'ol']))
            links = len(soup.find_all('a'))
            
            complexity_time = (tables * 0.1) + (images * 0.05) + (lists * 0.02) + (links * 0.01)
            
            return max(0.1, base_time + complexity_time)

        except Exception:
            # Fallback estimate
            return max(0.1, len(html_content) / 50000)


# Utility functions

def clean_text_for_markdown(text: str) -> str:
    """
    Clean text for safe inclusion in Markdown.

    Args:
        text: Text to clean

    Returns:
        Cleaned text safe for Markdown
    """
    if not text:
        return ""
    
    # Escape markdown special characters
    text = text.replace('\\', '\\\\')  # Backslash
    text = text.replace('*', '\\*')    # Asterisk
    text = text.replace('_', '\\_')    # Underscore
    text = text.replace('#', '\\#')    # Hash
    text = text.replace('`', '\\`')    # Backtick
    text = text.replace('[', '\\[')    # Square bracket
    text = text.replace(']', '\\]')    # Square bracket
    text = text.replace('(', '\\(')    # Parenthesis
    text = text.replace(')', '\\)')    # Parenthesis
    
    return text


def extract_text_content(html: str) -> str:
    """
    Extract plain text content from HTML.

    Args:
        html: HTML content

    Returns:
        Plain text content
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text().strip()
    except Exception as e:
        logger.error(f"Failed to extract text content: {e}")
        return ""


def get_markdown_file_extension() -> str:
    """Get the standard markdown file extension."""
    return ".md"


def is_valid_markdown_filename(filename: str) -> bool:
    """
    Check if a filename is valid for markdown files.

    Args:
        filename: Filename to check

    Returns:
        True if filename is valid
    """
    try:
        # Check extension
        if not filename.endswith('.md'):
            return False
        
        # Check for valid characters
        path = Path(filename)
        sanitized = sanitize_filename(path.stem) + '.md'
        
        return filename == sanitized
    
    except Exception:
        return False
