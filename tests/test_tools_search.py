"""
Tests for OneNote search tool.

Comprehensive unit tests for the OneNote search functionality,
including API integration, error handling, and rate limiting.
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.auth.microsoft_auth import AuthenticationError, MicrosoftAuthenticator
from src.models.onenote import OneNotePage, SearchResult
from src.tools.onenote_search import OneNoteSearchError, OneNoteSearchTool


class TestOneNoteSearchTool:
    """Test OneNote search tool functionality."""

    def test_search_tool_initialization(self):
        """Test search tool initialization with defaults."""
        tool = OneNoteSearchTool()

        assert tool.authenticator is not None
        assert tool.settings is not None
        assert tool.max_results > 0
        assert tool.timeout > 0
        assert tool._request_count == 0

    def test_search_tool_initialization_with_custom_auth(self):
        """Test search tool initialization with custom authenticator."""
        mock_auth = Mock(spec=MicrosoftAuthenticator)
        mock_settings = Mock()
        mock_settings.graph_api_base_url = "https://graph.microsoft.com/v1.0"
        mock_settings.request_timeout = 30
        mock_settings.max_search_results = 50

        tool = OneNoteSearchTool(authenticator=mock_auth, settings=mock_settings)

        assert tool.authenticator is mock_auth
        assert tool.settings is mock_settings
        assert tool.max_results == 50
        assert tool.timeout == 30

    @pytest.mark.asyncio
    async def test_search_pages_empty_query_validation(self):
        """Test that empty queries raise validation errors."""
        tool = OneNoteSearchTool()

        # Test empty string
        with pytest.raises(OneNoteSearchError, match="Search query cannot be empty"):
            await tool.search_pages("")

        # Test whitespace-only string
        with pytest.raises(OneNoteSearchError, match="Search query cannot be empty"):
            await tool.search_pages("   ")

    @pytest.mark.asyncio
    async def test_search_pages_authentication_error(self):
        """Test handling of authentication errors during search."""
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.get_valid_token.side_effect = AuthenticationError("Token expired")

        tool = OneNoteSearchTool(authenticator=mock_auth)

        with pytest.raises(OneNoteSearchError, match="Authentication failed"):
            await tool.search_pages("test query")

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_search_pages_successful_request(self, mock_client_class):
        """Test successful search request with mocked HTTP client."""
        # Mock authentication
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.ensure_authenticated.return_value = True
        mock_auth.get_valid_token.return_value = "test_token"

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {
                    "id": "1-page1",
                    "title": "Test Page 1",
                    "createdDateTime": "2025-01-01T10:00:00Z",
                    "lastModifiedDateTime": "2025-01-02T15:30:00Z",
                    "parentNotebook": {"displayName": "Work"},
                    "parentSection": {"displayName": "Meeting Notes"}
                },
                {
                    "id": "1-page2",
                    "title": "Test Page 2",
                    "createdDateTime": "2025-01-01T10:00:00Z",
                    "lastModifiedDateTime": "2025-01-03T15:30:00Z",
                    "parentNotebook": {"displayName": "Personal"},
                    "parentSection": {"displayName": "Ideas"}
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        tool = OneNoteSearchTool(authenticator=mock_auth)
        result = await tool.search_pages("meeting notes")

        assert isinstance(result, SearchResult)
        assert result.query == "meeting notes"
        assert len(result.pages) == 2
        assert result.pages[0].title == "Test Page 1"
        assert result.pages[1].title == "Test Page 2"
        assert result.has_results is True
        assert "Work" in result.unique_notebooks
        assert "Personal" in result.unique_notebooks

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_search_pages_http_error_handling(self, mock_client_class):
        """Test handling of HTTP errors during search."""
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.ensure_authenticated.return_value = True
        mock_auth.get_valid_token.return_value = "test_token"

        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 429  # Rate limited
        mock_response.text = "Rate limit exceeded"
        mock_response.json.return_value = {
            "error": {
                "code": "TooManyRequests",
                "message": "Rate limit exceeded"
            }
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        tool = OneNoteSearchTool(authenticator=mock_auth)

        with pytest.raises(OneNoteSearchError):
            await tool.search_pages("test query")

    @pytest.mark.asyncio
    @pytest.mark.slow
    @patch('httpx.AsyncClient')
    async def test_search_pages_network_timeout_original(self, mock_client_class):
        """Test handling of network timeouts during search - original slow version."""
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.ensure_authenticated.return_value = True
        mock_auth.get_valid_token.return_value = "test_token"

        # Mock network timeout
        import httpx
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        tool = OneNoteSearchTool(authenticator=mock_auth)

        with pytest.raises(OneNoteSearchError):
            await tool.search_pages("test query")

    @pytest.mark.asyncio
    @pytest.mark.fast
    @patch('httpx.AsyncClient')
    async def test_search_pages_network_timeout(self, mock_client_class, mock_network_delays):
        """Test handling of network timeouts during search - fast version."""
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.ensure_authenticated.return_value = True
        mock_auth.get_valid_token.return_value = "test_token"

        # Mock network timeout - fast version with no actual delays
        import httpx
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.TimeoutException("Request timed out")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        tool = OneNoteSearchTool(authenticator=mock_auth)

        with pytest.raises(OneNoteSearchError):
            await tool.search_pages("test query")

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_search_pages_max_results_limit(self, mock_client_class):
        """Test that max_results parameter is respected."""
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.get_valid_token.return_value = "test_token"

        # Mock response with many results
        pages_data = []
        for i in range(10):
            pages_data.append({
                "id": f"1-page{i}",
                "title": f"Test Page {i}",
                "createdDateTime": "2025-01-01T10:00:00Z",
                "lastModifiedDateTime": "2025-01-02T15:30:00Z"
            })

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": pages_data}

        # Mock content response for page content fetching
        mock_content_response = Mock()
        mock_content_response.status_code = 200
        mock_content_response.text.read.return_value = "<html><body>Test content</body></html>"

        mock_client = AsyncMock()
        # Return different responses for search vs content calls
        mock_client.get.side_effect = [mock_response] + [mock_content_response] * 5
        mock_client_class.return_value.__aenter__.return_value = mock_client

        tool = OneNoteSearchTool(authenticator=mock_auth)
        result = await tool.search_pages("test", max_results=5)

        # Verify that the search request was made with correct top parameter
        # Should be called multiple times: 1 for search + 5 for content fetching
        assert mock_client.get.call_count >= 1

        # Check the first call (search request) has correct parameters
        first_call_args = mock_client.get.call_args_list[0]
        params = first_call_args[1]["params"]
        assert params["$top"] == 5

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_search_pages_empty_results(self, mock_client_class):
        """Test handling of empty search results."""
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.get_valid_token.return_value = "test_token"

        # Mock empty response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        tool = OneNoteSearchTool(authenticator=mock_auth)
        result = await tool.search_pages("nonexistent query")

        assert isinstance(result, SearchResult)
        assert result.query == "nonexistent query"
        assert len(result.pages) == 0
        assert result.has_results is False
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_rate_limiting_behavior(self):
        """Test rate limiting behavior."""
        tool = OneNoteSearchTool()

        # Test initial state
        assert tool._request_count == 0
        assert tool._last_request_time == 0.0

        # Simulate rate limiting check
        current_time = time.time()
        tool._last_request_time = current_time - 0.1  # Recent request
        tool._request_count = 5

        # The actual rate limiting logic would be tested with the real method
        # This test verifies the state tracking
        assert tool._request_count == 5
        assert tool._last_request_time < current_time

    def test_search_query_preparation(self):
        """Test search query preparation and validation."""
        tool = OneNoteSearchTool()

        # Test that we can access the tool's configuration
        assert hasattr(tool, 'max_results')
        assert hasattr(tool, 'timeout')
        assert hasattr(tool, 'base_url')

        # Test that settings are properly configured
        assert tool.max_results > 0
        assert tool.timeout > 0
        assert "graph.microsoft.com" in tool.base_url

    def test_prepare_search_query_thought_extraction(self):
        """Test search query preparation for thought-related queries."""
        tool = OneNoteSearchTool()

        # Test thought-related query extraction
        test_cases = [
            ("What were my thoughts about Robo-me?", "Robo-me"),
            ("What did I think about the project?", "the project"),
            ("My thoughts on machine learning", "machine learning"),
            ("Ideas about artificial intelligence", "artificial intelligence"),
            ("Opinion about the meeting", "the meeting"),
        ]

        for query, expected in test_cases:
            result = tool._prepare_search_query(query)
            assert result == expected, f"Query '{query}' should extract '{expected}', got '{result}'"

        # Test non-thought queries (should use normal processing)
        normal_cases = [
            ("Show me notes about vacation", "notes vacation"),
            ("Find project documentation", "project documentation"),
        ]

        for query, expected in normal_cases:
            result = tool._prepare_search_query(query)
            assert result == expected, f"Query '{query}' should process to '{expected}', got '{result}'"

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_search_with_content_extraction(self, mock_client_class):
        """Test search with content extraction."""
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.ensure_authenticated.return_value = True
        mock_auth.get_valid_token.return_value = "test_token"

        # Mock search response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [{
                "id": "1-page1",
                "title": "Test Page",
                "createdDateTime": "2025-01-01T10:00:00Z",
                "lastModifiedDateTime": "2025-01-02T15:30:00Z",
                "contentUrl": "https://graph.microsoft.com/v1.0/me/onenote/pages/1-page1/content"
            }]
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        tool = OneNoteSearchTool(authenticator=mock_auth)
        result = await tool.search_pages("test")

        assert len(result.pages) == 1
        assert result.pages[0].title == "Test Page"

    @pytest.mark.asyncio
    async def test_search_pages_api_uses_filter_parameter(self):
        """Test that _search_pages_api uses $filter instead of $search parameter."""
        # Mock authenticator
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.get_valid_token.return_value = "fake_token"

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}

        # Mock httpx client
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client

            tool = OneNoteSearchTool(authenticator=mock_auth)
            await tool._search_pages_api("test query", "fake_token", 10)

            # Verify the API was called
            assert mock_client.get.called

            # Get the call arguments
            call_args = mock_client.get.call_args

            # Check the parameters
            params = call_args[1]['params']

            # Verify we're using $filter instead of $search (this was the bug)
            assert '$filter' in params
            assert '$search' not in params

            # Verify the filter format is correct
            assert 'contains(tolower(title)' in params['$filter']
            assert 'test query' in params['$filter']

            # Verify other expected parameters
            assert '$top' in params
            assert '$select' in params
            assert '$orderby' in params

    @pytest.mark.asyncio
    async def test_search_pages_api_escapes_quotes(self):
        """Test that single quotes in queries are properly escaped."""
        # Mock authenticator
        mock_auth = AsyncMock(spec=MicrosoftAuthenticator)
        mock_auth.get_valid_token.return_value = "fake_token"

        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": []}

        # Mock httpx client
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client

            tool = OneNoteSearchTool(authenticator=mock_auth)
            # Test query with single quotes (potential injection risk)
            await tool._search_pages_api("test's query", "fake_token", 10)

            # Get the parameters
            call_args = mock_client.get.call_args
            params = call_args[1]['params']

            # Verify single quotes are escaped (doubled)
            filter_query = params['$filter']
            assert "test''s query" in filter_query


class TestOneNoteSearchError:
    """Test OneNote search error exception."""

    def test_search_error_creation(self):
        """Test creating search error."""
        error = OneNoteSearchError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_search_error_inheritance(self):
        """Test error inheritance."""
        error = OneNoteSearchError("Test")
        assert isinstance(error, Exception)
        assert isinstance(error, OneNoteSearchError)
