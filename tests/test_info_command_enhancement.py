"""
Test cases for the enhanced --info command functionality.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.auth.microsoft_auth import MicrosoftAuthenticator
from src.main import show_system_info


class TestInfoCommandEnhancement:
    """Test cases for the enhanced --info command with user information."""

    def test_get_user_profile_method_exists(self):
        """Test that the get_user_profile method exists on MicrosoftAuthenticator."""
        authenticator = MicrosoftAuthenticator()
        assert hasattr(authenticator, 'get_user_profile')
        assert callable(getattr(authenticator, 'get_user_profile'))

    @pytest.mark.asyncio
    async def test_get_user_profile_not_authenticated(self):
        """Test get_user_profile returns None when user is not authenticated."""
        authenticator = MicrosoftAuthenticator()

        with patch.object(authenticator, 'is_authenticated', return_value=False):
            result = await authenticator.get_user_profile()
            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_profile_success(self):
        """Test get_user_profile returns user data when authenticated."""
        authenticator = MicrosoftAuthenticator()
        authenticator._access_token = "fake_token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "displayName": "Test User",
            "userPrincipalName": "test@example.com",
            "id": "12345"
        }

        with patch.object(authenticator, 'is_authenticated', return_value=True), \
             patch('httpx.AsyncClient') as mock_client:

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await authenticator.get_user_profile()

            assert result is not None
            assert result['displayName'] == "Test User"
            assert result['userPrincipalName'] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_profile_api_error(self):
        """Test get_user_profile handles API errors gracefully."""
        authenticator = MicrosoftAuthenticator()
        authenticator._access_token = "fake_token"

        mock_response = Mock()
        mock_response.status_code = 401

        with patch.object(authenticator, 'is_authenticated', return_value=True), \
             patch('httpx.AsyncClient') as mock_client:

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await authenticator.get_user_profile()
            assert result is None

    def test_show_system_info_includes_user_section(self):
        """Test that show_system_info includes user information section."""
        with patch('src.main.MicrosoftAuthenticator') as mock_auth_class, \
             patch('src.main.console') as mock_console, \
             patch('asyncio.new_event_loop') as mock_loop, \
             patch('asyncio.set_event_loop'), \
             patch('src.main.Panel') as mock_panel, \
             patch('src.main.Markdown') as mock_markdown:

            # Setup mocks
            mock_auth = Mock()
            mock_auth.is_authenticated.return_value = False
            mock_auth_class.return_value = mock_auth

            mock_event_loop = Mock()
            mock_loop.return_value = mock_event_loop

            # Call the function
            show_system_info()

            # Verify that authentication check was attempted
            mock_auth_class.assert_called_once()
            mock_auth.is_authenticated.assert_called_once()

            # Verify console.print was called (meaning the function completed)
            mock_console.print.assert_called_once()

    def test_show_system_info_handles_auth_errors(self):
        """Test that show_system_info handles authentication errors gracefully."""
        with patch('src.main.MicrosoftAuthenticator') as mock_auth_class, \
             patch('src.main.console') as mock_console, \
             patch('asyncio.new_event_loop') as mock_loop, \
             patch('asyncio.set_event_loop'), \
             patch('src.main.Panel') as mock_panel, \
             patch('src.main.Markdown') as mock_markdown:

            # Setup mocks to raise exception
            mock_auth_class.side_effect = Exception("Auth error")
            mock_event_loop = Mock()
            mock_loop.return_value = mock_event_loop

            # Call the function - should not raise exception
            show_system_info()

            # Verify console.print was still called (error was handled)
            mock_console.print.assert_called_once()
