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
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'):
            agent = OneNoteAgent()
            assert agent is not None
            # Note: llm is lazy-loaded, so we can't test it directly without triggering the load

    def test_agent_initialization_with_settings(self):
        """Test agent initialization with custom settings."""
        mock_settings = Mock()
        mock_settings.openai_api_key = "test_key"
        mock_settings.azure_openai_endpoint = "test_endpoint"
        mock_settings.azure_openai_deployment_name = "test_deployment"
        mock_settings.azure_openai_api_version = "test_version"

        with patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'):
            agent = OneNoteAgent(settings=mock_settings)
            assert agent is not None
            assert agent.settings == mock_settings

    def test_needs_tool_call_basic(self):
        """Test needs_tool_call method with basic scenarios."""
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'):
            agent = OneNoteAgent()

            # Test with query that needs search
            assert agent._needs_tool_call("search for project notes") == True
            assert agent._needs_tool_call("find my meeting notes") == True

            # Test with query that doesn't need search
            assert agent._needs_tool_call("hello") == False
            assert agent._needs_tool_call("what is onenote") == False

    def test_extract_tool_info_basic(self):
        """Test extract_tool_info method."""
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'):
            agent = OneNoteAgent()

            # Test search query extraction
            query = "search for project notes"
            result = agent._extract_tool_info(query)
            assert result["tool"] == "search_onenote"
            assert "project notes" in result["query"]

            # Test recent pages extraction
            query = "show me recent pages"
            result = agent._extract_tool_info(query)
            assert result["tool"] == "get_recent_pages"

            # Test notebooks extraction
            query = "list my notebooks"
            result = agent._extract_tool_info(query)
            assert result["tool"] == "get_notebooks"

    def test_extract_tool_info_notebooks_keywords(self):
        """Test extract_tool_info with various notebook keywords."""
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'):
            agent = OneNoteAgent()

            # Test different notebook keywords
            queries = [
                "show notebooks",
                "list notebooks",
                "get notebooks",
                "what notebooks do I have"
            ]

            for query in queries:
                result = agent._extract_tool_info(query)
                assert result["tool"] == "get_notebooks"

    def test_extract_tool_info_recent_pages_keywords(self):
        """Test extract_tool_info with various recent pages keywords."""
        with patch('src.agents.onenote_agent.get_settings'), \
             patch('src.agents.onenote_agent.MicrosoftAuthenticator'), \
             patch('src.agents.onenote_agent.OneNoteSearchTool'), \
             patch('src.agents.onenote_agent.OneNoteContentProcessor'):
            agent = OneNoteAgent()

            # Test different recent pages keywords
            queries = [
                "recent pages",
                "latest pages",
                "show recent",
                "my recent pages"
            ]

            for query in queries:
                result = agent._extract_tool_info(query)
                assert result["tool"] == "get_recent_pages"
