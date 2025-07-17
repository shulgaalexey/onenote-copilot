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
                logger.debug(f"Extracted subject from thought query: '{subject}'")
                return subject

        # Remove only very specific question words at the beginning - be more conservative
        question_patterns = [
            r'^show\s+me\s+',
            r'^find\s+me\s+',
            r'^search\s+for\s+',
            r'^look\s+for\s+'
        ]

        for pattern in question_patterns:
            query = re.sub(pattern, '', query, flags=re.IGNORECASE)

        # Only remove filler words if they're not part of the main content
        # Be more selective about word removal to preserve semantic meaning
        if query.startswith('about '):
            query = query[6:]  # Remove 'about ' from start only

        # Clean up extra whitespace
        query = re.sub(r'\s+', ' ', query).strip()

        # If query is too short after processing, use original minus punctuation
        if len(query) < 3:
            query = re.sub(r'[?!]', '', natural_query.strip())

        logger.debug(f"Processed query: '{natural_query}' -> '{query}'")
        return query

    def _generate_query_variations(self, natural_query: str) -> List[str]:
        """
        Generate multiple query variations to improve search success.

        Args:
            natural_query: Original natural language query

        Returns:
            List of query variations to try
        """
        variations = []

        # Always include the original query (cleaned)
        original = re.sub(r'[?!]', '', natural_query.strip())
        variations.append(original)

        # Add processed version
        processed = self._prepare_search_query(natural_query)
        if processed and processed != original:
            variations.append(processed)

        # Extract key content words (preserve important terms)
        import re
        words = re.findall(r'\b\w+\b', natural_query.lower())
        content_words = [w for w in words if w not in {
            'what', 'did', 'i', 'write', 'about', 'the', 'a', 'an', 'and', 'or',
            'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'
        }]

        if content_words:
            # Join content words
            content_query = ' '.join(content_words)
            if content_query and content_query not in variations:
                variations.append(content_query)

            # Try just the last content word (often the main topic)
            if len(content_words) > 1:
                last_word = content_words[-1]
                if last_word not in variations:
                    variations.append(last_word)

        # Remove empty variations and deduplicate
        variations = [v for v in variations if v and len(v.strip()) >= 2]
        unique_variations = []
        for v in variations:
            if v not in unique_variations:
                unique_variations.append(v)

        logger.debug(f"Generated {len(unique_variations)} query variations: {unique_variations}")
        return unique_variations

    async def search_pages(self, query: str, max_results: Optional[int] = None) -> SearchResult:
        """
        Search OneNote pages using the Microsoft Graph API.

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

            logger.debug(f"Searching OneNote pages for: '{original_query}' (processed: '{processed_query}')")

            # Get authentication token
            token = await self.authenticator.get_valid_token()

            # Search pages by title first
            pages_data, api_calls = await self._search_pages_api(processed_query, token, max_results)

            # If title search yields few results, try content search
            if len(pages_data) < 3:
                logger.debug(f"Title search returned {len(pages_data)} results, trying content search")
                content_pages_data, content_api_calls = await self._search_pages_by_content(processed_query, token, max_results)
                api_calls += content_api_calls

                # Merge results, avoiding duplicates
                existing_ids = {page.get('id') for page in pages_data}
                for page in content_pages_data:
                    if page.get('id') not in existing_ids:
                        pages_data.append(page)
                        if len(pages_data) >= max_results:
                            break

            # If still no results, try query variations
            if len(pages_data) == 0:
                logger.debug("No results found, trying query variations")
                query_variations = self._generate_query_variations(original_query)

                for i, variation in enumerate(query_variations[1:], 1):  # Skip first (already tried)
                    if len(pages_data) >= max_results:
                        break

                    logger.debug(f"Trying variation {i}: '{variation}'")

                    # Try title search with variation
                    var_pages_data, var_api_calls = await self._search_pages_api(variation, token, max_results)
                    api_calls += var_api_calls

                    # Add new results
                    existing_ids = {page.get('id') for page in pages_data}
                    for page in var_pages_data:
                        if page.get('id') not in existing_ids:
                            pages_data.append(page)

                    # If we found results, also try content search for this variation
                    if len(var_pages_data) > 0 and len(pages_data) < max_results:
                        var_content_pages, var_content_api_calls = await self._search_pages_by_content(variation, token, max_results - len(pages_data))
                        api_calls += var_content_api_calls

                        for page in var_content_pages:
                            if page.get('id') not in existing_ids:
                                pages_data.append(page)
                                if len(pages_data) >= max_results:
                                    break

                    # Stop if we found enough results
                    if len(pages_data) >= 3:  # Found some results
                        logger.debug(f"Found {len(pages_data)} results with variation '{variation}'")
                        break

            # Convert to OneNotePage models
            pages = []
            for page_data in pages_data:
                try:
                    page = OneNotePage(**page_data)
                    pages.append(page)
                except Exception as e:
                    logger.warning(f"Failed to parse page data: {e}")
                    continue

            # Fetch content for top results
            if pages:
                content_api_calls = await self._fetch_page_contents(pages[:5], token)
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
                    "search_parameter": "$search",
                    "original_query": original_query,
                    "processed_query": processed_query,
                    "content_fetched": min(5, len(pages))
                }
            )

            logger.info(f"Search completed: {len(pages)} pages found in {execution_time:.2f}s")
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

    async def _search_pages_by_content(self, query: str, token: str, max_results: int) -> tuple[List[Dict[str, Any]], int]:
        """
        Search pages by fetching recent pages and filtering by content.

        This is a fallback method when title search doesn't yield enough results.
        It fetches recent pages and searches their content locally.

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

        # Get recent pages (no filter, just recent ones)
        params = {
            "$top": min(20, max_results * 2),  # Get more pages to search through
            "$select": "id,title,createdDateTime,lastModifiedDateTime,contentUrl,parentSection,parentNotebook",
            "$expand": "parentSection,parentNotebook",
            "$orderby": "lastModifiedDateTime desc"
        }

        endpoint = f"{self.base_url}/me/onenote/pages"
        api_calls = 0

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=headers, params=params)

                if response.status_code != 200:
                    logger.warning(f"Content search failed: {response.status_code}")
                    return [], 1

                data = response.json()
                pages = data.get("value", [])
                api_calls += 1

                if not pages:
                    return [], api_calls

                logger.debug(f"Fetched {len(pages)} recent pages for content search")

                # Convert to OneNotePage objects for content fetching
                page_objects = []
                for page_data in pages:
                    try:
                        page = OneNotePage(**page_data)
                        page_objects.append(page)
                    except Exception as e:
                        logger.warning(f"Failed to parse page data: {e}")
                        continue

                # Fetch content for these pages
                content_api_calls = await self._fetch_page_contents(page_objects, token)
                api_calls += content_api_calls

                # Filter pages by content
                matching_pages = []
                query_lower = query.lower()

                for page in page_objects:
                    if hasattr(page, 'text_content') and page.text_content:
                        if query_lower in page.text_content.lower():
                            # Convert back to dict format to match expected return type
                            page_dict = {
                                'id': page.id,
                                'title': page.title,
                                'createdDateTime': page.created_date_time,
                                'lastModifiedDateTime': page.last_modified_date_time,
                                'contentUrl': page.content_url,
                                'parentSection': page.parent_section,
                                'parentNotebook': page.parent_notebook
                            }
                            matching_pages.append(page_dict)

                            if len(matching_pages) >= max_results:
                                break

                logger.debug(f"Content search found {len(matching_pages)} matching pages")
                return matching_pages, api_calls

        except httpx.TimeoutException:
            raise OneNoteSearchError("Content search request timed out")
        except Exception as e:
            logger.error(f"Content search failed: {e}")
            return [], api_calls

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
                import re

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
        Enforce rate limiting to respect Microsoft Graph API limits.

        Microsoft Graph allows 10,000 requests per 10 minutes per user.
        We implement a conservative rate limit to avoid hitting the limit.
        """
        current_time = time.time()

        # Reset counter every 10 minutes
        if current_time - self._rate_limit_window_start > 600:  # 10 minutes
            self._request_count = 0
            self._rate_limit_window_start = current_time

        # Check if we're approaching the limit
        if self._request_count >= 100:  # Conservative limit
            wait_time = 600 - (current_time - self._rate_limit_window_start)
            if wait_time > 0:
                logger.warning(f"Rate limit approaching, waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time)
                self._request_count = 0
                self._rate_limit_window_start = time.time()

        # Ensure minimum delay between requests
        time_since_last = current_time - self._last_request_time
        if time_since_last < 0.1:  # Minimum 100ms between requests
            await asyncio.sleep(0.1 - time_since_last)

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
                else:
                    raise OneNoteSearchError(f"Failed to get recent pages: {response.status_code}")

        except AuthenticationError:
            raise OneNoteSearchError("Authentication failed - please log in again")
        except Exception as e:
            logger.error(f"Failed to get recent pages: {e}")
            raise OneNoteSearchError(f"Failed to get recent pages: {e}")

    async def get_all_pages(self, limit: Optional[int] = None) -> List[OneNotePage]:
        """
        Get all OneNote pages from all notebooks.

        Args:
            limit: Optional maximum number of pages to return

        Returns:
            List of all pages from all notebooks with content loaded

        Raises:
            OneNoteSearchError: If operation fails
        """
        try:
            token = await self.authenticator.get_valid_token()

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Build params for API call
            params = {
                "$select": "id,title,createdDateTime,lastModifiedDateTime,contentUrl,parentSection,parentNotebook",
                "$expand": "parentSection,parentNotebook",
                "$orderby": "lastModifiedDateTime desc"
            }

            # Add limit if specified
            if limit:
                params["$top"] = min(limit, 200)  # API limit is typically 200

            endpoint = f"{self.base_url}/me/onenote/pages"

            all_pages = []
            next_url = None

            # Handle pagination if no limit specified
            while True:
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
                                all_pages.append(page)

                                # Stop if we've reached the limit
                                if limit and len(all_pages) >= limit:
                                    break
                            except Exception as e:
                                logger.warning(f"Failed to parse page data: {e}")
                                continue

                        # Check for more pages (pagination)
                        next_url = data.get("@odata.nextLink")

                        # Stop if we've reached the limit or no more pages
                        if (limit and len(all_pages) >= limit) or not next_url:
                            break
                    else:
                        raise OneNoteSearchError(f"Failed to get pages: {response.status_code}")

            logger.info(f"Retrieved {len(all_pages)} pages from all notebooks")

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

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(endpoint, headers=headers, params=params)

                if response.status_code == 200:
                    data = response.json()
                    return data.get("value", [])
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
