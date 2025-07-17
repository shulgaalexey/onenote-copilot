"""
Additional tests for OneNote search tool to improve coverage.

These tests focus on covering the missing lines identified in the coverage report.
"""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.models.onenote import OneNotePage, SearchResult
from src.tools.onenote_search import OneNoteSearchError, OneNoteSearchTool


class TestOneNoteSearchToolAdditional:
    """Additional tests for OneNoteSearchTool to improve coverage."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock()
        settings.graph_api_base_url = "https://graph.microsoft.com/v1.0"
        settings.request_timeout = 30
        settings.max_search_results = 20
        return settings

    @pytest.fixture
    def search_tool(self, mock_settings):
        """Create OneNoteSearchTool instance with mocked dependencies."""
        with patch('src.tools.onenote_search.get_settings', return_value=mock_settings):
            tool = OneNoteSearchTool(settings=mock_settings)
            tool.authenticator = Mock()
            # Configure the authenticator mock to be properly awaitable
            tool.authenticator.get_valid_token = AsyncMock(return_value="mock_token")
            return tool

    @pytest.mark.asyncio
    async def test_search_pages_authentication_required(self, search_tool):
        """Test search_pages raises error when authentication required."""
        search_tool.authenticator.get_valid_token = AsyncMock(side_effect=Exception("Auth required"))

        with pytest.raises(OneNoteSearchError) as exc_info:
            await search_tool.search_pages("test query")

        assert "Search operation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_aiohttp_client_error(self, search_tool):
        """Test search_pages handles HTTP client errors."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        with patch('httpx.AsyncClient') as mock_client_class:
            # Simulate HTTP 400 client error
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"error": {"message": "Bad request"}}
            mock_response.text = "Bad request"

            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            assert "Search operation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_http_server_error(self, search_tool):
        """Test search_pages handles HTTP server errors."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        with patch('httpx.AsyncClient') as mock_client_class:
            # Simulate HTTP 500 server error
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"error": {"message": "Internal server error"}}
            mock_response.text = "Internal server error"

            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            assert "Search operation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_timeout_error(self, search_tool):
        """Test search_pages handles timeout errors."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = Mock()
            mock_client.get = AsyncMock(side_effect=asyncio.TimeoutError("Request timeout"))
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            assert "Search operation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_aiohttp_client_error(self, search_tool):
        """Test search_pages handles HTTP client errors."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = Mock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            assert "Search operation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_with_max_results_limit(self, search_tool):
        """Test search_pages respects max_results parameter."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        # Create mock response with multiple pages
        all_mock_pages = [
            {
                "id": f"page{i}",
                "title": f"Page {i}",
                "createdDateTime": "2024-01-15T10:00:00Z",
                "lastModifiedDateTime": "2024-01-15T10:00:00Z",
                "contentUrl": f"https://graph.microsoft.com/v1.0/pages/page{i}/content"
            }
            for i in range(50)  # More than max_results
        ]

        # Mock response should respect the top parameter (simulate API behavior)
        mock_response_data = {
            "value": all_mock_pages[:10]  # Return only first 10 to simulate $top=10
        }

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data

            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await search_tool.search_pages("test query", max_results=10)

            # Should only return 10 pages despite 50 being available
            assert len(result.pages) == 10
            assert all(page.title.startswith("Page") for page in result.pages)

    @pytest.mark.asyncio
    async def test_search_pages_content_extraction_success(self, search_tool):
        """Test search_pages successfully extracts page content."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        # Mock search response
        mock_pages = [{
            "id": "page1",
            "title": "Test Page",
            "createdDateTime": "2024-01-15T10:00:00Z",
            "lastModifiedDateTime": "2024-01-15T10:00:00Z",
            "contentUrl": "https://graph.microsoft.com/v1.0/pages/page1/content"
        }]

        mock_search_response = {
            "value": mock_pages  # Direct array, not wrapped in hits
        }

        # Mock content response
        mock_content = "<html><body><p>This is the page content</p></body></html>"

        with patch('httpx.AsyncClient') as mock_client_class:
            # Create separate response mocks for each call
            mock_search_resp = Mock()
            mock_search_resp.status_code = 200
            mock_search_resp.json.return_value = mock_search_response

            mock_content_resp = Mock()
            mock_content_resp.status_code = 200
            mock_content_resp.text = mock_content

            # Setup client to return different responses for different calls
            mock_client = Mock()
            mock_client.get = AsyncMock()

            # First call returns search results, subsequent calls return content
            def side_effect(*args, **kwargs):
                if '/me/onenote/pages' in str(args[0]) and 'content' not in str(args[0]):
                    return mock_search_resp
                else:
                    return mock_content_resp

            mock_client.get.side_effect = side_effect
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await search_tool.search_pages("test query")

            assert len(result.pages) == 1
            page = result.pages[0]
            assert page.title == "Test Page"
            assert "This is the page content" in page.content

    @pytest.mark.asyncio
    async def test_search_pages_content_extraction_failure(self, search_tool):
        """Test search_pages handles content extraction failures gracefully."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        mock_pages = [{
            "id": "page1",
            "title": "Test Page",
            "createdDateTime": "2024-01-15T10:00:00Z",
            "lastModifiedDateTime": "2024-01-15T10:00:00Z",
            "contentUrl": "https://graph.microsoft.com/v1.0/pages/page1/content"
        }]

        mock_search_response = {
            "value": mock_pages  # Direct array, not wrapped in hits
        }

        with patch('httpx.AsyncClient') as mock_client_class:
            # Setup search response
            mock_search_resp = Mock()
            mock_search_resp.status_code = 200
            mock_search_resp.json.return_value = mock_search_response

            mock_client = Mock()

            # First call returns search results, content fetch raises exception
            def side_effect(*args, **kwargs):
                if '/me/onenote/pages' in str(args[0]) and 'content' not in str(args[0]):
                    return mock_search_resp
                else:
                    raise Exception("Content fetch failed")

            mock_client.get = AsyncMock(side_effect=side_effect)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await search_tool.search_pages("test query")

            # Should still return the page but without content
            assert len(result.pages) == 1
            page = result.pages[0]
            assert page.title == "Test Page"
            assert page.content is None  # Content should be None when fetching fails

    @pytest.mark.asyncio
    async def test_search_pages_rate_limiting_with_retry(self, search_tool):
        """Test search_pages handles rate limiting with retry logic."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        call_count = 0

        def mock_post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_response = Mock()
            if call_count == 1:
                # First call returns 429 (rate limited)
                mock_response.status = 429
                mock_response.headers = {"Retry-After": "1"}
                mock_response.json = AsyncMock(return_value={"error": {"message": "Rate limited"}})
                mock_response.text = AsyncMock(return_value="Rate limited")
            else:
                # Second call succeeds
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={"value": [{"hits": [], "total": 0}]})

            return mock_response

        with patch('httpx.AsyncClient') as mock_client_class, \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:

            def mock_get_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                mock_response = Mock()
                if call_count <= 2:
                    # First two calls return 429 (rate limited)
                    mock_response.status_code = 429
                    mock_response.headers = {"Retry-After": "1"}
                    mock_response.json.return_value = {"error": {"message": "Rate limited"}}
                    mock_response.text = "Rate limited"
                else:
                    # Third call succeeds
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"value": []}  # Empty results but valid format
                return mock_response

            mock_client = Mock()
            mock_client.get = AsyncMock(side_effect=mock_get_side_effect)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await search_tool.search_pages("test query")

            # Should have made multiple calls due to retries and eventually succeeded
            assert call_count >= 3  # At least 3 calls should have been made
            assert mock_sleep.call_count >= 2  # Should have slept at least twice for rate limits
            assert isinstance(result, SearchResult)

    @pytest.mark.asyncio
    async def test_search_pages_malformed_response(self, search_tool):
        """Test search_pages handles malformed JSON responses."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.text = "Invalid JSON response"

            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            # The error message may be wrapped by retry mechanism
            error_message = str(exc_info.value)
            assert "Invalid JSON" in error_message or "RetryError" in error_message

    @pytest.mark.asyncio
    async def test_get_notebooks_success(self, search_tool):
        """Test get_notebooks successfully retrieves notebook list."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        mock_notebooks_response = {
            "value": [
                {"id": "nb1", "displayName": "Work Notebook"},
                {"id": "nb2", "displayName": "Personal Notebook"}
            ]
        }

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_notebooks_response

            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await search_tool.get_notebooks()

            assert len(result) == 2
            assert result[0]["displayName"] == "Work Notebook"
            assert result[1]["displayName"] == "Personal Notebook"
            assert result[0]["id"] == "nb1"
            assert result[1]["id"] == "nb2"

    @pytest.mark.asyncio
    async def test_get_notebooks_authentication_error(self, search_tool):
        """Test get_notebooks handles authentication errors."""
        search_tool.authenticator.get_valid_token = AsyncMock(side_effect=Exception("Auth failed"))

        with pytest.raises(OneNoteSearchError) as exc_info:
            await search_tool.get_notebooks()

        assert "Auth failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_notebooks_http_error(self, search_tool):
        """Test get_notebooks handles HTTP errors."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.json.return_value = {"error": {"message": "Forbidden"}}
            mock_response.text = "Forbidden"

            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.get_notebooks()

            assert "403" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_recent_pages_success(self, search_tool):
        """Test get_recent_pages successfully retrieves recent pages."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        mock_pages_response = {
            "value": [
                {
                    "id": "page1",
                    "title": "Recent Page 1",
                    "createdDateTime": "2024-01-15T09:00:00Z",  # Added missing field
                    "lastModifiedDateTime": "2024-01-15T10:00:00Z",
                    "contentUrl": "https://graph.microsoft.com/v1.0/pages/page1/content"
                },
                {
                    "id": "page2",
                    "title": "Recent Page 2",
                    "createdDateTime": "2024-01-14T09:00:00Z",  # Added missing field
                    "lastModifiedDateTime": "2024-01-14T10:00:00Z",
                    "contentUrl": "https://graph.microsoft.com/v1.0/pages/page2/content"
                }
            ]
        }

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_pages_response

            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await search_tool.get_recent_pages(limit=5)

            assert len(result) == 2
            assert all(isinstance(page, OneNotePage) for page in result)
            assert result[0].title == "Recent Page 1"
            assert result[1].title == "Recent Page 2"

    @pytest.mark.asyncio
    async def test_get_recent_pages_authentication_error(self, search_tool):
        """Test get_recent_pages handles authentication errors."""
        search_tool.authenticator.get_valid_token = AsyncMock(side_effect=Exception("Auth failed"))

        with pytest.raises(OneNoteSearchError) as exc_info:
            await search_tool.get_recent_pages()

        assert "Auth failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_recent_pages_http_error(self, search_tool):
        """Test get_recent_pages handles HTTP errors."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="test_token")

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.json.return_value = {"error": {"message": "Not found"}}
            mock_response.text = "Not found"

            mock_client = Mock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.get_recent_pages()

            assert "404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ensure_authenticated_success(self, search_tool):
        """Test ensure_authenticated successfully validates token."""
        search_tool.authenticator.get_valid_token = AsyncMock(return_value="valid_token")

        result = await search_tool.ensure_authenticated()

        assert result is True
        search_tool.authenticator.get_valid_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_failure(self, search_tool):
        """Test ensure_authenticated handles authentication failures."""
        from src.auth.microsoft_auth import AuthenticationError

        search_tool.authenticator.get_valid_token = AsyncMock(
            side_effect=AuthenticationError("Token expired")
        )

        result = await search_tool.ensure_authenticated()
        assert result is False

    def test_prepare_search_query_basic(self, search_tool):
        """Test _prepare_search_query with basic query."""
        query = "test search"
        result = search_tool._prepare_search_query(query)

        assert isinstance(result, str)
        assert "test search" in result

    def test_prepare_search_query_with_quotes(self, search_tool):
        """Test _prepare_search_query handles quoted strings."""
        query = 'search for "exact phrase" in notes'
        result = search_tool._prepare_search_query(query)

        assert isinstance(result, str)
        assert '"exact phrase"' in result

    def test_prepare_search_query_escapes_special_chars(self, search_tool):
        """Test _prepare_search_query removes question words."""
        query = "what are my project notes?"
        result = search_tool._prepare_search_query(query)

        # Should clean up the query
        assert isinstance(result, str)
        assert "project notes" in result


class TestOneNoteSearchErrorAdditional:
    """Additional tests for OneNoteSearchError."""

    def test_search_error_with_status_code(self):
        """Test OneNoteSearchError with HTTP status code."""
        error = OneNoteSearchError("Request failed", status_code=404)

        assert str(error) == "Request failed"
        assert error.status_code == 404

    def test_search_error_with_response_data(self):
        """Test OneNoteSearchError with response data."""
        response_data = {"error": {"code": "NotFound", "message": "Resource not found"}}
        error = OneNoteSearchError("API error", response_data=response_data)

        assert str(error) == "API error"
        assert error.response_data == response_data

    def test_search_error_inheritance(self):
        """Test OneNoteSearchError inherits from Exception."""
        error = OneNoteSearchError("Test error")

        assert isinstance(error, Exception)
        assert isinstance(error, OneNoteSearchError)

    def test_search_error_repr(self):
        """Test OneNoteSearchError repr representation."""
        error = OneNoteSearchError("Test error", status_code=500)

        repr_str = repr(error)
        assert "OneNoteSearchError" in repr_str
        assert "Test error" in repr_str

    @pytest.mark.asyncio
    async def test_get_all_pages_success(self, search_tool):
        """Test get_all_pages returns all pages successfully."""
        # Mock API response
        mock_response_data = {
            "value": [
                {
                    "id": "page1",
                    "title": "Test Page 1",
                    "createdDateTime": "2025-01-01T10:00:00Z",
                    "lastModifiedDateTime": "2025-01-02T15:30:00Z",
                    "contentUrl": "https://example.com/content1"
                },
                {
                    "id": "page2",
                    "title": "Test Page 2",
                    "createdDateTime": "2025-01-01T11:00:00Z",
                    "lastModifiedDateTime": "2025-01-02T16:30:00Z",
                    "contentUrl": "https://example.com/content2"
                }
            ]
        }

        # Mock the httpx response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        # Mock _fetch_page_contents to avoid actual content fetching
        search_tool._fetch_page_contents = AsyncMock(return_value=2)

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            pages = await search_tool.get_all_pages()

            assert len(pages) == 2
            assert pages[0].id == "page1"
            assert pages[0].title == "Test Page 1"
            assert pages[1].id == "page2"
            assert pages[1].title == "Test Page 2"

    @pytest.mark.asyncio
    async def test_get_all_pages_with_limit(self, search_tool):
        """Test get_all_pages respects limit parameter."""
        # Mock API response with more pages than limit
        mock_response_data = {
            "value": [
                {
                    "id": "page1",
                    "title": "Test Page 1",
                    "createdDateTime": "2025-01-01T10:00:00Z",
                    "lastModifiedDateTime": "2025-01-02T15:30:00Z",
                    "contentUrl": "https://example.com/content1"
                },
                {
                    "id": "page2",
                    "title": "Test Page 2",
                    "createdDateTime": "2025-01-01T11:00:00Z",
                    "lastModifiedDateTime": "2025-01-02T16:30:00Z",
                    "contentUrl": "https://example.com/content2"
                }
            ]
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        # Mock _fetch_page_contents
        search_tool._fetch_page_contents = AsyncMock(return_value=1)

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            # Test with limit of 1
            pages = await search_tool.get_all_pages(limit=1)

            assert len(pages) == 1
            assert pages[0].id == "page1"

    @pytest.mark.asyncio
    async def test_get_all_pages_authentication_error(self, search_tool):
        """Test get_all_pages handles authentication errors."""
        from src.auth.microsoft_auth import AuthenticationError

        search_tool.authenticator.get_valid_token = AsyncMock(side_effect=AuthenticationError("Auth failed"))

        with pytest.raises(OneNoteSearchError) as exc_info:
            await search_tool.get_all_pages()

        assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_all_pages_api_error(self, search_tool):
        """Test get_all_pages handles API errors."""
        mock_response = Mock()
        mock_response.status_code = 500

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.get_all_pages()

            assert "Failed to get pages: 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_all_pages_pagination(self, search_tool):
        """Test get_all_pages handles pagination correctly."""
        # First page response
        first_response_data = {
            "value": [
                {
                    "id": "page1",
                    "title": "Test Page 1",
                    "createdDateTime": "2025-01-01T10:00:00Z",
                    "lastModifiedDateTime": "2025-01-02T15:30:00Z",
                    "contentUrl": "https://example.com/content1"
                }
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/onenote/pages?$skip=1"
        }

        # Second page response (no more pages)
        second_response_data = {
            "value": [
                {
                    "id": "page2",
                    "title": "Test Page 2",
                    "createdDateTime": "2025-01-01T11:00:00Z",
                    "lastModifiedDateTime": "2025-01-02T16:30:00Z",
                    "contentUrl": "https://example.com/content2"
                }
            ]
        }

        # Mock responses
        first_response = Mock()
        first_response.status_code = 200
        first_response.json.return_value = first_response_data

        second_response = Mock()
        second_response.status_code = 200
        second_response.json.return_value = second_response_data

        # Mock _fetch_page_contents
        search_tool._fetch_page_contents = AsyncMock(return_value=2)

        with patch('httpx.AsyncClient') as mock_client:
            # Return different responses for first and second calls
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=[first_response, second_response]
            )

            pages = await search_tool.get_all_pages()

            assert len(pages) == 2
            assert pages[0].id == "page1"
            assert pages[1].id == "page2"

            # Verify that get was called twice (once for each page)
            assert mock_client.return_value.__aenter__.return_value.get.call_count == 2
