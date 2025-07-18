"""
Tests for src.agents.onenote_agent module.

These tests cover the OneNote LangGraph agent functionality including
initialization, tool nodes, routing logic, and streaming query processing.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.onenote_agent import MessagesState, OneNoteAgent
from src.models.onenote import OneNotePage, SearchResult
from src.models.responses import OneNoteSearchResponse, StreamingChunk


@pytest.mark.agent
@pytest.mark.unit
class TestOneNoteAgent:
    """Test OneNote agent initialization and core functionality."""

    @pytest.mark.fast
    @pytest.mark.mock_heavy
    @patch('src.agents.onenote_agent.get_settings')
    @patch('src.agents.onenote_agent.MicrosoftAuthenticator')
    @patch('src.agents.onenote_agent.OneNoteSearchTool')
    @patch('src.agents.onenote_agent.OneNoteContentProcessor')
    @patch('langchain_openai.ChatOpenAI')  # Patch where it's actually imported
    def test_init(self, mock_chat_openai, mock_content_processor,
                  mock_search_tool, mock_authenticator, mock_get_settings):
        """Test OneNote agent initialization."""
        # Setup mocks
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4"
        mock_settings.openai_temperature = 0.7
        mock_get_settings.return_value = mock_settings

        # Initialize agent
        agent = OneNoteAgent()

        # Verify initialization
        assert agent.settings == mock_settings
        mock_authenticator.assert_called_once_with(mock_settings)
        mock_search_tool.assert_called_once()
        mock_content_processor.assert_called_once()
        # Note: ChatOpenAI is lazy-loaded, so it won't be called during __init__

    @patch('src.agents.onenote_agent.get_settings')
    def test_init_with_custom_settings(self, mock_get_settings):
        """Test OneNote agent initialization with custom settings."""
        custom_settings = MagicMock()

        with patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'):

            agent = OneNoteAgent(settings=custom_settings)

            # Should use custom settings, not call get_settings
            assert agent.settings == custom_settings
            mock_get_settings.assert_not_called()

    def test_create_agent_graph(self):
        """Test LangGraph workflow creation."""
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'), \
             patch('langgraph.graph.StateGraph'):

            agent = OneNoteAgent()

            # Verify graph property works (lazy initialization)
            assert agent.graph is not None


class TestAgentNode:
    """Test the main agent node functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'):

            self.agent = OneNoteAgent()
            self.agent._llm = AsyncMock()  # Mock the private attribute directly

    async def test_agent_node_with_system_message(self):
        """Test agent node with existing system message."""
        # Setup state
        state = MessagesState(messages=[
            SystemMessage(content="System prompt"),
            HumanMessage(content="Test query")
        ])

        # Mock LLM response
        mock_response = AIMessage(content="Test response")
        self.agent.llm.ainvoke.return_value = mock_response

        # Test agent node
        result = await self.agent._agent_node(state)

        # Verify result
        assert len(result["messages"]) == 3
        assert result["messages"][-1] == mock_response

    async def test_agent_node_adds_system_message(self):
        """Test agent node adds system message when missing."""
        # Setup state without system message
        state = MessagesState(messages=[
            HumanMessage(content="Test query")
        ])

        # Mock LLM response
        mock_response = AIMessage(content="Test response")
        self.agent.llm.ainvoke.return_value = mock_response

        with patch('src.agents.onenote_agent.get_system_prompt', return_value="System prompt"):
            result = await self.agent._agent_node(state)

        # Verify system message was added
        assert len(result["messages"]) == 3
        assert isinstance(result["messages"][0], SystemMessage)

    async def test_agent_node_with_tool_results(self):
        """Test agent node processing tool results."""
        # Setup state with tool results
        state = MessagesState(messages=[
            HumanMessage(content="Search for test"),
            AIMessage(content="SEARCH_RESULTS:\nTest results here")
        ])

        # Mock LLM response
        mock_response = AIMessage(content="Final response")
        self.agent.llm.ainvoke.return_value = mock_response

        with patch('src.agents.onenote_agent.get_system_prompt', return_value="System"), \
             patch('src.agents.onenote_agent.get_answer_generation_prompt', return_value="Prompt"):

            result = await self.agent._agent_node(state)

        # Verify final response (system message + original messages + LLM response)
        assert len(result["messages"]) == 4  # SystemMessage + 2 original + 1 LLM response
        assert result["messages"][-1] == mock_response

    async def test_agent_node_no_results(self):
        """Test agent node with no results."""
        # Setup state with no results
        state = MessagesState(messages=[
            HumanMessage(content="Search for test"),
            AIMessage(content="NO_RESULTS: No pages found")
        ])

        # Mock LLM response
        mock_response = AIMessage(content="No results response")
        self.agent.llm.ainvoke.return_value = mock_response

        with patch('src.agents.onenote_agent.get_system_prompt', return_value="System"), \
             patch('src.agents.onenote_agent.get_no_results_prompt', return_value="No results prompt"):

            result = await self.agent._agent_node(state)

        # Verify response (system message + original messages + LLM response)
        assert len(result["messages"]) == 4  # SystemMessage + 2 original + 1 LLM response
        assert result["messages"][-1] == mock_response

    async def test_agent_node_needs_tool(self):
        """Test agent node detecting need for tool call."""
        # Setup state with search query
        state = MessagesState(messages=[
            HumanMessage(content="Search for project notes")
        ])

        # Test tool detection
        result = await self.agent._agent_node(state)

        # Should return tool information (system message + original message + LLM response)
        assert len(result["messages"]) == 3  # SystemMessage + 1 original + 1 LLM response
        tool_message = result["messages"][-1]
        assert isinstance(tool_message, AIMessage)
        assert tool_message.content.startswith("{")

    async def test_agent_node_exception_handling(self):
        """Test agent node exception handling."""
        # Setup state
        state = MessagesState(messages=[
            HumanMessage(content="Test query")
        ])

        # Mock LLM to raise exception
        self.agent.llm.ainvoke.side_effect = Exception("Test error")

        # Test exception handling
        result = await self.agent._agent_node(state)

        # Should return error message (system message + original message + error response)
        assert len(result["messages"]) == 3  # SystemMessage + 1 original + 1 error response
        error_message = result["messages"][-1]
        assert isinstance(error_message, AIMessage)
        assert "error" in error_message.content.lower()


class TestSearchOneNoteNode:
    """Test OneNote search tool node."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'), \
             patch('src.agents.onenote_agent.ChatOpenAI'):

            self.agent = OneNoteAgent()
            self.agent.search_tool = AsyncMock()
            self.agent.content_processor = MagicMock()

    async def test_search_onenote_node_success(self):
        """Test successful OneNote search."""
        # Setup state
        tool_info = {"query": "test query", "max_results": 5}
        state = MessagesState(messages=[
            AIMessage(content=json.dumps(tool_info))
        ])

        # Mock search results
        mock_page = OneNotePage(
            id="page1",
            title="Test Page",
            content="Test content",
            created_date_time=datetime.now(),
            last_modified_date_time=datetime.now(),
            links={}
        )
        mock_search_result = SearchResult(
            pages=[mock_page],
            query="test query",
            total_count=1,
            execution_time=0.5,
            api_calls_made=1
        )

        self.agent.search_tool.search_pages.return_value = mock_search_result
        self.agent.content_processor.format_search_results_for_ai.return_value = "Formatted results"

        with patch('src.agents.onenote_agent.get_answer_generation_prompt', return_value="Answer prompt"):
            result = await self.agent._search_onenote_node(state)

        # Verify result
        assert len(result["messages"]) == 2
        response_message = result["messages"][-1]
        assert isinstance(response_message, AIMessage)
        assert response_message.content.startswith("SEARCH_RESULTS:")

    async def test_search_onenote_node_no_results(self):
        """Test OneNote search with no results."""
        # Setup state
        tool_info = {"query": "test query", "max_results": 5}
        state = MessagesState(messages=[
            AIMessage(content=json.dumps(tool_info))
        ])

        # Mock empty search results
        mock_search_result = SearchResult(
            pages=[],
            query="test query",
            total_count=0,
            execution_time=0.5,
            api_calls_made=1
        )

        self.agent.search_tool.search_pages.return_value = mock_search_result

        with patch('src.agents.onenote_agent.get_no_results_prompt', return_value="No results prompt"):
            result = await self.agent._search_onenote_node(state)

        # Verify result
        assert len(result["messages"]) == 2
        response_message = result["messages"][-1]
        assert isinstance(response_message, AIMessage)
        assert response_message.content.startswith("NO_RESULTS:")

    async def test_search_onenote_node_search_error(self):
        """Test OneNote search with search error."""
        # Setup state
        tool_info = {"query": "test query", "max_results": 5}
        state = MessagesState(messages=[
            AIMessage(content=json.dumps(tool_info))
        ])

        # Mock search error
        from src.tools.onenote_search import OneNoteSearchError
        self.agent.search_tool.search_pages.side_effect = OneNoteSearchError("Search failed")

        result = await self.agent._search_onenote_node(state)

        # Verify error result
        assert len(result["messages"]) == 2
        response_message = result["messages"][-1]
        assert isinstance(response_message, AIMessage)
        assert response_message.content.startswith("SEARCH_ERROR:")

    async def test_search_onenote_node_general_exception(self):
        """Test OneNote search with general exception."""
        # Setup state
        tool_info = {"query": "test query", "max_results": 5}
        state = MessagesState(messages=[
            AIMessage(content=json.dumps(tool_info))
        ])

        # Mock general exception
        self.agent.search_tool.search_pages.side_effect = Exception("Unexpected error")

        result = await self.agent._search_onenote_node(state)

        # Verify error result
        assert len(result["messages"]) == 2
        response_message = result["messages"][-1]
        assert isinstance(response_message, AIMessage)
        assert response_message.content.startswith("SEARCH_ERROR:")


class TestUtilityMethods:
    """Test utility methods for tool detection and routing."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'), \
             patch('src.agents.onenote_agent.ChatOpenAI'):

            self.agent = OneNoteAgent()

    def test_needs_tool_call_search_indicators(self):
        """Test tool call detection for search indicators."""
        test_cases = [
            "search for project notes",
            "find my meeting notes",
            "show me notes about vacation",
            "what did I write about work"
        ]

        for query in test_cases:
            assert self.agent._needs_tool_call(query) is True

    def test_needs_tool_call_recent_indicators(self):
        """Test tool call detection for recent indicators."""
        test_cases = [
            "show me recent notes",
            "what have I written lately",
            "latest pages",
            "notes from yesterday"
        ]

        for query in test_cases:
            assert self.agent._needs_tool_call(query) is True

    def test_needs_tool_call_notebook_indicators(self):
        """Test tool call detection for notebook indicators."""
        test_cases = [
            "list my notebooks",
            "show me all notebooks",
            "what notebooks do I have"
        ]

        for query in test_cases:
            assert self.agent._needs_tool_call(query) is True

    def test_needs_tool_call_thought_indicators(self):
        """Test tool call detection for thought/opinion indicators."""
        test_cases = [
            "What were my thoughts about Robo-me?",
            "What did I think about the project?",
            "My thoughts on artificial intelligence",
            "What was my opinion about the meeting?",
            "thoughts about the new feature",
            "ideas about machine learning"
        ]

        for query in test_cases:
            assert self.agent._needs_tool_call(query) is True

    def test_needs_tool_call_no_indicators(self):
        """Test tool call detection when no indicators present."""
        test_cases = [
            "hello",
            "how are you",
            "what is your name",
            "explain something to me"
        ]

        for query in test_cases:
            assert self.agent._needs_tool_call(query) is False

    def test_extract_tool_info_recent(self):
        """Test tool info extraction for recent queries."""
        query = "show me recent notes"
        result = self.agent._extract_tool_info(query)

        assert result["tool"] == "get_recent_pages"
        assert result["limit"] == 10

    def test_extract_tool_info_notebooks(self):
        """Test tool info extraction for notebook queries."""
        query = "list my notebooks"
        result = self.agent._extract_tool_info(query)

        assert result["tool"] == "get_notebooks"

    def test_extract_tool_info_search(self):
        """Test tool info extraction for search queries."""
        query = "search for project planning notes"
        result = self.agent._extract_tool_info(query)

        assert result["tool"] == "search_onenote"
        assert "query" in result
        assert result["max_results"] == 10

    def test_should_use_tools_end_condition(self):
        """Test tool routing end condition."""
        # State with tool results and regular AI response
        state = MessagesState(messages=[
            HumanMessage(content="Search for test"),
            AIMessage(content="SEARCH_RESULTS: Results here"),
            AIMessage(content="Here are your search results...")
        ])

        result = self.agent._should_use_tools(state)
        assert result == "end"

    def test_should_use_tools_search_tool(self):
        """Test tool routing for search tool."""
        # State with tool instruction for search
        tool_info = {"tool": "search_onenote", "query": "test"}
        state = MessagesState(messages=[
            HumanMessage(content="Search for test"),
            AIMessage(content=json.dumps(tool_info))
        ])

        result = self.agent._should_use_tools(state)
        assert result == "search_onenote"

    def test_should_use_tools_recent_pages_tool(self):
        """Test tool routing for recent pages tool."""
        # State with tool instruction for recent pages
        tool_info = {"tool": "get_recent_pages", "limit": 10}
        state = MessagesState(messages=[
            HumanMessage(content="Show recent pages"),
            AIMessage(content=json.dumps(tool_info))
        ])

        result = self.agent._should_use_tools(state)
        assert result == "get_recent_pages"

    def test_should_use_tools_notebooks_tool(self):
        """Test tool routing for notebooks tool."""
        # State with tool instruction for notebooks
        tool_info = {"tool": "get_notebooks"}
        state = MessagesState(messages=[
            HumanMessage(content="List notebooks"),
            AIMessage(content=json.dumps(tool_info))
        ])

        result = self.agent._should_use_tools(state)
        assert result == "get_notebooks"

    def test_should_use_tools_invalid_json(self):
        """Test tool routing with invalid JSON."""
        # State with invalid JSON
        state = MessagesState(messages=[
            HumanMessage(content="Test"),
            AIMessage(content="invalid json {")
        ])

        result = self.agent._should_use_tools(state)
        assert result == "end"


class TestPublicMethods:
    """Test public methods of OneNote agent."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'), \
             patch('src.agents.onenote_agent.ChatOpenAI'):

            self.agent = OneNoteAgent()
            self.agent.authenticator = AsyncMock()
            self.agent.search_tool = AsyncMock()
            self.agent.llm = AsyncMock()

    async def test_initialize_success(self):
        """Test successful agent initialization."""
        # Mock successful authentication
        self.agent.authenticator.get_valid_token.return_value = "token"
        self.agent.authenticator.validate_token.return_value = True

        # Should not raise exception
        await self.agent.initialize()

        self.agent.authenticator.get_valid_token.assert_called_once()
        self.agent.authenticator.validate_token.assert_called_once()

    async def test_initialize_authentication_failure(self):
        """Test agent initialization with authentication failure."""
        # Mock failed authentication
        self.agent.authenticator.get_valid_token.return_value = "token"
        self.agent.authenticator.validate_token.return_value = False

        # Should raise AuthenticationError
        from src.auth.microsoft_auth import AuthenticationError
        with pytest.raises(AuthenticationError):
            await self.agent.initialize()

    async def test_initialize_exception(self):
        """Test agent initialization with exception."""
        # Mock exception during initialization
        self.agent.authenticator.get_valid_token.side_effect = Exception("Test error")

        # Should raise exception
        with pytest.raises(Exception):
            await self.agent.initialize()

    def test_get_conversation_starters(self):
        """Test getting conversation starters."""
        with patch('src.agents.prompts.CONVERSATION_STARTERS', ["Test starter"]):
            starters = self.agent.get_conversation_starters()
            assert isinstance(starters, list)
            assert len(starters) > 0

    async def test_list_notebooks(self):
        """Test listing notebooks."""
        # Mock the search tool directly
        mock_notebooks = [{"id": "1", "name": "Test Notebook"}]
        self.agent.search_tool.get_notebooks = AsyncMock(return_value=mock_notebooks)

        result = await self.agent.list_notebooks()

        # Should return list from search tool
        assert isinstance(result, list)
        assert result == mock_notebooks

    async def test_get_recent_pages(self):
        """Test getting recent pages."""
        # Mock the search tool directly
        from datetime import datetime

        from src.models.onenote import OneNotePage
        mock_page = OneNotePage(
            id="test-id",
            title="Test Page",
            content="Test content",
            createdDateTime=datetime.fromisoformat("2023-01-01T00:00:00+00:00"),
            lastModifiedDateTime=datetime.fromisoformat("2023-01-01T00:00:00+00:00"),
            links={}
        )
        mock_pages = [mock_page]
        self.agent.search_tool.get_recent_pages = AsyncMock(return_value=mock_pages)

        result = await self.agent.get_recent_pages(5)

        # Should return list from search tool
        assert isinstance(result, list)
        assert result == mock_pages

    async def test_stream_query_alias(self):
        """Test stream_query alias method."""
        # Mock process_query as an async generator that accepts query parameter
        async def mock_generator(query: str):
            yield StreamingChunk.text_chunk("Test")

        # Replace the method directly
        self.agent.process_query = mock_generator

        # Test alias
        chunks = []
        async for chunk in self.agent.stream_query("test"):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].type == "text"
