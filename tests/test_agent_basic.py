"""
Simple integration test for OneNote Agent with local search.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.onenote_agent import OneNoteAgent


class TestAgentLocalSearchBasic:
    """Basic tests for agent local search integration."""

    async def test_agent_basic_functionality(self):
        """Test that agent can be created and initialized without errors."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.enable_hybrid_search = True
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4"
        mock_settings.openai_temperature = 0.1
        
        # Create agent
        agent = OneNoteAgent(mock_settings)
        
        # Mock authenticator
        agent.authenticator.get_valid_token = AsyncMock(return_value="mock-token")
        agent.authenticator.validate_token = AsyncMock(return_value=True)
        
        # Mock cache manager with no cached content
        agent._cache_manager = MagicMock()
        agent._cache_manager.get_all_cached_pages = AsyncMock(return_value=[])
        
        # Initialize agent
        await agent.initialize()
        
        # Verify local search was not initialized (no cached content)
        assert agent._local_search_available is False
        
        # Verify cache status
        status = await agent.get_cache_status()
        assert status["local_search_available"] is False
        assert status["search_mode"] == "api"


if __name__ == "__main__":
    asyncio.run(TestAgentLocalSearchBasic().test_agent_basic_functionality())
    print("✅ Basic agent functionality test passed!")
