"""
Simple test for authentication module to improve coverage.
"""
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from src.auth.microsoft_auth import AuthenticationError, MicrosoftAuthenticator


class TestMicrosoftAuthCoverage:
    """Simple coverage tests for Microsoft authentication."""

    def test_authenticator_init_without_settings(self):
        """Test authenticator initialization without settings."""
        with patch('src.auth.microsoft_auth.get_settings') as mock_settings:
            mock_settings.return_value = Mock()
            mock_settings.return_value.microsoft_client_id = "test_client"
            mock_settings.return_value.microsoft_scopes = ["test_scope"]

            auth = MicrosoftAuthenticator()
            assert auth is not None

    def test_authenticator_init_with_settings(self):
        """Test authenticator initialization with settings."""
        mock_settings = Mock()
        mock_settings.microsoft_client_id = "test_client"
        mock_settings.microsoft_scopes = ["test_scope"]

        auth = MicrosoftAuthenticator(settings=mock_settings)
        assert auth is not None

    def test_authentication_error_basic(self):
        """Test AuthenticationError creation."""
        error = AuthenticationError("Test error")
        assert str(error) == "Test error"

        error_with_details = AuthenticationError("Test error", {"code": "invalid_request"})
        assert str(error_with_details) == "Test error"

    def test_token_cache_file_path(self):
        """Test token cache file path creation."""
        with patch('src.auth.microsoft_auth.get_settings') as mock_settings:
            mock_settings.return_value = Mock()
            mock_settings.return_value.microsoft_client_id = "test_client"
            mock_settings.return_value.microsoft_scopes = ["test_scope"]

            auth = MicrosoftAuthenticator()

            # Verify token cache file path exists
            assert hasattr(auth, 'token_cache_file')
            assert auth.token_cache_file is not None

    def test_is_authenticated_no_token(self):
        """Test is_authenticated when no token exists."""
        with patch('src.auth.microsoft_auth.get_settings') as mock_settings:
            mock_settings.return_value = Mock()
            mock_settings.return_value.microsoft_client_id = "test_client"
            mock_settings.return_value.microsoft_scopes = ["test_scope"]

            auth = MicrosoftAuthenticator()

            # Mock empty accounts
            with patch.object(auth.app, 'get_accounts', return_value=[]):
                result = auth.is_authenticated()
                assert result is False

    @pytest.mark.asyncio
    async def test_ensure_authenticated_no_token(self):
        """Test ensure_authenticated when no token exists."""
        with patch('src.auth.microsoft_auth.get_settings') as mock_settings:
            mock_settings.return_value = Mock()
            mock_settings.return_value.microsoft_client_id = "test_client"
            mock_settings.return_value.microsoft_scopes = ["test_scope"]

            auth = MicrosoftAuthenticator()

            # Mock get_access_token to return None (no token)
            with patch.object(auth, 'get_access_token', return_value=None):
                with patch.object(auth, 'authenticate', return_value="test_token"):
                    token = await auth.ensure_authenticated()
                    assert token == "test_token"
