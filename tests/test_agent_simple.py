"""
Simple coverage tests for OneNote agent module.
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.agents.onenote_agent import OneNoteAgent


class TestAgentSimpleCoverage:
    """Simple tests to improve agent coverage."""

    def test_agent_initialization_basic(self):
        """Test basic agent initialization."""
        with patch('src.agents.onenote_agent.AzureChatOpenAI') as mock_llm:
            agent = OneNoteAgent()
            assert agent is not None
            assert hasattr(agent, 'llm')

    def test_agent_initialization_with_settings(self):
        """Test agent initialization with custom settings."""
        mock_settings = Mock()
        mock_settings.openai_api_key = "test_key"
        mock_settings.azure_openai_endpoint = "test_endpoint"
        mock_settings.azure_openai_deployment_name = "test_deployment"
        mock_settings.azure_openai_api_version = "test_version"

        with patch('src.agents.onenote_agent.AzureChatOpenAI') as mock_llm:
            agent = OneNoteAgent(settings=mock_settings)
            assert agent is not None

    def test_needs_tool_call_basic(self):
        """Test needs_tool_call method with basic scenarios."""
        with patch('src.agents.onenote_agent.AzureChatOpenAI'):
            agent = OneNoteAgent()

            # Test with query that needs search
            assert agent.needs_tool_call("search for project notes") == True
            assert agent.needs_tool_call("find my meeting notes") == True

            # Test with query that doesn't need search
            assert agent.needs_tool_call("hello") == False
            assert agent.needs_tool_call("what is onenote") == False

    def test_extract_tool_info_basic(self):
        """Test extract_tool_info method."""
        with patch('src.agents.onenote_agent.AzureChatOpenAI'):
            agent = OneNoteAgent()

            # Test search query extraction
            query = "search for project notes"
            tool_name, search_query = agent.extract_tool_info(query)
            assert tool_name == "search_pages"
            assert "project notes" in search_query

            # Test recent pages extraction
            query = "show me recent pages"
            tool_name, search_query = agent.extract_tool_info(query)
            assert tool_name == "get_recent_pages"

            # Test notebooks extraction
            query = "list my notebooks"
            tool_name, search_query = agent.extract_tool_info(query)
            assert tool_name == "get_notebooks"

    def test_extract_tool_info_notebooks_keywords(self):
        """Test extract_tool_info with various notebook keywords."""
        with patch('src.agents.onenote_agent.AzureChatOpenAI'):
            agent = OneNoteAgent()

            # Test different notebook keywords
            queries = [
                "show notebooks",
                "list notebooks",
                "get notebooks",
                "what notebooks do I have"
            ]

            for query in queries:
                tool_name, _ = agent.extract_tool_info(query)
                assert tool_name == "get_notebooks"

    def test_extract_tool_info_recent_pages_keywords(self):
        """Test extract_tool_info with various recent pages keywords."""
        with patch('src.agents.onenote_agent.AzureChatOpenAI'):
            agent = OneNoteAgent()

            # Test different recent pages keywords
            queries = [
                "recent pages",
                "latest pages",
                "show recent",
                "my recent pages"
            ]

            for query in queries:
                tool_name, _ = agent.extract_tool_info(query)
                assert tool_name == "get_recent_pages"
