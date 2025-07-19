"""
Additional tests for OneNote agent module to improve coverage.

These tests focus on covering the missing lines identified in the coverage report.
"""

import json
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest
from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)

from src.agents.onenote_agent import MessagesState, OneNoteAgent
from src.models.responses import AgentState


class TestOneNoteAgentAdditional:
    """Additional tests for OneNoteAgent to improve coverage."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        from pathlib import Path
        settings = Mock()
        settings.openai_api_key = "test-key"
        settings.openai_model = "gpt-4"
        settings.openai_temperature = 0.7
        settings.max_search_results = 10
        settings.azure_client_id = "test-client-id"
        # Required for MSAL authentication
        settings.msal_authority = "https://login.microsoftonline.com/common"
        settings.msal_scopes = ["https://graph.microsoft.com/.default"]
        settings.token_cache_path = Path("test_cache.bin")
        settings.msal_client_id = "test-client-id"
        return settings

    @pytest.fixture
    def agent(self, mock_settings):
        """Create OneNoteAgent instance with mocked dependencies."""
        with patch('src.agents.onenote_agent.get_settings', return_value=mock_settings):
            agent = OneNoteAgent()
            agent.search_tool = Mock()
            return agent

    @pytest.mark.asyncio
    async def test_agent_node_with_no_results_tool_response(self, agent):
        """Test agent node handling tool response with NO_RESULTS prefix."""
        # Create state with tool response indicating no results - use MessagesState format
        state = {
            "messages": [
                HumanMessage(content="search for project notes"),
                AIMessage(content="NO_RESULTS: No pages found matching your search criteria")
            ]
        }

        # Mock the LLM response
        mock_response = AIMessage(content="I couldn't find any pages matching your search.")

        with patch.object(agent, '_llm') as mock_llm, \
             patch('src.agents.onenote_agent.get_system_prompt', return_value="System prompt"), \
             patch('src.agents.onenote_agent.get_no_results_prompt', return_value="No results prompt"):
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            # Verify the response was generated for no results
            assert len(result["messages"]) == 4  # System + Human + AI(NO_RESULTS) + AI(response)
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with no results prompt
            call_args = mock_llm.ainvoke.call_args[0][0]
            assert len(call_args) == 2
            assert isinstance(call_args[0], SystemMessage)
            assert isinstance(call_args[1], HumanMessage)

    @pytest.mark.asyncio
    async def test_agent_node_with_recent_pages_tool_response(self, agent):
        """Test agent node handling tool response with RECENT_PAGES prefix."""
        tool_message = AIMessage(
            content="RECENT_PAGES:\nPage 1: Meeting Notes\nPage 2: Project Ideas"
        )

        state = MessagesState(
            messages=[
                HumanMessage(content="show me recent pages"),
                tool_message
            ]
        )

        mock_response = AIMessage(content="Here are your recent pages...")

        with patch.object(agent, 'llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 4  # System + Human + Tool + AI response
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with recent pages content
            call_args = mock_llm.ainvoke.call_args[0][0]
            prompt_content = call_args[1].content
            assert "Page 1: Meeting Notes" in prompt_content
            assert "Page 2: Project Ideas" in prompt_content

    @pytest.mark.asyncio
    async def test_agent_node_with_notebooks_tool_response(self, agent):
        """Test agent node handling tool response with NOTEBOOKS prefix."""
        tool_message = AIMessage(
            content="NOTEBOOKS:\nWork Notebook\nPersonal Notebook\nProject Notebook"
        )

        state = MessagesState(
            messages=[
                HumanMessage(content="list my notebooks"),
                tool_message
            ]
        )

        mock_response = AIMessage(content="Here are your OneNote notebooks...")

        with patch.object(agent, '_llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 4  # System + Human + Tool + AI response
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with notebooks content
            call_args = mock_llm.ainvoke.call_args[0][0]
            prompt_content = call_args[1].content
            assert "Work Notebook" in prompt_content
            assert "Personal Notebook" in prompt_content

    @pytest.mark.asyncio
    async def test_agent_node_with_error_tool_response(self, agent):
        """Test agent node handling tool response with error content."""
        tool_message = AIMessage(
            content="SEARCH_ERROR: Failed to connect to OneNote API"
        )

        state = MessagesState(
            messages=[
                HumanMessage(content="search for notes"),
                tool_message
            ]
        )

        result = await agent._agent_node(state)

        # Verify error response was generated directly
        assert len(result["messages"]) == 4  # System + Human + Tool + Error response
        error_response = result["messages"][-1]
        assert isinstance(error_response, AIMessage)
        assert "Failed to connect to OneNote API" in error_response.content

    @pytest.mark.asyncio
    async def test_agent_node_needs_tool_call_for_search(self, agent):
        """Test agent node detecting need for search tool."""
        state = MessagesState(
            messages=[HumanMessage(content="find my project documentation")]
        )

        mock_response = AIMessage(content='{"tool": "search", "query": "project documentation"}')

        with patch.object(agent, '_needs_tool_call', return_value=True), \
             patch.object(agent, '_extract_tool_info', return_value={"tool": "search", "query": "project documentation"}):

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 3  # System + Human + AI response
            assert isinstance(result["messages"][-1], AIMessage)

            # Verify tool info was returned as JSON
            tool_data = json.loads(result["messages"][-1].content)
            assert tool_data["tool"] == "search"
            assert tool_data["query"] == "project documentation"

    @pytest.mark.asyncio
    async def test_agent_node_direct_response_without_tools(self, agent):
        """Test agent node providing direct response without tools."""
        state = MessagesState(
            messages=[HumanMessage(content="what is OneNote?")]
        )

        mock_response = AIMessage(content="OneNote is a digital note-taking application...")

        with patch.object(agent, '_needs_tool_call', return_value=False), \
             patch.object(agent, '_llm') as mock_llm:

            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 3  # System + Human + AI response
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with messages including system prompt
            expected_messages = [ANY, HumanMessage(content="what is OneNote?")]  # System + Human
            mock_llm.ainvoke.assert_called_once_with(expected_messages)

    @pytest.mark.asyncio
    async def test_agent_node_default_llm_response(self, agent):
        """Test agent node default case with LLM response."""
        # Create state with complex message structure
        state = MessagesState(
            messages=[
                SystemMessage(content="You are a helpful assistant"),
                HumanMessage(content="hello"),
                AIMessage(content="Hi there!")
            ]
        )

        mock_response = AIMessage(content="How can I help you today?")

        with patch.object(agent, '_llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 4
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with all existing messages (no system message added since one exists)
            expected_messages = [
                SystemMessage(content="You are a helpful assistant"),
                HumanMessage(content="hello"),
                AIMessage(content="Hi there!")
            ]
            mock_llm.ainvoke.assert_called_once_with(expected_messages)

    def test_needs_tool_call_recent_indicators(self, agent):
        """Test _needs_tool_call detects recent pages indicators."""
        test_cases = [
            "show me recent pages",
            "what are my recent notes",
            "display recent entries",
            "latest pages please"
        ]

        for query in test_cases:
            assert agent._needs_tool_call(query) is True

    def test_needs_tool_call_notebook_indicators(self, agent):
        """Test _needs_tool_call detects notebook indicators."""
        test_cases = [
            "list my notebooks",
            "show all notebooks",
            "what notebooks do I have",
            "display my notebooks"
        ]

        for query in test_cases:
            assert agent._needs_tool_call(query) is True

    def test_needs_tool_call_no_indicators(self, agent):
        """Test _needs_tool_call returns False for queries without indicators."""
        test_cases = [
            "what is OneNote?",
            "how does note-taking work?",
            "explain digital organization",
            "tell me about productivity"
        ]

        for query in test_cases:
            assert agent._needs_tool_call(query) is False

    def test_extract_tool_info_recent_pages(self, agent):
        """Test _extract_tool_info for recent pages queries."""
        query = "show me my recent pages"
        result = agent._extract_tool_info(query)

        assert result["tool"] == "get_recent_pages"
        assert result["limit"] == 10
        assert "query" not in result  # get_recent_pages doesn't use query

    def test_extract_tool_info_notebooks(self, agent):
        """Test _extract_tool_info for notebooks queries."""
        query = "list all my notebooks"
        result = agent._extract_tool_info(query)

        assert result["tool"] == "get_notebooks"
        assert "query" not in result  # get_notebooks doesn't use query

    def test_extract_tool_info_search_default(self, agent):
        """Test _extract_tool_info defaults to search for other queries."""
        query = "find my project notes"
        result = agent._extract_tool_info(query)

        assert result["tool"] == "search_onenote"
        assert result["query"] == "my project notes"  # Processed query

    def test_should_use_tools_end_condition(self, agent):
        """Test _should_use_tools with END condition."""
        state = MessagesState(messages=[
            AIMessage(content='{"condition": "END"}')
        ])

        result = agent._should_use_tools(state)
        assert result == "end"

    def test_should_use_tools_search_tool(self, agent):
        """Test _should_use_tools with search tool."""
        state = MessagesState(messages=[
            AIMessage(content='{"tool": "search_onenote", "query": "test"}')
        ])

        result = agent._should_use_tools(state)
        assert result == "search_onenote"

    def test_should_use_tools_recent_pages_tool(self, agent):
        """Test _should_use_tools with recent_pages tool."""
        state = MessagesState(messages=[
            AIMessage(content='{"tool": "get_recent_pages", "limit": 10}')
        ])

        result = agent._should_use_tools(state)
        assert result == "get_recent_pages"

    def test_should_use_tools_notebooks_tool(self, agent):
        """Test _should_use_tools with notebooks tool."""
        state = MessagesState(messages=[
            AIMessage(content='{"tool": "get_notebooks"}')
        ])

        result = agent._should_use_tools(state)
        assert result == "get_notebooks"

    def test_should_use_tools_invalid_json(self, agent):
        """Test _should_use_tools with invalid JSON."""
        state = MessagesState(messages=[
            AIMessage(content='invalid json content')
        ])

        result = agent._should_use_tools(state)
        assert result == "end"

    @pytest.mark.asyncio
    async def test_initialize_success_flow(self, agent):
        """Test successful initialization flow."""
        with patch.object(agent, 'search_tool') as mock_search_tool, \
             patch.object(agent, 'authenticator') as mock_auth:
            # Mock authentication success
            mock_auth.get_valid_token = AsyncMock(return_value="fake-token")
            mock_auth.validate_token = AsyncMock(return_value=True)
            mock_search_tool.ensure_authenticated = AsyncMock()

            # Should not raise any exception
            await agent.initialize()

            # Verify authentication was called
            mock_auth.get_valid_token.assert_called_once()
            mock_auth.validate_token.assert_called_once_with("fake-token")

    @pytest.mark.asyncio
    async def test_initialize_authentication_failure(self, agent):
        """Test initialization with authentication failure."""
        from src.auth.microsoft_auth import AuthenticationError

        with patch.object(agent, 'search_tool') as mock_search_tool, \
             patch.object(agent, 'authenticator') as mock_auth:
            # Mock authentication failure
            mock_auth.get_valid_token = AsyncMock(side_effect=AuthenticationError("Auth failed"))
            mock_search_tool.ensure_authenticated = AsyncMock()

            # Should raise AuthenticationError
            with pytest.raises(AuthenticationError, match="Auth failed"):
                await agent.initialize()

    @pytest.mark.asyncio
    async def test_initialize_general_exception(self, agent):
        """Test initialization with general exception."""
        with patch.object(agent, 'search_tool') as mock_search_tool, \
             patch.object(agent, 'authenticator') as mock_auth:
            # Mock general exception
            mock_auth.get_valid_token = AsyncMock(side_effect=Exception("Network error"))
            mock_search_tool.ensure_authenticated = AsyncMock()

            # Should raise the general exception
            with pytest.raises(Exception, match="Network error"):
                await agent.initialize()

    def test_get_conversation_starters(self, agent):
        """Test get_conversation_starters returns list of starters."""
        starters = agent.get_conversation_starters()

        assert isinstance(starters, list)
        assert len(starters) > 0
        assert all(isinstance(starter, str) for starter in starters)

    @pytest.mark.asyncio
    async def test_list_notebooks(self, agent):
        """Test list_notebooks functionality."""
        mock_notebooks = ["Work Notebook", "Personal Notebook"]

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.get_notebooks = AsyncMock(return_value=mock_notebooks)

            result = await agent.list_notebooks()

            assert result == mock_notebooks
            mock_search_tool.get_notebooks.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_recent_pages(self, agent):
        """Test get_recent_pages functionality."""
        mock_pages = [{"title": "Page 1"}, {"title": "Page 2"}]

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.get_recent_pages = AsyncMock(return_value=mock_pages)

            result = await agent.get_recent_pages()

            assert result == mock_pages
            mock_search_tool.get_recent_pages.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_stream_query_alias(self, agent):
        """Test stream_query is an alias for process_query."""
        async def mock_process_query(query):
            yield "chunk1"
            yield "chunk2"

        with patch.object(agent, 'process_query', side_effect=mock_process_query) as mock_process:
            result = []
            async for chunk in agent.stream_query("test query"):
                result.append(chunk)

            assert result == ["chunk1", "chunk2"]
            mock_process.assert_called_once_with("test query")


class TestOneNoteAgentToolHandling:
    """Test OneNote agent tool handling scenarios."""

    @pytest.fixture
    def agent(self):
        """Create agent with mocked dependencies."""
        settings = Mock()
        settings.openai_api_key = "test-key"
        settings.openai_model = "gpt-4"
        settings.openai_temperature = 0.7
        settings.max_search_results = 10

        with patch('src.agents.onenote_agent.get_settings', return_value=settings):
            agent = OneNoteAgent()
            agent.search_tool = Mock()
            return agent

    @pytest.mark.asyncio
    async def test_search_onenote_node_success(self, agent):
        """Test successful search OneNote node execution."""
        # Create mock search result
        from datetime import datetime

        from src.models.onenote import OneNotePage, SearchResult
        mock_page = OneNotePage(
            id="page1",
            title="Test Page",
            content="Test content",
            createdDateTime=datetime.now(),
            lastModifiedDateTime=datetime.now()
        )
        mock_search_result = SearchResult(
            pages=[mock_page],
            query="test query"
        )

        state = MessagesState(messages=[
            AIMessage(content='{"tool": "search", "query": "test query"}')
        ])

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.search_pages = AsyncMock(return_value=mock_search_result)

            result = await agent._search_onenote_node(state)

            # Verify tool message was added
            assert len(result["messages"]) == 2  # Original AI message + search result
            tool_message = result["messages"][-1]
            assert isinstance(tool_message, AIMessage)
            assert "Test Page" in tool_message.content

    @pytest.mark.asyncio
    async def test_search_onenote_node_no_results(self, agent):
        """Test search OneNote node with no results."""
        from langchain_core.messages import AIMessage

        from src.models.onenote import SearchResult

        state = MessagesState(messages=[
            AIMessage(content='{"tool": "search", "query": "nonexistent"}')
        ])

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.search_pages = AsyncMock(return_value=SearchResult(
                pages=[],
                query="nonexistent"
            ))

            result = await agent._search_onenote_node(state)

            # Verify NO_RESULTS message was added
            assert len(result["messages"]) == 2
            response_message = result["messages"][1]  # The new message added
            assert isinstance(response_message, AIMessage)
            assert response_message.content.startswith("NO_RESULTS:")

    @pytest.mark.asyncio
    async def test_search_onenote_node_search_error(self, agent):
        """Test search OneNote node with search error."""
        from langchain_core.messages import AIMessage

        from src.tools.onenote_search import OneNoteSearchError

        state = MessagesState(messages=[
            AIMessage(content='{"tool": "search", "query": "test"}')
        ])

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.search_pages = AsyncMock(side_effect=OneNoteSearchError("Search failed"))

            result = await agent._search_onenote_node(state)

            # Verify error message was added
            assert len(result["messages"]) == 2
            response_message = result["messages"][1]  # The new message added
            assert isinstance(response_message, AIMessage)
            assert "Search failed" in response_message.content

    @pytest.mark.asyncio
    async def test_search_onenote_node_general_exception(self, agent):
        """Test search OneNote node with general exception."""
        from langchain_core.messages import AIMessage

        state = MessagesState(messages=[
            AIMessage(content='{"tool": "search", "query": "test"}')
        ])

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.search_pages = AsyncMock(side_effect=Exception("Network error"))

            result = await agent._search_onenote_node(state)

            # Verify error message was added
            assert len(result["messages"]) == 2
            response_message = result["messages"][1]  # The new message added
            assert isinstance(response_message, AIMessage)
            assert "Network error" in response_message.content
