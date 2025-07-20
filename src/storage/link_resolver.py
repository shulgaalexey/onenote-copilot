"""
Link resolver for OneNote cache system.

Resolves internal OneNote links to local markdown files, handling
section links, page links, and hierarchical navigation.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs, unquote

from ..config.settings import get_settings
from ..models.cache import LinkInfo, LinkResolutionResult, OneNotePage, OneNoteSection
from .directory_utils import get_content_path_for_page, get_content_path_for_section, sanitize_filename

logger = logging.getLogger(__name__)


class LinkResolver:
    """
    Resolves OneNote internal links to local markdown file paths.
    
    Handles various OneNote link formats and converts them to relative
    paths in the local cache structure.
    """

    def __init__(self, cache_root: Path):
        """
        Initialize the link resolver.

        Args:
            cache_root: Root directory of the cache
        """
        self.cache_root = cache_root
        self.settings = get_settings()
        
        # Link pattern matchers
        self.onenote_patterns = [
            # Standard OneNote web links
            r'https://[^/]+\.sharepoint\.com/.*/([^/]+)\.one#.*',
            # OneNote desktop links
            r'onenote:.*#.*',
            # OneNote online links
            r'https://[^/]+\.onenote\.com/.*',
            # Section links
            r'#section-id=([a-zA-Z0-9-]+)',
            # Page links  
            r'#page-id=([a-zA-Z0-9-]+)',
        ]
        
        # Cache for resolved links to avoid repeated lookups
        self.resolution_cache: Dict[str, Optional[str]] = {}
        
        # Statistics
        self.stats = {
            'total_links': 0,
            'resolved_links': 0,
            'failed_links': 0,
            'cached_lookups': 0
        }

        logger.debug(f"Initialized link resolver for cache root: {cache_root}")

    def resolve_links(self, links: List[LinkInfo], pages: List[OneNotePage], 
                     sections: List[OneNoteSection]) -> LinkResolutionResult:
        """
        Resolve a list of internal links to local paths.

        Args:
            links: List of links to resolve
            pages: List of available pages
            sections: List of available sections

        Returns:
            Resolution result with statistics
        """
        result = LinkResolutionResult()
        result.total_links = len(links)
        
        if not links:
            result.success = True
            return result

        try:
            logger.info(f"Resolving {len(links)} internal links")
            
            # Reset stats
            self.stats = {
                'total_links': len(links),
                'resolved_links': 0,
                'failed_links': 0,
                'cached_lookups': 0
            }

            # Build lookup tables for pages and sections
            page_lookup = self._build_page_lookup(pages)
            section_lookup = self._build_section_lookup(sections)
            
            # Resolve each link
            for link in links:
                try:
                    resolved_path = self._resolve_single_link(link, page_lookup, section_lookup)
                    
                    if resolved_path:
                        link.resolved_path = resolved_path
                        link.resolution_status = "resolved"
                        result.resolved_links.append(link)
                        self.stats['resolved_links'] += 1
                    else:
                        link.resolution_status = "failed"
                        result.failed_links.append(link)
                        self.stats['failed_links'] += 1
                        
                except Exception as e:
                    error_msg = f"Failed to resolve link {link.original_url}: {e}"
                    logger.warning(error_msg)
                    link.resolution_status = "error"
                    link.error_message = str(e)
                    result.failed_links.append(link)
                    self.stats['failed_links'] += 1

            # Set final statistics
            result.resolved_count = self.stats['resolved_links']
            result.failed_count = self.stats['failed_links']
            result.success = result.resolved_count > 0 or result.total_links == 0

            logger.info(f"Link resolution completed: {result.resolved_count}/{result.total_links} resolved")

        except Exception as e:
            result.success = False
            result.error = str(e)
            logger.error(f"Link resolution batch failed: {e}")

        return result

    def _resolve_single_link(self, link: LinkInfo, page_lookup: Dict[str, OneNotePage],
                           section_lookup: Dict[str, OneNoteSection]) -> Optional[str]:
        """
        Resolve a single link to a local path.

        Args:
            link: Link to resolve
            page_lookup: Dictionary of pages by ID
            section_lookup: Dictionary of sections by ID

        Returns:
            Resolved local path or None if not resolvable
        """
        url = link.original_url
        
        # Check cache first
        if url in self.resolution_cache:
            self.stats['cached_lookups'] += 1
            return self.resolution_cache[url]

        resolved_path = None

        try:
            # Parse the URL to extract components
            parsed = urlparse(url)
            
            # Extract IDs from different URL formats
            page_id = self._extract_page_id(url)
            section_id = self._extract_section_id(url)
            
            # Try to resolve to page first
            if page_id and page_id in page_lookup:
                page = page_lookup[page_id]
                resolved_path = self._get_relative_path_to_page(page)
                logger.debug(f"Resolved page link: {url} -> {resolved_path}")
            
            # Try to resolve to section if page resolution failed
            elif section_id and section_id in section_lookup:
                section = section_lookup[section_id]
                resolved_path = self._get_relative_path_to_section(section)
                logger.debug(f"Resolved section link: {url} -> {resolved_path}")
            
            # Try alternative resolution methods
            else:
                resolved_path = self._try_alternative_resolution(url, page_lookup, section_lookup)

            # Update link type based on resolution
            if resolved_path:
                if resolved_path.endswith('.md'):
                    link.link_type = "page"
                else:
                    link.link_type = "section"

        except Exception as e:
            logger.warning(f"Exception during link resolution: {e}")

        # Cache the result (even if None)
        self.resolution_cache[url] = resolved_path
        return resolved_path

    def _extract_page_id(self, url: str) -> Optional[str]:
        """
        Extract page ID from OneNote URL.

        Args:
            url: OneNote URL

        Returns:
            Page ID if found, None otherwise
        """
        try:
            # Look for page-id parameter
            match = re.search(r'page-id=([a-zA-Z0-9-]+)', url)
            if match:
                return match.group(1)
            
            # Look for pageId parameter
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'pageId' in params:
                return params['pageId'][0]
            
            # Look for page ID in fragment
            if parsed.fragment:
                match = re.search(r'pageId=([a-zA-Z0-9-]+)', parsed.fragment)
                if match:
                    return match.group(1)
            
            # Try to extract from path (for some OneNote formats)
            path_parts = parsed.path.split('/')
            for part in path_parts:
                if len(part) > 20 and all(c.isalnum() or c == '-' for c in part):
                    return part

        except Exception as e:
            logger.debug(f"Failed to extract page ID from {url}: {e}")

        return None

    def _extract_section_id(self, url: str) -> Optional[str]:
        """
        Extract section ID from OneNote URL.

        Args:
            url: OneNote URL

        Returns:
            Section ID if found, None otherwise
        """
        try:
            # Look for section-id parameter
            match = re.search(r'section-id=([a-zA-Z0-9-]+)', url)
            if match:
                return match.group(1)
            
            # Look for sectionId parameter
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'sectionId' in params:
                return params['sectionId'][0]
            
            # Look for section ID in fragment
            if parsed.fragment:
                match = re.search(r'sectionId=([a-zA-Z0-9-]+)', parsed.fragment)
                if match:
                    return match.group(1)

        except Exception as e:
            logger.debug(f"Failed to extract section ID from {url}: {e}")

        return None

    def _try_alternative_resolution(self, url: str, page_lookup: Dict[str, OneNotePage],
                                  section_lookup: Dict[str, OneNoteSection]) -> Optional[str]:
        """
        Try alternative methods to resolve a link.

        Args:
            url: URL to resolve
            page_lookup: Dictionary of pages by ID
            section_lookup: Dictionary of sections by ID

        Returns:
            Resolved path or None
        """
        try:
            # Try to match by URL patterns
            for page in page_lookup.values():
                if self._urls_match(url, page.web_url):
                    return self._get_relative_path_to_page(page)
            
            for section in section_lookup.values():
                if self._urls_match(url, section.web_url):
                    return self._get_relative_path_to_section(section)
            
            # Try to match by title (for anchor-style links)
            anchor_title = self._extract_anchor_title(url)
            if anchor_title:
                for page in page_lookup.values():
                    if self._titles_match(anchor_title, page.title):
                        return self._get_relative_path_to_page(page)

        except Exception as e:
            logger.debug(f"Alternative resolution failed for {url}: {e}")

        return None

    def _urls_match(self, url1: str, url2: str) -> bool:
        """Check if two URLs are similar enough to be considered matching."""
        try:
            parsed1 = urlparse(url1)
            parsed2 = urlparse(url2)
            
            # Compare domains
            if parsed1.netloc != parsed2.netloc:
                return False
            
            # Compare paths (ignoring parameters)
            path1 = parsed1.path.rstrip('/')
            path2 = parsed2.path.rstrip('/')
            
            return path1 == path2
            
        except Exception:
            return False

    def _extract_anchor_title(self, url: str) -> Optional[str]:
        """Extract title from anchor-style links."""
        try:
            parsed = urlparse(url)
            if parsed.fragment:
                # Decode URL encoding
                title = unquote(parsed.fragment)
                # Clean up common OneNote anchor formats
                title = re.sub(r'^(section|page)[-_]', '', title, flags=re.IGNORECASE)
                title = title.replace('-', ' ').replace('_', ' ')
                return title.strip()
        except Exception:
            pass
        return None

    def _titles_match(self, title1: str, title2: str) -> bool:
        """Check if two titles match (case-insensitive, normalized)."""
        try:
            norm1 = re.sub(r'[^\w\s]', '', title1.lower()).strip()
            norm2 = re.sub(r'[^\w\s]', '', title2.lower()).strip()
            return norm1 == norm2
        except Exception:
            return False

    def _build_page_lookup(self, pages: List[OneNotePage]) -> Dict[str, OneNotePage]:
        """Build a lookup dictionary for pages by ID."""
        lookup = {}
        for page in pages:
            if page.id:
                lookup[page.id] = page
            # Also add alternative ID formats if available
            if hasattr(page, 'onenote_id') and page.onenote_id:
                lookup[page.onenote_id] = page
        return lookup

    def _build_section_lookup(self, sections: List[OneNoteSection]) -> Dict[str, OneNoteSection]:
        """Build a lookup dictionary for sections by ID."""
        lookup = {}
        for section in sections:
            if section.id:
                lookup[section.id] = section
            # Also add alternative ID formats if available
            if hasattr(section, 'onenote_id') and section.onenote_id:
                lookup[section.onenote_id] = section
        return lookup

    def _get_relative_path_to_page(self, page: OneNotePage) -> str:
        """
        Get relative path from current location to a page.

        Args:
            page: Page to link to

        Returns:
            Relative path to the page markdown file
        """
        try:
            # Get the absolute path to the page's markdown file
            page_path = get_content_path_for_page(
                self.cache_root, page.notebook_name, page.section_name, page.title
            )
            
            # For now, return relative path assuming we're linking from within content
            # This would need to be adjusted based on the actual linking context
            content_root = self.cache_root / "content"
            
            try:
                rel_path = page_path.relative_to(content_root)
                return str(rel_path).replace('\\', '/')  # Use forward slashes for markdown links
            except ValueError:
                # If relative path fails, use absolute path
                return str(page_path).replace('\\', '/')

        except Exception as e:
            logger.warning(f"Failed to create relative path for page {page.title}: {e}")
            # Fallback: create simple relative path
            return f"./{sanitize_filename(page.title)}.md"

    def _get_relative_path_to_section(self, section: OneNoteSection) -> str:
        """
        Get relative path from current location to a section.

        Args:
            section: Section to link to

        Returns:
            Relative path to the section directory
        """
        try:
            # Get the absolute path to the section directory
            section_path = get_content_path_for_section(
                self.cache_root, section.notebook_name, section.name
            )
            
            # Return relative path
            content_root = self.cache_root / "content"
            
            try:
                rel_path = section_path.relative_to(content_root)
                return str(rel_path).replace('\\', '/')
            except ValueError:
                return str(section_path).replace('\\', '/')

        except Exception as e:
            logger.warning(f"Failed to create relative path for section {section.name}: {e}")
            # Fallback: create simple relative path
            return f"./{sanitize_filename(section.name)}/"

    def is_internal_onenote_link(self, url: str) -> bool:
        """
        Check if a URL is an internal OneNote link.

        Args:
            url: URL to check

        Returns:
            True if this appears to be an internal OneNote link
        """
        try:
            # Check against known OneNote patterns
            for pattern in self.onenote_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return True
            
            # Check for OneNote domains
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            onenote_domains = [
                'onenote.com',
                'sharepoint.com',
                'office.com',
                'live.com'
            ]
            
            for onenote_domain in onenote_domains:
                if onenote_domain in domain:
                    return True
            
            # Check for OneNote-specific URL schemes
            if url.startswith('onenote:'):
                return True
            
            return False

        except Exception as e:
            logger.debug(f"Error checking if URL is internal OneNote link: {e}")
            return False

    def extract_links_from_html(self, html_content: str) -> List[LinkInfo]:
        """
        Extract internal OneNote links from HTML content.

        Args:
            html_content: HTML content to scan

        Returns:
            List of internal links found
        """
        links = []
        
        try:
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for anchor in soup.find_all('a', href=True):
                href = anchor.get('href')
                text = anchor.get_text().strip()
                
                if self.is_internal_onenote_link(href):
                    link = LinkInfo(
                        original_url=href,
                        resolved_path="",
                        link_text=text,
                        link_type="unknown",
                        resolution_status="pending"
                    )
                    links.append(link)

            logger.debug(f"Extracted {len(links)} internal links from HTML content")

        except Exception as e:
            logger.error(f"Failed to extract links from HTML: {e}")

        return links

    def get_resolution_stats(self) -> Dict[str, any]:
        """
        Get current resolution statistics.

        Returns:
            Dictionary with resolution statistics
        """
        return self.stats.copy()

    def clear_resolution_cache(self) -> None:
        """Clear the link resolution cache."""
        self.resolution_cache.clear()
        logger.debug("Link resolution cache cleared")

    def update_link_in_markdown(self, markdown_content: str, 
                               old_link: str, new_link: str) -> str:
        """
        Update a link reference in markdown content.

        Args:
            markdown_content: Markdown content to update
            old_link: Old link URL or path
            new_link: New link URL or path

        Returns:
            Updated markdown content
        """
        try:
            # Update markdown link format [text](url)
            pattern = r'\[([^\]]*)\]\(' + re.escape(old_link) + r'\)'
            replacement = r'[\1](' + new_link + ')'
            updated_content = re.sub(pattern, replacement, markdown_content)
            
            # Update reference-style links if any
            ref_pattern = r'^\[([^\]]+)\]:\s*' + re.escape(old_link) + r'.*$'
            ref_replacement = f'[\\1]: {new_link}'
            updated_content = re.sub(ref_pattern, ref_replacement, updated_content, flags=re.MULTILINE)
            
            return updated_content

        except Exception as e:
            logger.error(f"Failed to update link in markdown: {e}")
            return markdown_content

    def validate_resolved_links(self, links: List[LinkInfo]) -> Tuple[List[LinkInfo], List[LinkInfo]]:
        """
        Validate that resolved links point to existing files.

        Args:
            links: List of links to validate

        Returns:
            Tuple of (valid_links, invalid_links)
        """
        valid_links = []
        invalid_links = []
        
        for link in links:
            if not link.resolved_path:
                invalid_links.append(link)
                continue
            
            try:
                # Check if resolved path exists
                resolved_file = self.cache_root / "content" / link.resolved_path
                
                if resolved_file.exists():
                    valid_links.append(link)
                else:
                    link.resolution_status = "invalid"
                    link.error_message = f"Resolved path does not exist: {resolved_file}"
                    invalid_links.append(link)
                    
            except Exception as e:
                link.resolution_status = "error"
                link.error_message = f"Validation error: {e}"
                invalid_links.append(link)

        logger.info(f"Link validation: {len(valid_links)} valid, {len(invalid_links)} invalid")
        return valid_links, invalid_links


# Utility functions

def normalize_onenote_url(url: str) -> str:
    """
    Normalize OneNote URL for consistent comparison.

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    try:
        # Remove common variations and normalize
        normalized = url.lower().strip()
        
        # Remove trailing slashes
        normalized = normalized.rstrip('/')
        
        # Normalize parameter order (basic approach)
        parsed = urlparse(normalized)
        if parsed.query:
            params = parse_qs(parsed.query)
            sorted_params = sorted(params.items())
            from urllib.parse import urlencode
            normalized_query = urlencode(sorted_params, doseq=True)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{normalized_query}"
            if parsed.fragment:
                normalized += f"#{parsed.fragment}"
        
        return normalized

    except Exception:
        return url


def create_markdown_link(text: str, url: str) -> str:
    """
    Create a markdown link with proper escaping.

    Args:
        text: Link text
        url: Link URL

    Returns:
        Formatted markdown link
    """
    # Escape special characters in text
    safe_text = text.replace('[', '\\[').replace(']', '\\]')
    
    # Escape parentheses in URL
    safe_url = url.replace('(', '%28').replace(')', '%29')
    
    return f"[{safe_text}]({safe_url})"


def is_absolute_path(path: str) -> bool:
    """Check if a path is absolute."""
    try:
        return Path(path).is_absolute()
    except Exception:
        return False
