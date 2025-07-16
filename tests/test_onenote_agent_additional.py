"""
Additional tests for OneNote agent module to improve coverage.

These tests focus on covering the missing lines identified in the coverage report.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agents.onenote_agent import OneNoteAgent
from src.models.responses import AgentState


class TestOneNoteAgentAdditional:
    """Additional tests for OneNoteAgent to improve coverage."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock()
        settings.openai_api_key = "test-key"
        settings.openai_model = "gpt-4"
        settings.max_search_results = 10
        settings.azure_client_id = "test-client-id"
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
        # Create state with tool response indicating no results
        tool_message = ToolMessage(
            content="NO_RESULTS: No pages found matching your search criteria",
            tool_call_id="test_tool_call"
        )

        state = AgentState(
            messages=[
                HumanMessage(content="search for project notes"),
                tool_message
            ]
        )

        # Mock the LLM response
        mock_response = AIMessage(content="I couldn't find any pages matching your search.")

        with patch.object(agent, 'llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            # Verify the response was generated for no results
            assert len(result["messages"]) == 3
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with no results prompt
            call_args = mock_llm.ainvoke.call_args[0][0]
            assert len(call_args) == 2
            assert isinstance(call_args[0], SystemMessage)
            assert isinstance(call_args[1], HumanMessage)

    @pytest.mark.asyncio
    async def test_agent_node_with_recent_pages_tool_response(self, agent):
        """Test agent node handling tool response with RECENT_PAGES prefix."""
        tool_message = ToolMessage(
            content="RECENT_PAGES:\nPage 1: Meeting Notes\nPage 2: Project Ideas",
            tool_call_id="test_tool_call"
        )

        state = AgentState(
            messages=[
                HumanMessage(content="show me recent pages"),
                tool_message
            ]
        )

        mock_response = AIMessage(content="Here are your recent pages...")

        with patch.object(agent, 'llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 3
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with recent pages content
            call_args = mock_llm.ainvoke.call_args[0][0]
            prompt_content = call_args[1].content
            assert "Page 1: Meeting Notes" in prompt_content
            assert "Page 2: Project Ideas" in prompt_content

    @pytest.mark.asyncio
    async def test_agent_node_with_notebooks_tool_response(self, agent):
        """Test agent node handling tool response with NOTEBOOKS prefix."""
        tool_message = ToolMessage(
            content="NOTEBOOKS:\nWork Notebook\nPersonal Notebook\nProject Notebook",
            tool_call_id="test_tool_call"
        )

        state = AgentState(
            messages=[
                HumanMessage(content="list my notebooks"),
                tool_message
            ]
        )

        mock_response = AIMessage(content="Here are your OneNote notebooks...")

        with patch.object(agent, 'llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 3
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with notebooks content
            call_args = mock_llm.ainvoke.call_args[0][0]
            prompt_content = call_args[1].content
            assert "Work Notebook" in prompt_content
            assert "Personal Notebook" in prompt_content

    @pytest.mark.asyncio
    async def test_agent_node_with_error_tool_response(self, agent):
        """Test agent node handling tool response with error content."""
        tool_message = ToolMessage(
            content="ERROR: Failed to connect to OneNote API",
            tool_call_id="test_tool_call"
        )

        state = AgentState(
            messages=[
                HumanMessage(content="search for notes"),
                tool_message
            ]
        )

        result = await agent._agent_node(state)

        # Verify error response was generated directly
        assert len(result["messages"]) == 3
        error_response = result["messages"][-1]
        assert isinstance(error_response, AIMessage)
        assert "Failed to connect to OneNote API" in error_response.content

    @pytest.mark.asyncio
    async def test_agent_node_needs_tool_call_for_search(self, agent):
        """Test agent node detecting need for search tool."""
        state = AgentState(
            messages=[HumanMessage(content="find my project documentation")]
        )

        mock_response = AIMessage(content='{"tool": "search", "query": "project documentation"}')

        with patch.object(agent, '_needs_tool_call', return_value=True), \
             patch.object(agent, '_extract_tool_info', return_value={"tool": "search", "query": "project documentation"}):

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 2
            assert isinstance(result["messages"][-1], AIMessage)

            # Verify tool info was returned as JSON
            tool_data = json.loads(result["messages"][-1].content)
            assert tool_data["tool"] == "search"
            assert tool_data["query"] == "project documentation"

    @pytest.mark.asyncio
    async def test_agent_node_direct_response_without_tools(self, agent):
        """Test agent node providing direct response without tools."""
        state = AgentState(
            messages=[HumanMessage(content="what is OneNote?")]
        )

        mock_response = AIMessage(content="OneNote is a digital note-taking application...")

        with patch.object(agent, '_needs_tool_call', return_value=False), \
             patch.object(agent, 'llm') as mock_llm:

            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 2
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with original messages
            mock_llm.ainvoke.assert_called_once_with([HumanMessage(content="what is OneNote?")])

    @pytest.mark.asyncio
    async def test_agent_node_default_llm_response(self, agent):
        """Test agent node default case with LLM response."""
        # Create state with complex message structure
        state = AgentState(
            messages=[
                SystemMessage(content="You are a helpful assistant"),
                HumanMessage(content="hello"),
                AIMessage(content="Hi there!")
            ]
        )

        mock_response = AIMessage(content="How can I help you today?")

        with patch.object(agent, 'llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)

            result = await agent._agent_node(state)

            assert len(result["messages"]) == 4
            assert result["messages"][-1] == mock_response

            # Verify LLM was called with all existing messages
            mock_llm.ainvoke.assert_called_once_with(state.messages)

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

        assert result["tool"] == "recent_pages"
        assert "query" in result

    def test_extract_tool_info_notebooks(self, agent):
        """Test _extract_tool_info for notebooks queries."""
        query = "list all my notebooks"
        result = agent._extract_tool_info(query)

        assert result["tool"] == "notebooks"
        assert "query" in result

    def test_extract_tool_info_search_default(self, agent):
        """Test _extract_tool_info defaults to search for other queries."""
        query = "find my project notes"
        result = agent._extract_tool_info(query)

        assert result["tool"] == "search"
        assert result["query"] == "find my project notes"

    def test_should_use_tools_end_condition(self, agent):
        """Test _should_use_tools with END condition."""
        state = AgentState(messages=[])
        state.last_ai_response = '{"condition": "END"}'

        result = agent._should_use_tools(state)
        assert result == "end"

    def test_should_use_tools_search_tool(self, agent):
        """Test _should_use_tools with search tool."""
        state = AgentState(messages=[])
        state.last_ai_response = '{"tool": "search", "query": "test"}'

        result = agent._should_use_tools(state)
        assert result == "search_onenote"

    def test_should_use_tools_recent_pages_tool(self, agent):
        """Test _should_use_tools with recent_pages tool."""
        state = AgentState(messages=[])
        state.last_ai_response = '{"tool": "recent_pages"}'

        result = agent._should_use_tools(state)
        assert result == "search_onenote"

    def test_should_use_tools_notebooks_tool(self, agent):
        """Test _should_use_tools with notebooks tool."""
        state = AgentState(messages=[])
        state.last_ai_response = '{"tool": "notebooks"}'

        result = agent._should_use_tools(state)
        assert result == "search_onenote"

    def test_should_use_tools_invalid_json(self, agent):
        """Test _should_use_tools with invalid JSON."""
        state = AgentState(messages=[])
        state.last_ai_response = 'invalid json content'

        result = agent._should_use_tools(state)
        assert result == "end"

    @pytest.mark.asyncio
    async def test_initialize_success_flow(self, agent):
        """Test successful initialization flow."""
        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.ensure_authenticated = AsyncMock()

            success = await agent.initialize()

            assert success is True
            mock_search_tool.ensure_authenticated.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_authentication_failure(self, agent):
        """Test initialization with authentication failure."""
        from src.auth.microsoft_auth import AuthenticationError

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.ensure_authenticated = AsyncMock(side_effect=AuthenticationError("Auth failed"))

            success = await agent.initialize()

            assert success is False

    @pytest.mark.asyncio
    async def test_initialize_general_exception(self, agent):
        """Test initialization with general exception."""
        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.ensure_authenticated = AsyncMock(side_effect=Exception("Network error"))

            success = await agent.initialize()

            assert success is False

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
            mock_search_tool.get_recent_pages.assert_called_once_with(limit=10)

    @pytest.mark.asyncio
    async def test_stream_query_alias(self, agent):
        """Test stream_query is an alias for process_query."""
        with patch.object(agent, 'process_query', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = ["chunk1", "chunk2"]

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
        settings.max_search_results = 10

        with patch('src.agents.onenote_agent.get_settings', return_value=settings):
            agent = OneNoteAgent()
            agent.search_tool = Mock()
            return agent

    @pytest.mark.asyncio
    async def test_search_onenote_node_success(self, agent):
        """Test successful search OneNote node execution."""
        from src.models.onenote import OneNotePage, SearchResult

        # Create mock search result
        mock_page = OneNotePage(
            id="page1",
            title="Test Page",
            content="Test content"
        )
        mock_search_result = SearchResult(pages=[mock_page])

        state = AgentState(messages=[])
        state.last_ai_response = '{"tool": "search", "query": "test query"}'

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.search_pages = AsyncMock(return_value=mock_search_result)

            result = await agent._search_onenote_node(state)

            # Verify tool message was added
            assert len(result["messages"]) == 1
            tool_message = result["messages"][0]
            assert isinstance(tool_message, ToolMessage)
            assert "Test Page" in tool_message.content

    @pytest.mark.asyncio
    async def test_search_onenote_node_no_results(self, agent):
        """Test search OneNote node with no results."""
        from src.models.onenote import SearchResult

        state = AgentState(messages=[])
        state.last_ai_response = '{"tool": "search", "query": "nonexistent"}'

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.search_pages = AsyncMock(return_value=SearchResult(pages=[]))

            result = await agent._search_onenote_node(state)

            # Verify NO_RESULTS message was added
            assert len(result["messages"]) == 1
            tool_message = result["messages"][0]
            assert isinstance(tool_message, ToolMessage)
            assert tool_message.content.startswith("NO_RESULTS:")

    @pytest.mark.asyncio
    async def test_search_onenote_node_search_error(self, agent):
        """Test search OneNote node with search error."""
        from src.tools.onenote_search import OneNoteSearchError

        state = AgentState(messages=[])
        state.last_ai_response = '{"tool": "search", "query": "test"}'

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.search_pages = AsyncMock(side_effect=OneNoteSearchError("Search failed"))

            result = await agent._search_onenote_node(state)

            # Verify error message was added
            assert len(result["messages"]) == 1
            tool_message = result["messages"][0]
            assert isinstance(tool_message, ToolMessage)
            assert "Search failed" in tool_message.content

    @pytest.mark.asyncio
    async def test_search_onenote_node_general_exception(self, agent):
        """Test search OneNote node with general exception."""
        state = AgentState(messages=[])
        state.last_ai_response = '{"tool": "search", "query": "test"}'

        with patch.object(agent, 'search_tool') as mock_search_tool:
            mock_search_tool.search_pages = AsyncMock(side_effect=Exception("Network error"))

            result = await agent._search_onenote_node(state)

            # Verify error message was added
            assert len(result["messages"]) == 1
            tool_message = result["messages"][0]
            assert isinstance(tool_message, ToolMessage)
            assert "Network error" in tool_message.content
