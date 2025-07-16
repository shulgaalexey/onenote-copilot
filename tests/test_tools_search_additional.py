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
        settings.graph_api_url = "https://graph.microsoft.com/v1.0"
        settings.search_url = "https://graph.microsoft.com/v1.0/search/query"
        settings.max_search_results = 20
        settings.request_timeout = 30
        return settings

    @pytest.fixture
    def search_tool(self, mock_settings):
        """Create OneNoteSearchTool instance with mocked dependencies."""
        with patch('src.tools.onenote_search.get_settings', return_value=mock_settings):
            tool = OneNoteSearchTool()
            tool.authenticator = Mock()
            return tool

    @pytest.mark.asyncio
    async def test_search_pages_authentication_required(self, search_tool):
        """Test search_pages raises error when authentication required."""
        search_tool.authenticator.get_access_token = AsyncMock(side_effect=Exception("Auth required"))

        with pytest.raises(OneNoteSearchError) as exc_info:
            await search_tool.search_pages("test query")

        assert "Authentication required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_http_client_error(self, search_tool):
        """Test search_pages handles HTTP client errors."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        with patch('aiohttp.ClientSession.post') as mock_post:
            # Simulate HTTP 400 client error
            mock_response = Mock()
            mock_response.status = 400
            mock_response.json = AsyncMock(return_value={"error": {"message": "Bad request"}})
            mock_response.text = AsyncMock(return_value="Bad request")
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            assert "HTTP 400" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_http_server_error(self, search_tool):
        """Test search_pages handles HTTP server errors."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        with patch('aiohttp.ClientSession.post') as mock_post:
            # Simulate HTTP 500 server error
            mock_response = Mock()
            mock_response.status = 500
            mock_response.json = AsyncMock(return_value={"error": {"message": "Internal server error"}})
            mock_response.text = AsyncMock(return_value="Internal server error")
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            assert "HTTP 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_timeout_error(self, search_tool):
        """Test search_pages handles timeout errors."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError("Request timeout")

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            assert "Request timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_aiohttp_client_error(self, search_tool):
        """Test search_pages handles aiohttp client errors."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = Exception("Connection failed")

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_pages_with_max_results_limit(self, search_tool):
        """Test search_pages respects max_results parameter."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        # Create mock response with multiple pages
        mock_pages = [
            {
                "id": f"page{i}",
                "title": f"Page {i}",
                "contentUrl": f"https://graph.microsoft.com/v1.0/pages/page{i}/content"
            }
            for i in range(50)  # More than max_results
        ]

        mock_response_data = {
            "value": [{
                "hits": mock_pages,
                "total": len(mock_pages)
            }]
        }

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await search_tool.search_pages("test query", max_results=10)

            # Should only return 10 pages despite 50 being available
            assert len(result.pages) == 10
            assert all(page.title.startswith("Page") for page in result.pages)

    @pytest.mark.asyncio
    async def test_search_pages_content_extraction_success(self, search_tool):
        """Test search_pages successfully extracts page content."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        # Mock search response
        mock_pages = [{
            "id": "page1",
            "title": "Test Page",
            "contentUrl": "https://graph.microsoft.com/v1.0/pages/page1/content"
        }]

        mock_search_response = {
            "value": [{
                "hits": mock_pages,
                "total": 1
            }]
        }

        # Mock content response
        mock_content = "<html><body><p>This is the page content</p></body></html>"

        with patch('aiohttp.ClientSession.post') as mock_post, \
             patch('aiohttp.ClientSession.get') as mock_get:

            # Setup search response
            mock_search_resp = Mock()
            mock_search_resp.status = 200
            mock_search_resp.json = AsyncMock(return_value=mock_search_response)
            mock_post.return_value.__aenter__.return_value = mock_search_resp

            # Setup content response
            mock_content_resp = Mock()
            mock_content_resp.status = 200
            mock_content_resp.text = AsyncMock(return_value=mock_content)
            mock_get.return_value.__aenter__.return_value = mock_content_resp

            result = await search_tool.search_pages("test query")

            assert len(result.pages) == 1
            page = result.pages[0]
            assert page.title == "Test Page"
            assert "This is the page content" in page.content

    @pytest.mark.asyncio
    async def test_search_pages_content_extraction_failure(self, search_tool):
        """Test search_pages handles content extraction failures gracefully."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        mock_pages = [{
            "id": "page1",
            "title": "Test Page",
            "contentUrl": "https://graph.microsoft.com/v1.0/pages/page1/content"
        }]

        mock_search_response = {
            "value": [{
                "hits": mock_pages,
                "total": 1
            }]
        }

        with patch('aiohttp.ClientSession.post') as mock_post, \
             patch('aiohttp.ClientSession.get') as mock_get:

            # Setup search response
            mock_search_resp = Mock()
            mock_search_resp.status = 200
            mock_search_resp.json = AsyncMock(return_value=mock_search_response)
            mock_post.return_value.__aenter__.return_value = mock_search_resp

            # Setup content response failure
            mock_get.side_effect = Exception("Content fetch failed")

            result = await search_tool.search_pages("test query")

            # Should still return the page but without content
            assert len(result.pages) == 1
            page = result.pages[0]
            assert page.title == "Test Page"
            assert page.content == ""

    @pytest.mark.asyncio
    async def test_search_pages_rate_limiting_with_retry(self, search_tool):
        """Test search_pages handles rate limiting with retry logic."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

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

        with patch('aiohttp.ClientSession.post') as mock_post, \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:

            mock_post.return_value.__aenter__.side_effect = mock_post_side_effect

            result = await search_tool.search_pages("test query")

            # Should have made 2 calls and slept for retry
            assert call_count == 2
            mock_sleep.assert_called_once_with(1)
            assert isinstance(result, SearchResult)

    @pytest.mark.asyncio
    async def test_search_pages_malformed_response(self, search_tool):
        """Test search_pages handles malformed JSON responses."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
            mock_response.text = AsyncMock(return_value="Invalid JSON response")
            mock_post.return_value.__aenter__.return_value = mock_response

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.search_pages("test query")

            assert "Invalid JSON" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_notebooks_success(self, search_tool):
        """Test get_notebooks successfully retrieves notebook list."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        mock_notebooks_response = {
            "value": [
                {"id": "nb1", "displayName": "Work Notebook"},
                {"id": "nb2", "displayName": "Personal Notebook"}
            ]
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_notebooks_response)
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await search_tool.get_notebooks()

            assert len(result) == 2
            assert "Work Notebook" in result
            assert "Personal Notebook" in result

    @pytest.mark.asyncio
    async def test_get_notebooks_authentication_error(self, search_tool):
        """Test get_notebooks handles authentication errors."""
        search_tool.authenticator.get_access_token = AsyncMock(side_effect=Exception("Auth failed"))

        with pytest.raises(OneNoteSearchError) as exc_info:
            await search_tool.get_notebooks()

        assert "Authentication required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_notebooks_http_error(self, search_tool):
        """Test get_notebooks handles HTTP errors."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = Mock()
            mock_response.status = 403
            mock_response.json = AsyncMock(return_value={"error": {"message": "Forbidden"}})
            mock_response.text = AsyncMock(return_value="Forbidden")
            mock_get.return_value.__aenter__.return_value = mock_response

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.get_notebooks()

            assert "HTTP 403" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_recent_pages_success(self, search_tool):
        """Test get_recent_pages successfully retrieves recent pages."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        mock_pages_response = {
            "value": [
                {
                    "id": "page1",
                    "title": "Recent Page 1",
                    "lastModifiedDateTime": "2024-01-15T10:00:00Z",
                    "contentUrl": "https://graph.microsoft.com/v1.0/pages/page1/content"
                },
                {
                    "id": "page2",
                    "title": "Recent Page 2",
                    "lastModifiedDateTime": "2024-01-14T10:00:00Z",
                    "contentUrl": "https://graph.microsoft.com/v1.0/pages/page2/content"
                }
            ]
        }

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_pages_response)
            mock_get.return_value.__aenter__.return_value = mock_response

            result = await search_tool.get_recent_pages(limit=5)

            assert len(result) == 2
            assert all(isinstance(page, OneNotePage) for page in result)
            assert result[0].title == "Recent Page 1"
            assert result[1].title == "Recent Page 2"

    @pytest.mark.asyncio
    async def test_get_recent_pages_authentication_error(self, search_tool):
        """Test get_recent_pages handles authentication errors."""
        search_tool.authenticator.get_access_token = AsyncMock(side_effect=Exception("Auth failed"))

        with pytest.raises(OneNoteSearchError) as exc_info:
            await search_tool.get_recent_pages()

        assert "Authentication required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_recent_pages_http_error(self, search_tool):
        """Test get_recent_pages handles HTTP errors."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="test_token")

        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = Mock()
            mock_response.status = 404
            mock_response.json = AsyncMock(return_value={"error": {"message": "Not found"}})
            mock_response.text = AsyncMock(return_value="Not found")
            mock_get.return_value.__aenter__.return_value = mock_response

            with pytest.raises(OneNoteSearchError) as exc_info:
                await search_tool.get_recent_pages()

            assert "HTTP 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ensure_authenticated_success(self, search_tool):
        """Test ensure_authenticated successfully validates token."""
        search_tool.authenticator.get_access_token = AsyncMock(return_value="valid_token")

        await search_tool.ensure_authenticated()

        search_tool.authenticator.get_access_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_failure(self, search_tool):
        """Test ensure_authenticated handles authentication failures."""
        from src.auth.microsoft_auth import AuthenticationError

        search_tool.authenticator.get_access_token = AsyncMock(
            side_effect=AuthenticationError("Token expired")
        )

        with pytest.raises(AuthenticationError):
            await search_tool.ensure_authenticated()

    def test_prepare_search_query_basic(self, search_tool):
        """Test _prepare_search_query with basic query."""
        query = "test search"
        result = search_tool._prepare_search_query(query)

        assert "test search" in result
        assert "entityTypes" in result
        assert "contentSources" in result

    def test_prepare_search_query_with_quotes(self, search_tool):
        """Test _prepare_search_query handles quoted strings."""
        query = 'search for "exact phrase" in notes'
        result = search_tool._prepare_search_query(query)

        assert '"exact phrase"' in result

    def test_prepare_search_query_escapes_special_chars(self, search_tool):
        """Test _prepare_search_query escapes special characters."""
        query = "search with & and | operators"
        result = search_tool._prepare_search_query(query)

        # Should escape special characters that could break search
        assert "&" not in result or "\\&" in result
        assert "|" not in result or "\\|" in result


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
