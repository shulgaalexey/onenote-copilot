"""
OneNote search tool using Microsoft Graph API.

Provides search functionality for OneNote content with HTML parsing,
rate limiting, and comprehensive error handling.
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..auth.microsoft_auth import AuthenticationError, MicrosoftAuthenticator
from ..config.logging import log_api_call, log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import OneNotePage, SearchResult

logger = logging.getLogger(__name__)


class OneNoteSearchError(Exception):
    """Exception raised when OneNote search operations fail."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict[str, Any]] = None):
        """
        Initialize OneNoteSearchError with optional context.

        Args:
            message: Error message
            status_code: Optional HTTP status code
            response_data: Optional response data from API
        """
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

    def __repr__(self) -> str:
        """Return detailed string representation of error."""
        parts = [f"OneNoteSearchError('{self.args[0]}'"]
        if self.status_code:
            parts.append(f"status_code={self.status_code}")
        if self.response_data:
            parts.append(f"response_data={self.response_data}")
        return ", ".join(parts) + ")"


class OneNoteSearchTool:
    """
    OneNote search tool using Microsoft Graph API.

    Provides comprehensive search functionality with rate limiting,
    error handling, and content extraction.
    """

    def __init__(self, authenticator: Optional[MicrosoftAuthenticator] = None, settings: Optional[Any] = None):
        """
        Initialize the OneNote search tool.

        Args:
            authenticator: Optional Microsoft authenticator instance
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()
        self.authenticator = authenticator or MicrosoftAuthenticator(self.settings)

        # API configuration
        self.base_url = self.settings.graph_api_base_url
        self.timeout = self.settings.request_timeout
        self.max_results = self.settings.max_search_results

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_count = 0
        self._rate_limit_window_start = time.time()

    def _prepare_search_query(self, natural_query: str) -> str:
        """
        Prepare a natural language query for OneNote search API.

        The Microsoft Graph OneNote search API expects specific query formats.
        This method extracts keywords and formats them appropriately.

        Args:
            natural_query: Natural language query from user

        Returns:
            Formatted query string for API
        """
        if not natural_query or not natural_query.strip():
            return ""

        # Remove common question words and patterns
        query = natural_query.strip()

        # Remove question marks and other problematic punctuation
        query = re.sub(r'[?!]', '', query)

        # For thought-related queries, extract the subject after "about", "on", etc.
        thought_patterns = [
            r'thoughts?\s+about\s+(.+)',
            r'thoughts?\s+on\s+(.+)',
            r'think\s+about\s+(.+)',
            r'opinion\s+about\s+(.+)',
            r'ideas?\s+about\s+(.+)'
        ]

        for pattern in thought_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                subject = match.group(1).strip()
                # Remove articles and common words at the beginning for better matching
                subject = re.sub(r'^(the|a|an)\s+', '', subject, flags=re.IGNORECASE)
                logger.debug(f"Extracted subject from thought query: '{subject}'")
                return subject

        # Remove only very specific question words at the beginning - be more conservative
        question_patterns = [
            r'^show\s+me\s+',
            r'^find\s+me\s+',
            r'^find\s+',
            r'^search\s+for\s+',
            r'^look\s+for\s+'
        ]

        for pattern in question_patterns:
            query = re.sub(pattern, '', query, flags=re.IGNORECASE)

        # Only remove filler words if they're not part of the main content
        # Be more selective about word removal to preserve semantic meaning
        if query.startswith('about '):
            query = query[6:]  # Remove 'about ' from start only

        # Remove 'about' from middle of queries for better matching
        query = re.sub(r'\s+about\s+', ' ', query, flags=re.IGNORECASE)

        # Clean up extra whitespace
        query = re.sub(r'\s+', ' ', query).strip()

        # If query is too short after processing, use original minus punctuation
        if len(query) < 3:
            query = re.sub(r'[?!]', '', natural_query.strip())

        logger.debug(f"Processed query: '{natural_query}' -> '{query}'")
        return query

    async def search_pages(self, query: str, max_results: Optional[int] = None) -> SearchResult:
        """
        Search OneNote pages using the Microsoft Graph API (fallback method).

        NOTE: This is now primarily a fallback method. Local search should be used as the primary search method
        for better performance and capabilities.

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            SearchResult containing matching pages

        Raises:
            OneNoteSearchError: If search operation fails
        """
        start_time = time.time()
        api_calls = 0

        try:
            # Validate and prepare query
            if not query or not query.strip():
                raise OneNoteSearchError("Search query cannot be empty")

            # Process natural language query for API
            original_query = query.strip()
            processed_query = self._prepare_search_query(original_query)

            if not processed_query:
                raise OneNoteSearchError("Unable to extract searchable terms from query")

            max_results = max_results or self.max_results

            logger.debug(f"API search (fallback) for: '{original_query}' (processed: '{processed_query}')")

            # Get authentication token
            token = await self.authenticator.get_valid_token()

            # Simple API search - try title search first, then fallback to section-based if needed
            pages_data, api_calls = await self._search_pages_api(processed_query, token, max_results)

            # If no results, try section-based search as fallback
            if len(pages_data) == 0:
                logger.debug("No results from direct API search, trying section-based fallback")
                pages_data, fallback_api_calls = await self._search_pages_by_sections(processed_query, token, max_results)
                api_calls += fallback_api_calls

            # Convert to OneNotePage models
            pages = []
            for page_data in pages_data:
                try:
                    page = OneNotePage(**page_data)
                    pages.append(page)
                except Exception as e:
                    logger.warning(f"Failed to parse page data: {e}")
                    continue

            # Fetch content for top results (reduced from 5 to 3 for efficiency)
            if pages:
                content_api_calls = await self._fetch_page_contents(pages[:3], token)
                api_calls += content_api_calls

            execution_time = time.time() - start_time

            result = SearchResult(
                pages=pages,
                query=original_query,
                total_count=len(pages),
                execution_time=execution_time,
                api_calls_made=api_calls,
                search_metadata={
                    "search_endpoint": "/me/onenote/pages",
                    "search_method": "api_fallback",
                    "original_query": original_query,
                    "processed_query": processed_query,
                    "content_fetched": min(3, len(pages))
                }
            )

            logger.info(f"API fallback search completed: {len(pages)} pages found in {execution_time:.2f}s")
            return result

        except AuthenticationError:
            raise OneNoteSearchError("Authentication failed - please log in again")
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise OneNoteSearchError(f"Search operation failed: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _search_pages_api(self, query: str, token: str, max_results: int) -> tuple[List[Dict[str, Any]], int]:
        """
        Make API call to search OneNote pages.

        Args:
            query: Search query
            token: Authentication token
            max_results: Maximum results to return

        Returns:
            Tuple of (pages data, api calls made)
        """
        await self._enforce_rate_limit()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Build search parameters using $filter instead of $search
        # OneNote API doesn't support $search parameter, so we use title filtering
        # Escape single quotes to prevent injection
        escaped_query = query.replace("'", "''")
        filter_query = f"contains(tolower(title), '{escaped_query.lower()}')"

        params = {
            "$filter": filter_query,
            "$top": min(max_results, 50),  # API limit is 50 per request
            "$select": "id,title,createdDateTime,lastModifiedDateTime,contentUrl,parentSection,parentNotebook",
            "$expand": "parentSection,parentNotebook",
            "$orderby": "lastModifiedDateTime desc"
        }

        endpoint = f"{self.base_url}/me/onenote/pages"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    pages = data.get("value", [])
                    logger.debug(f"API returned {len(pages)} pages")
                    return pages, 1
                elif response.status_code == 401:
                    raise AuthenticationError("Token expired or invalid")
                elif response.status_code == 403:
                    raise OneNoteSearchError("Access denied - check OneNote permissions")
                elif response.status_code == 400:
                    # Handle "too many sections" error - fallback to section-by-section search
                    logger.warning(f"Search pages endpoint returned 400, falling back to section-based search for query: {query}")
                    return await self._search_pages_by_sections(query, token, max_results)
                elif response.status_code == 429:
                    # Rate limit exceeded
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit exceeded, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    raise OneNoteSearchError("Rate limit exceeded")
                else:
                    error_msg = f"API request failed with status {response.status_code}"
                    logger.error(f"{error_msg}: {response.text}")
                    raise OneNoteSearchError(error_msg)

        except httpx.TimeoutException:
            raise OneNoteSearchError("Search request timed out")
        except Exception as e:
            logger.error(f"API request failed: {e}")
            raise OneNoteSearchError(f"API request failed: {e}")

    async def _fetch_page_contents(self, pages: List[OneNotePage], token: str) -> int:
        """
        Fetch content for a list of pages.

        Args:
            pages: List of pages to fetch content for
            token: Authentication token

        Returns:
            Number of API calls made
        """
        if not pages:
            return 0

        logger.debug(f"Fetching content for {len(pages)} pages")
        api_calls = 0

        # Fetch content in parallel (with limited concurrency)
        semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent requests

        async def fetch_single_content(page: OneNotePage) -> None:
            nonlocal api_calls
            async with semaphore:
                try:
                    content, calls = await self._fetch_page_content(page.id, token)
                    if content:
                        page.content = content
                        page.text_content = self._extract_text_from_html(content)
                        page.processed_content = page.text_content  # Use processed text for chunking
                    api_calls += calls
                except Exception as e:
                    logger.warning(f"Failed to fetch content for page {page.id}: {e}")

        # Execute all content fetches
        await asyncio.gather(*[fetch_single_content(page) for page in pages], return_exceptions=True)

        return api_calls

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5)
    )
    async def _fetch_page_content(self, page_id: str, token: str) -> tuple[Optional[str], int]:
        """
        Fetch content for a specific page.

        Args:
            page_id: OneNote page ID
            token: Authentication token

        Returns:
            Tuple of (page content HTML, api calls made)
        """
        await self._enforce_rate_limit()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/xhtml+xml"
        }

        endpoint = f"{self.base_url}/me/onenote/pages/{page_id}/content"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=headers)

                if response.status_code == 200:
                    return response.text, 1
                elif response.status_code == 401:
                    raise AuthenticationError("Token expired or invalid")
                elif response.status_code == 404:
                    logger.warning(f"Page {page_id} not found")
                    return None, 1
                elif response.status_code == 429:
                    # Rate limit exceeded - wait and retry
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit exceeded fetching page {page_id}, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    # Retry the request
                    return await self._fetch_page_content(page_id, token)
                else:
                    logger.warning(f"Failed to fetch content for page {page_id}: {response.status_code}")
                    return None, 1

        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching content for page {page_id}")
            return None, 1
        except Exception as e:
            logger.warning(f"Error fetching content for page {page_id}: {e}")
            return None, 1

    def _extract_text_from_html(self, html_content: str) -> str:
        """
        Extract text content from OneNote HTML.

        Args:
            html_content: HTML content from OneNote API

        Returns:
            Extracted text content
        """
        if not html_content:
            return ""

        try:
            # Try to use BeautifulSoup for proper HTML parsing
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text content
                text = soup.get_text()

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)

                return text

            except ImportError:
                # Fallback to simple regex-based extraction

                # Remove script and style elements
                text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

                # Remove HTML tags
                text = re.sub(r'<[^>]+>', '', text)

                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text)
                text = text.strip()

                return text

        except Exception as e:
            logger.warning(f"Failed to extract text from HTML: {e}")
            return ""

    async def _enforce_rate_limit(self) -> None:
        """
        Simple rate limiting to respect Microsoft Graph API limits.

        Note: With local cache as primary search, API usage should be minimal.
        This is a simplified version for the remaining API fallback calls.
        """
        current_time = time.time()

        # Simple delay between API calls - increased for bulk operations
        time_since_last = current_time - self._last_request_time
        min_delay = 0.5  # 500ms delay between API calls to avoid rate limits

        if time_since_last < min_delay:
            await asyncio.sleep(min_delay - time_since_last)

        self._request_count += 1
        self._last_request_time = time.time()

    async def get_recent_pages(self, limit: int = 10) -> List[OneNotePage]:
        """
        Get recently modified OneNote pages with content.

        Args:
            limit: Maximum number of pages to return

        Returns:
            List of recently modified pages with content loaded

        Raises:
            OneNoteSearchError: If operation fails
        """
        try:
            token = await self.authenticator.get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            params = {
                "$top": min(limit, 50),
                "$select": "id,title,createdDateTime,lastModifiedDateTime,contentUrl,parentSection,parentNotebook",
                "$expand": "parentSection,parentNotebook",
                "$orderby": "lastModifiedDateTime desc"
            }

            endpoint = f"{self.base_url}/me/onenote/pages"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    pages_data = data.get("value", [])

                    pages = []
                    for page_data in pages_data:
                        try:
                            page = OneNotePage(**page_data)
                            pages.append(page)
                        except Exception as e:
                            logger.warning(f"Failed to parse page data: {e}")
                            continue

                    # Fetch content for all pages
                    if pages:
                        logger.debug(f"Fetching content for {len(pages)} recent pages")
                        await self._fetch_page_contents(pages, token)

                    return pages
                elif response.status_code == 400:
                    # Fallback for tenants with too many sections: use section-by-section retrieval
                    logger.warning(f"Recent pages endpoint returned 400, falling back to section-based retrieval")
                    # Use optimized fallback that respects the original limit
                    return await self._get_recent_pages_fallback(limit)
                else:
                    raise OneNoteSearchError(f"Failed to get recent pages: {response.status_code}")

        except AuthenticationError:
            raise OneNoteSearchError("Authentication failed - please log in again")
        except Exception as e:
            logger.error(f"Failed to get recent pages: {e}")
            raise OneNoteSearchError(f"Failed to get recent pages: {e}")

    async def _get_recent_pages_fallback(self, limit: int = 10) -> List[OneNotePage]:
        """
        Optimized fallback for getting recent pages when main endpoint fails.

        This method uses section-by-section retrieval but with several optimizations:
        1. Fetches only metadata initially (no content)
        2. Limits total pages processed to avoid rate limiting
        3. Only fetches content for the final limited set

        Args:
            limit: Maximum number of recent pages to return

        Returns:
            List of recent pages with content loaded
        """
        try:
            logger.info(f"Using optimized recent pages fallback for {limit} pages")

            token = await self.authenticator.get_valid_token()

            # Get all sections first
            sections = await self._get_all_sections(token)
            logger.debug(f"Found {len(sections)} sections for recent pages fallback")

            if not sections:
                return []

            all_pages = []
            pages_processed = 0
            # Process sections but limit total pages to avoid rate limits
            max_pages_to_process = min(50, limit * 3)  # Process up to 3x the requested limit

            for i, section in enumerate(sections):
                section_id = section.get("id")
                section_name = section.get("displayName", "Unknown")

                try:
                    logger.debug(f"Getting pages from section: {section_name} ({i+1}/{len(sections)})")

                    # Get pages metadata only (no content yet)
                    section_pages = await self._get_pages_from_section(
                        section_id, token, max_pages_to_process - pages_processed
                    )

                    if section_pages:
                        all_pages.extend(section_pages)
                        pages_processed += len(section_pages)
                        logger.debug(f"Retrieved {len(section_pages)} pages from section '{section_name}'")

                    # Stop if we have enough pages to choose from
                    if pages_processed >= max_pages_to_process:
                        logger.debug(f"Reached processing limit of {max_pages_to_process} pages")
                        break

                    # Small delay between sections to respect API limits
                    await asyncio.sleep(0.1)  # Reduced delay for fallback

                except Exception as e:
                    logger.warning(f"Failed to get pages from section '{section_name}': {e}")
                    continue

            # Sort by last modified date (newest first) and limit
            all_pages.sort(key=lambda p: p.last_modified_date_time, reverse=True)
            recent_pages = all_pages[:limit]

            logger.info(f"Selected {len(recent_pages)} most recent pages from {len(all_pages)} total pages")

            # Now fetch content only for the limited set
            if recent_pages:
                logger.debug(f"Fetching content for {len(recent_pages)} selected recent pages")
                await self._fetch_page_contents(recent_pages, token)

            return recent_pages

        except Exception as e:
            logger.error(f"Recent pages fallback failed: {e}")
            # Return empty list rather than failing completely
            return []

    async def get_all_pages(self, limit: Optional[int] = None) -> List[OneNotePage]:
        """
        Get all OneNote pages from all notebooks using section-by-section approach.

        This method handles cases where accounts have many sections by fetching
        sections first, then getting pages for each section individually.

        Args:
            limit: Optional maximum number of pages to return

        Returns:
            List of all pages from all notebooks with content loaded

        Raises:
            OneNoteSearchError: If operation fails
        """
        try:
            token = await self.authenticator.get_valid_token()

            # First, get all sections from all notebooks
            logger.info("Getting all sections from notebooks...")
            sections = await self._get_all_sections(token)
            logger.info(f"Found {len(sections)} sections across all notebooks")

            if not sections:
                logger.warning("No sections found in any notebooks")
                return []

            all_pages = []
            pages_fetched = 0

            # Get pages from each section
            for i, section in enumerate(sections):
                section_id = section.get("id")
                section_name = section.get("displayName", "Unknown")

                try:
                    logger.debug(f"Getting pages from section: {section_name} ({i+1}/{len(sections)})")

                    # Get pages for this specific section
                    section_pages = await self._get_pages_from_section(section_id, token, limit)

                    if section_pages:
                        all_pages.extend(section_pages)
                        pages_fetched += len(section_pages)
                        logger.debug(f"Retrieved {len(section_pages)} pages from section '{section_name}'")

                    # Stop if we've reached the limit
                    if limit and pages_fetched >= limit:
                        all_pages = all_pages[:limit]  # Trim to exact limit
                        break

                    # Small delay between sections to respect API limits
                    await asyncio.sleep(0.2)

                except Exception as e:
                    logger.warning(f"Failed to get pages from section '{section_name}': {e}")
                    continue

            logger.info(f"Retrieved {len(all_pages)} pages from {len(sections)} sections")

            # Sort by last modified date (newest first)
            all_pages.sort(key=lambda p: p.last_modified_date_time, reverse=True)

            # Fetch content for pages in batches to avoid overwhelming the API
            if all_pages:
                logger.info(f"Fetching content for {len(all_pages)} pages...")

                # Process in smaller batches to manage memory and API limits
                batch_size = 10
                for i in range(0, len(all_pages), batch_size):
                    batch = all_pages[i:i + batch_size]
                    await self._fetch_page_contents(batch, token)

                    # Progress logging for large operations
                    if len(all_pages) > 20:
                        progress = min(i + batch_size, len(all_pages))
                        logger.info(f"Content fetched for {progress}/{len(all_pages)} pages")

                    # Small delay between batches to respect API limits
                    if i + batch_size < len(all_pages):
                        await asyncio.sleep(0.5)

            return all_pages

        except AuthenticationError:
            raise OneNoteSearchError("Authentication failed - please log in again")
        except Exception as e:
            logger.error(f"Failed to get all pages: {e}")
            raise OneNoteSearchError(f"Failed to get all pages: {e}")

    async def _get_all_sections(self, token: str) -> List[Dict[str, Any]]:
        """
        Get all sections from all notebooks.

        Args:
            token: Authentication token

        Returns:
            List of section information from all notebooks

        Raises:
            OneNoteSearchError: If operation fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            params = {
                "$select": "id,displayName,parentNotebook",
                "$expand": "parentNotebook"
            }

            endpoint = f"{self.base_url}/me/onenote/sections"
            all_sections = []
            next_url = None

            # Handle pagination
            while True:
                await self._enforce_rate_limit()  # Add rate limiting
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if next_url:
                        response = await client.get(next_url, headers=headers)
                    else:
                        response = await client.get(endpoint, headers=headers, params=params)

                    if response.status_code == 200:
                        data = response.json()
                        sections_data = data.get("value", [])
                        all_sections.extend(sections_data)

                        # Check for more sections (pagination)
                        next_url = data.get("@odata.nextLink")
                        if not next_url:
                            break
                    elif response.status_code == 429:
                        # Rate limit exceeded - wait and retry
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limit exceeded getting sections, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        # Don't increment next_url, retry the same request
                        continue
                    else:
                        logger.error(f"Failed to get sections: HTTP {response.status_code}")
                        raise OneNoteSearchError(f"Failed to get sections: {response.status_code}")

            return all_sections

        except Exception as e:
            logger.error(f"Failed to get all sections: {e}")
            raise OneNoteSearchError(f"Failed to get all sections: {e}")

    async def _get_pages_from_section(self, section_id: str, token: str, remaining_limit: Optional[int] = None) -> List[OneNotePage]:
        """
        Get all pages from a specific section.

        Args:
            section_id: Section ID to get pages from
            token: Authentication token
            remaining_limit: Optional remaining limit for total pages

        Returns:
            List of OneNotePage objects from the section

        Raises:
            OneNoteSearchError: If operation fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            params = {
                "$select": "id,title,createdDateTime,lastModifiedDateTime,contentUrl,parentSection,parentNotebook",
                "$expand": "parentSection,parentNotebook",
                "$orderby": "lastModifiedDateTime desc"
            }

            # Add limit if specified
            if remaining_limit:
                params["$top"] = min(remaining_limit, 50)  # API limit per request

            endpoint = f"{self.base_url}/me/onenote/sections/{section_id}/pages"
            section_pages = []
            next_url = None

            # Handle pagination within the section
            while True:
                await self._enforce_rate_limit()  # Add rate limiting
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if next_url:
                        response = await client.get(next_url, headers=headers)
                    else:
                        response = await client.get(endpoint, headers=headers, params=params)

                    if response.status_code == 200:
                        data = response.json()
                        pages_data = data.get("value", [])

                        # Convert to OneNotePage models
                        for page_data in pages_data:
                            try:
                                page = OneNotePage(**page_data)
                                section_pages.append(page)

                                # Stop if we've reached the limit
                                if remaining_limit and len(section_pages) >= remaining_limit:
                                    break
                            except Exception as e:
                                logger.warning(f"Failed to parse page data: {e}")
                                continue

                        # Check for more pages in this section
                        next_url = data.get("@odata.nextLink")
                        if not next_url or (remaining_limit and len(section_pages) >= remaining_limit):
                            break
                    elif response.status_code == 429:
                        # Rate limit exceeded - wait and retry
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limit exceeded getting pages from section {section_id}, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        # Don't increment next_url, retry the same request
                        continue
                    else:
                        logger.warning(f"Failed to get pages from section {section_id}: HTTP {response.status_code}")
                        break  # Continue with next section instead of failing completely

            return section_pages

        except Exception as e:
            logger.warning(f"Failed to get pages from section {section_id}: {e}")
            return []  # Return empty list to continue with other sections

    async def get_notebooks(self) -> List[Dict[str, Any]]:
        """
        Get list of OneNote notebooks.

        Returns:
            List of notebook information

        Raises:
            OneNoteSearchError: If operation fails
        """
        try:
            token = await self.authenticator.get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            params = {
                "$select": "id,displayName,createdDateTime,lastModifiedDateTime,isDefault"
            }

            endpoint = f"{self.base_url}/me/onenote/notebooks"

            await self._enforce_rate_limit()  # Add rate limiting
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    return data.get("value", [])
                elif response.status_code == 429:
                    # Rate limit exceeded - wait and retry once
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit exceeded getting notebooks, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)

                    # Retry once
                    response = await client.get(endpoint, headers=headers, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        return data.get("value", [])
                    else:
                        raise OneNoteSearchError(f"Failed to get notebooks after retry: {response.status_code}")
                else:
                    raise OneNoteSearchError(f"Failed to get notebooks: {response.status_code}")

        except AuthenticationError:
            raise OneNoteSearchError("Authentication failed - please log in again")
        except Exception as e:
            logger.error(f"Failed to get notebooks: {e}")
            raise OneNoteSearchError(f"Failed to get notebooks: {e}")

    @logged
    async def get_page_content_by_title(self, title: str) -> Optional[OneNotePage]:
        """
        Get full content of a OneNote page by its title.

        Args:
            title: Title of the page to retrieve

        Returns:
            OneNotePage with full content if found, None otherwise

        Raises:
            OneNoteSearchError: If operation fails
        """
        try:
            # First, search for pages with matching title
            result = await self.search_pages(title, max_results=20)

            if not result.pages:
                logger.info(f"No pages found with title containing: {title}")
                return None

            # Find exact title match (case-insensitive)
            title_lower = title.lower().strip()
            exact_matches = [
                page for page in result.pages
                if page.title.lower().strip() == title_lower
            ]

            # If no exact match, find best partial match
            if not exact_matches:
                partial_matches = [
                    page for page in result.pages
                    if title_lower in page.title.lower()
                ]

                if not partial_matches:
                    logger.info(f"No pages found matching title: {title}")
                    return None

                # Use the first partial match
                target_page = partial_matches[0]
                logger.info(f"Using partial match: '{target_page.title}' for query: '{title}'")
            else:
                # Use exact match
                target_page = exact_matches[0]
                logger.info(f"Found exact match: '{target_page.title}'")

            # Fetch full content if not already loaded
            if not target_page.content or not target_page.text_content:
                token = await self.authenticator.get_valid_token()
                content, _ = await self._fetch_page_content(target_page.id, token)

                if content:
                    target_page.content = content
                    target_page.text_content = self._extract_text_from_html(content)
                    logger.info(f"Successfully fetched content for page: {target_page.title}")
                else:
                    logger.warning(f"Failed to fetch content for page: {target_page.title}")

            return target_page

        except Exception as e:
            logger.error(f"Failed to get page content by title '{title}': {e}")
            raise OneNoteSearchError(f"Failed to get page content: {e}")

    async def _search_pages_by_sections(self, query: str, token: str, max_results: int) -> tuple[List[Dict[str, Any]], int]:
        """
        Search pages by fetching all pages section-by-section and filtering by title.

        This is a fallback method when the main search endpoint fails with 400 error
        for accounts with too many sections.

        Args:
            query: Search query
            token: Authentication token
            max_results: Maximum results to return

        Returns:
            Tuple of (pages data, api calls made)
        """
        try:
            logger.info(f"Using section-by-section search fallback for query: '{query}'")

            # Get all pages using our section-by-section approach
            all_pages = await self.get_all_pages()
            api_calls = len(await self._get_all_sections(token))  # Approximate API calls

            # Filter pages by title matching the query
            query_lower = query.lower()
            matching_pages = []

            for page in all_pages:
                if query_lower in page.title.lower():
                    matching_pages.append({
                        "id": page.id,
                        "title": page.title,
                        "createdDateTime": page.created_date_time.isoformat() if page.created_date_time else None,
                        "lastModifiedDateTime": page.last_modified_date_time.isoformat() if page.last_modified_date_time else None,
                        "contentUrl": page.content_url,
                        "parentSection": page.parent_section,
                        "parentNotebook": page.parent_notebook
                    })

                    if len(matching_pages) >= max_results:
                        break

            logger.info(f"Section-by-section search found {len(matching_pages)} matching pages")
            return matching_pages, api_calls

        except Exception as e:
            logger.error(f"Section-by-section search failed: {e}")
            return [], 0

    async def ensure_authenticated(self) -> bool:
        """
        Ensure that the user is properly authenticated.

        Returns:
            True if authentication is successful, False otherwise
        """
        try:
            token = await self.authenticator.get_valid_token()
            return token is not None and token.strip() != ""
        except Exception as e:
            logger.error(f"Authentication check failed: {e}")
            return False


if __name__ == "__main__":
    """Test OneNote search functionality."""
    async def test_search():
        try:
            search_tool = OneNoteSearchTool()

            print("Testing OneNote search...")
            result = await search_tool.search_pages("test", max_results=5)

            print(f"✅ Search successful: {result.total_count} pages found")
            for page in result.pages[:3]:
                print(f"  - {page.title} ({page.get_notebook_name()})")

        except Exception as e:
            print(f"❌ Search test failed: {e}")

    asyncio.run(test_search())
