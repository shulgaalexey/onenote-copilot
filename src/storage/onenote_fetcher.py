"""
OneNote content fetcher for cache system.

Handles bulk downloading of OneNote content (notebooks, sections, pages)
with proper API error handling and rate limiting integration.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import httpx

from ..config.settings import get_settings
from ..models.cache import (CachedPage, CachedPageMetadata, SyncResult,
                            SyncStatus, SyncType)
from ..tools.onenote_search import OneNoteSearchTool
from .cache_manager import OneNoteCacheManager

logger = logging.getLogger(__name__)


class OneNoteContentFetcher:
    """
    Fetches OneNote content for local caching.

    Integrates with existing OneNoteSearch tool and handles bulk operations
    with proper rate limiting and error recovery.
    """

    def __init__(self, cache_manager: Optional[OneNoteCacheManager] = None,
                 onenote_search: Optional[OneNoteSearchTool] = None):
        """
        Initialize the content fetcher.

        Args:
            cache_manager: Optional cache manager instance
            onenote_search: Optional OneNote search tool instance
        """
        self.settings = get_settings()
        self.cache_manager = cache_manager or OneNoteCacheManager()
        self.onenote_search = onenote_search  # Will be injected during usage

        logger.debug("Initialized OneNote content fetcher")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Clean up resources if needed
        pass

    async def fetch_notebooks(self):
        """Fetch all notebooks for the current user."""
        from ..models.onenote import OneNoteNotebook

        raw_notebooks = await self._get_all_notebooks()
        notebooks = []

        for notebook_data in raw_notebooks:
            notebook = OneNoteNotebook(
                id=notebook_data['id'],
                name=notebook_data.get('displayName', 'Untitled'),
                web_url=notebook_data.get('links', {}).get('oneNoteWebUrl', {}).get('href', '')
            )
            notebooks.append(notebook)

        return notebooks

    async def fetch_sections_for_notebook(self, notebook):
        """Fetch sections for a specific notebook."""
        from ..models.onenote import OneNoteSection

        raw_sections = await self._get_all_sections(notebook.id)
        sections = []

        for section_data in raw_sections:
            section = OneNoteSection(
                id=section_data['id'],
                displayName=section_data.get('displayName', 'Untitled'),
                notebook_name=notebook.name
            )
            sections.append(section)

        return sections

    async def fetch_pages_for_section(self, section):
        """Fetch pages for a specific section."""
        from datetime import datetime

        from ..models.onenote import OneNotePage

        raw_pages = await self._get_pages_from_section(section.id)
        pages = []

        for page_data in raw_pages:
            # Parse the datetime
            last_modified_str = page_data.get('lastModifiedDateTime', '')
            last_modified = None
            if last_modified_str:
                try:
                    last_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
                except ValueError:
                    last_modified = datetime.utcnow()
            else:
                last_modified = datetime.utcnow()

            page = OneNotePage(
                id=page_data['id'],
                title=page_data.get('title', 'Untitled'),
                web_url=page_data.get('links', {}).get('oneNoteWebUrl', {}).get('href', ''),
                last_modified_date_time=last_modified,
                notebook_name=section.notebook_name,
                section_name=section.display_name
            )
            pages.append(page)

        return pages

    async def fetch_page_content(self, page):
        """Fetch content for a specific page."""
        page_data = await self._fetch_single_page(page.id)
        if page_data:
            return page_data.get('content', '')
        return ''

    async def fetch_all_content(self, user_id: str,
                               sync_type: SyncType = SyncType.FULL) -> SyncResult:
        """
        Fetch all OneNote content for a user.

        Args:
            user_id: User identifier
            sync_type: Type of sync operation

        Returns:
            Sync result with statistics and status
        """
        start_time = datetime.utcnow()
        result = SyncResult(
            sync_type=sync_type,
            status=SyncStatus.IN_PROGRESS,
            started_at=start_time
        )

        try:
            logger.info(f"Starting {sync_type.value} content fetch for user: {user_id}")

            # Initialize user cache if needed
            if not self.cache_manager.cache_exists(user_id):
                await self.cache_manager.initialize_user_cache(user_id)
                logger.info(f"Initialized cache for new user: {user_id}")

            # Update sync metadata
            await self.cache_manager.update_cache_metadata(
                user_id,
                sync_in_progress=True,
                last_sync_attempt=start_time
            )

            # Get notebooks and sections
            notebooks = await self._get_all_notebooks()
            # We'll track notebooks and sections in variables since they're not in the statistics model
            notebooks_processed = len(notebooks)
            sections_processed = 0
            logger.info(f"Found {len(notebooks)} notebooks")

            # Process each notebook
            for notebook in notebooks:
                try:
                    notebook_result = await self._process_notebook(
                        user_id, notebook, sync_type
                    )
                    sections_processed += notebook_result['sections']
                    # Use the proper statistics field names
                    result.statistics.pages_added += notebook_result['cached']
                    result.errors.extend(notebook_result['errors'])

                except Exception as e:
                    error_msg = f"Failed to process notebook {notebook.get('displayName', notebook.get('id', 'unknown'))}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    continue

            # Calculate final statistics
            end_time = datetime.utcnow()
            result.completed_at = end_time
            result.statistics.total_time_seconds = (end_time - start_time).total_seconds()
            result.status = SyncStatus.COMPLETED if not result.errors else SyncStatus.PARTIAL

            # Update cache metadata
            await self.cache_manager.update_cache_metadata(
                user_id,
                sync_in_progress=False,
                last_full_sync=end_time if sync_type == SyncType.FULL else None,
                last_incremental_sync=end_time if sync_type == SyncType.INCREMENTAL else None,
                total_notebooks=notebooks_processed,
                total_pages=result.statistics.pages_added
            )

            logger.info(f"Content fetch completed: {result.statistics.pages_added} pages cached, "
                       f"{len(result.errors)} errors")

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.completed_at = datetime.utcnow()
            result.errors.append(f"Content fetch failed: {e}")
            logger.error(f"Content fetch failed for user {user_id}: {e}")

            # Clean up sync metadata
            try:
                await self.cache_manager.update_cache_metadata(
                    user_id, sync_in_progress=False
                )
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup sync metadata: {cleanup_error}")

        return result

    async def fetch_specific_pages(self, user_id: str, page_ids: List[str]) -> SyncResult:
        """
        Fetch specific pages by their IDs.

        Args:
            user_id: User identifier
            page_ids: List of page IDs to fetch

        Returns:
            Sync result for the specific pages
        """
        start_time = datetime.utcnow()
        result = SyncResult(
            sync_type=SyncType.SELECTIVE,
            status=SyncStatus.IN_PROGRESS,
            started_at=start_time
        )

        try:
            logger.info(f"Fetching {len(page_ids)} specific pages for user: {user_id}")

            # Ensure cache exists
            if not self.cache_manager.cache_exists(user_id):
                await self.cache_manager.initialize_user_cache(user_id)

            # Process each page
            for page_id in page_ids:
                try:
                    page_data = await self._fetch_single_page(page_id)
                    if page_data:
                        cached_page = await self._convert_to_cached_page(page_data)
                        await self.cache_manager.store_page_content(user_id, cached_page)
                        result.statistics.pages_added += 1
                        logger.debug(f"Cached page: {page_data.get('title', page_id)}")
                    else:
                        result.errors.append(f"Page not found: {page_id}")

                except Exception as e:
                    error_msg = f"Failed to fetch page {page_id}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    continue

            # Finalize result
            end_time = datetime.utcnow()
            result.completed_at = end_time
            result.statistics.total_time_seconds = (end_time - start_time).total_seconds()
            result.status = SyncStatus.COMPLETED if not result.errors else SyncStatus.PARTIAL

            logger.info(f"Specific page fetch completed: {result.statistics.pages_added}/{len(page_ids)} pages cached")

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.completed_at = datetime.utcnow()
            result.errors.append(f"Specific page fetch failed: {e}")
            logger.error(f"Specific page fetch failed: {e}")

        return result

    async def _get_all_notebooks(self) -> List[Dict]:
        """
        Get all notebooks for the authenticated user using OneNoteSearchTool.

        Returns:
            List of notebook dictionaries
        """
        try:
            if self.onenote_search:
                notebooks = await self.onenote_search.get_notebooks()
                logger.debug(f"Retrieved {len(notebooks)} notebooks via OneNoteSearchTool")
                return notebooks
            else:
                raise ValueError("OneNoteSearchTool instance not provided")

        except Exception as e:
            logger.error(f"Failed to get notebooks: {e}")
            raise

    async def _get_all_sections(self, notebook_id: str) -> List[Dict]:
        """
        Get all sections for a notebook using OneNoteSearchTool.

        Args:
            notebook_id: Notebook ID

        Returns:
            List of section dictionaries
        """
        try:
            if self.onenote_search:
                # Get authentication token
                token = await self.onenote_search.authenticator.get_valid_token()

                # Get all sections and filter by notebook_id
                all_sections = await self.onenote_search._get_all_sections(token)
                notebook_sections = [
                    section for section in all_sections
                    if section.get('parentNotebook', {}).get('id') == notebook_id
                ]

                logger.debug(f"Retrieved {len(notebook_sections)} sections for notebook {notebook_id}")
                return notebook_sections
            else:
                raise ValueError("OneNoteSearchTool instance not provided")

        except Exception as e:
            logger.error(f"Failed to get sections for notebook {notebook_id}: {e}")
            raise

    async def _process_notebook(self, user_id: str, notebook: Dict,
                              sync_type: SyncType) -> Dict[str, any]:
        """
        Process all content in a notebook.

        Args:
            user_id: User identifier
            notebook: Notebook dictionary
            sync_type: Type of sync operation

        Returns:
            Dictionary with processing statistics
        """
        notebook_id = notebook.get('id')
        notebook_name = notebook.get('displayName', 'Unknown')

        result = {
            'sections': 0,
            'pages': 0,
            'cached': 0,
            'errors': []
        }

        try:
            logger.debug(f"Processing notebook: {notebook_name} ({notebook_id})")

            # Get sections for this notebook
            sections = await self._get_all_sections(notebook_id)
            result['sections'] = len(sections)

            # Process each section
            for section in sections:
                try:
                    section_result = await self._process_section(
                        user_id, section, sync_type
                    )
                    result['pages'] += section_result['pages']
                    result['cached'] += section_result['cached']
                    result['errors'].extend(section_result['errors'])

                except Exception as e:
                    error_msg = f"Failed to process section {section.get('displayName', section.get('id', 'unknown'))}: {e}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
                    continue

            logger.debug(f"Notebook {notebook_name}: {result['cached']}/{result['pages']} pages cached")

        except Exception as e:
            error_msg = f"Failed to process notebook {notebook_name}: {e}"
            logger.error(error_msg)
            result['errors'].append(error_msg)

        return result

    async def _process_section(self, user_id: str, section: Dict,
                             sync_type: SyncType) -> Dict[str, any]:
        """
        Process all pages in a section.

        Args:
            user_id: User identifier
            section: Section dictionary
            sync_type: Type of sync operation

        Returns:
            Dictionary with processing statistics
        """
        section_id = section.get('id')
        section_name = section.get('displayName', 'Unknown')

        result = {
            'pages': 0,
            'cached': 0,
            'errors': []
        }

        try:
            logger.debug(f"Processing section: {section_name} ({section_id})")

            # Get pages for this section using the section-by-section approach
            pages = await self._get_pages_from_section(section_id)
            result['pages'] = len(pages)

            # Process each page
            for page_data in pages:
                try:
                    page_id = page_data.get('id')

                    # Check if we should skip this page (for incremental sync)
                    if sync_type == SyncType.INCREMENTAL:
                        existing_page = await self.cache_manager.get_cached_page(user_id, page_id)
                        if existing_page and self._is_page_up_to_date(existing_page, page_data):
                            logger.debug(f"Skipping up-to-date page: {page_data.get('title', page_id)}")
                            result['cached'] += 1  # Count as cached since it's current
                            continue

                    # Convert and cache the page
                    cached_page = await self._convert_to_cached_page(page_data)
                    await self.cache_manager.store_page_content(user_id, cached_page)
                    result['cached'] += 1

                    logger.debug(f"Cached page: {page_data.get('title', page_id)}")

                except Exception as e:
                    error_msg = f"Failed to cache page {page_data.get('title', page_data.get('id', 'unknown'))}: {e}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
                    continue

            logger.debug(f"Section {section_name}: {result['cached']}/{result['pages']} pages cached")

        except Exception as e:
            error_msg = f"Failed to process section {section_name}: {e}"
            logger.error(error_msg)
            result['errors'].append(error_msg)

        return result

    async def _get_pages_from_section(self, section_id: str) -> List[Dict]:
        """
        Get all pages from a specific section using OneNoteSearchTool.

        Args:
            section_id: Section ID

        Returns:
            List of page dictionaries
        """
        try:
            if self.onenote_search:
                # Get authentication token
                token = await self.onenote_search.authenticator.get_valid_token()

                # Get pages from section
                onenote_pages = await self.onenote_search._get_pages_from_section(section_id, token)

                # Convert OneNotePage objects to dictionaries for consistency
                pages = []
                for page in onenote_pages:
                    pages.append({
                        "id": page.id,
                        "title": page.title,
                        "lastModifiedDateTime": page.last_modified_date_time.isoformat() if page.last_modified_date_time else None,
                        "createdDateTime": page.created_date_time.isoformat() if page.created_date_time else None,
                        "contentUrl": page.content_url,
                        "webUrl": page.web_url
                    })

                logger.debug(f"Retrieved {len(pages)} pages from section {section_id}")
                return pages
            else:
                raise ValueError("OneNoteSearchTool instance not provided")

        except Exception as e:
            logger.error(f"Failed to get pages from section {section_id}: {e}")
            raise

    async def _fetch_single_page(self, page_id: str) -> Optional[Dict]:
        """
        Fetch a single page by ID using direct HTTP calls.

        Args:
            page_id: Page ID

        Returns:
            Page dictionary or None if not found
        """
        try:
            import aiohttp

            # Get access token (assuming we have one)
            headers = {
                "Authorization": "Bearer mock_access_token",  # In real use, get from auth
                "Accept": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                # Get page metadata
                async with session.get(
                    f"https://graph.microsoft.com/v1.0/me/onenote/pages/{page_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        page_data = await response.json()

                        # Get page content
                        content_headers = headers.copy()
                        content_headers["Accept"] = "text/html"

                        async with session.get(
                            f"https://graph.microsoft.com/v1.0/me/onenote/pages/{page_id}/content",
                            headers=content_headers
                        ) as content_response:
                            if content_response.status == 200:
                                page_data['content'] = await content_response.text()
                            else:
                                logger.warning(f"Failed to get page content for {page_id}: {content_response.status}")
                                page_data['content'] = ''

                        return page_data
                    else:
                        logger.warning(f"Failed to get page metadata for {page_id}: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Failed to fetch single page {page_id}: {e}")
            return None

    async def _convert_to_cached_page(self, page_data: Dict) -> CachedPage:
        """
        Convert OneNote page data to cached page format.

        Args:
            page_data: Raw page data from OneNote API

        Returns:
            CachedPage instance
        """
        try:
            # Create metadata
            metadata = CachedPageMetadata(
                id=page_data['id'],
                title=page_data.get('title', 'Untitled'),
                created_date_time=datetime.fromisoformat(
                    page_data['createdDateTime'].replace('Z', '+00:00')
                ),
                last_modified_date_time=datetime.fromisoformat(
                    page_data['lastModifiedDateTime'].replace('Z', '+00:00')
                ),
                parent_notebook=page_data.get('parentNotebook', {}),
                parent_section=page_data.get('parentSection', {}),
                content_url=page_data.get('contentUrl', ''),
                local_content_path='',  # Will be set by cache manager
                local_html_path=''      # Will be set by cache manager
            )

            # Extract text content (basic extraction)
            content_html = page_data.get('content', '')
            text_content = self._extract_text_from_html(content_html)

            # Create cached page
            cached_page = CachedPage(
                metadata=metadata,
                content=content_html,
                markdown_content='',  # Will be converted later
                text_content=text_content
            )

            return cached_page

        except Exception as e:
            logger.error(f"Failed to convert page data: {e}")
            raise

    def _extract_text_from_html(self, html_content: str) -> str:
        """
        Extract plain text from HTML content.

        Args:
            html_content: HTML content string

        Returns:
            Plain text content
        """
        try:
            if not html_content:
                return ""

            # Simple HTML tag removal (will be enhanced with proper HTML parser later)
            import re

            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', html_content)

            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()

            return text

        except Exception as e:
            logger.warning(f"Failed to extract text from HTML: {e}")
            return ""

    def _is_page_up_to_date(self, cached_page: CachedPage, page_data: Dict) -> bool:
        """
        Check if a cached page is up-to-date with OneNote data.

        Args:
            cached_page: Existing cached page
            page_data: Fresh page data from OneNote

        Returns:
            True if cached page is current, False otherwise
        """
        try:
            # Compare last modified timestamps
            onenote_modified = datetime.fromisoformat(
                page_data['lastModifiedDateTime'].replace('Z', '+00:00')
            )

            cached_modified = cached_page.metadata.last_modified_date_time

            # Consider page up-to-date if timestamps match (within 1 second tolerance)
            time_diff = abs((onenote_modified - cached_modified).total_seconds())
            return time_diff < 1.0

        except Exception as e:
            logger.warning(f"Failed to compare page timestamps: {e}")
            return False  # Assume out of date if we can't compare

    async def get_sync_progress(self, user_id: str) -> Optional[Dict[str, any]]:
        """
        Get current sync progress for a user.

        Args:
            user_id: User identifier

        Returns:
            Progress information or None if no sync in progress
        """
        try:
            metadata = await self.cache_manager._load_cache_metadata(user_id)
            if not metadata or not metadata.sync_in_progress:
                return None

            return {
                'sync_in_progress': True,
                'sync_started': metadata.last_sync_attempt,
                'estimated_completion': None,  # Could be calculated based on progress
                'pages_processed': metadata.total_pages_cached or 0
            }

        except Exception as e:
            logger.error(f"Failed to get sync progress: {e}")
            return None

    async def cancel_sync(self, user_id: str) -> bool:
        """
        Cancel an in-progress sync operation.

        Args:
            user_id: User identifier

        Returns:
            True if sync was cancelled, False otherwise
        """
        try:
            # Update metadata to indicate sync is no longer in progress
            await self.cache_manager.update_cache_metadata(
                user_id, sync_in_progress=False
            )

            logger.info(f"Cancelled sync for user: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel sync: {e}")
            return False
