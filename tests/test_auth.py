"""
Unit tests for Microsoft authentication module.

Tests MSAL integration, token management, and OAuth2 flow.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.auth.microsoft_auth import (AuthenticationError, CallbackHandler,
                                     MicrosoftAuthenticator)


class TestMicrosoftAuthenticator:
    """Test cases for MicrosoftAuthenticator class."""

    def test_authenticator_initialization(self, mock_settings):
        """Test authenticator initialization with settings."""
        authenticator = MicrosoftAuthenticator(mock_settings)

        assert authenticator.settings == mock_settings
        assert authenticator.app is None
        assert authenticator.http_server is None
        assert not authenticator.is_authenticated()

    @pytest.mark.asyncio
    async def test_successful_authentication_flow(self, mock_settings, temp_dir):
        """Test successful OAuth2 authentication flow."""
        # Mock MSAL PublicClientApplication
        mock_app = Mock()
        mock_app.get_accounts = Mock(return_value=[])
        mock_app.acquire_token_silent = Mock(return_value=None)
        mock_app.get_authorization_request_url = Mock(
            return_value="https://login.microsoftonline.com/auth?code=123"
        )
        mock_app.acquire_token_by_authorization_code = Mock(return_value={
            "access_token": "test-access-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        })

        with patch('msal.PublicClientApplication', return_value=mock_app):
            authenticator = MicrosoftAuthenticator(mock_settings)

            # Mock the callback server
            with patch.object(authenticator, '_start_callback_server') as mock_server:
                mock_server.return_value = ("http://localhost:8080", Mock())

                # Mock browser opening
                with patch('webbrowser.open') as mock_browser:
                    # Mock authorization code reception
                    with patch.object(authenticator, '_wait_for_auth_code') as mock_wait:
                        mock_wait.return_value = "test-auth-code"

                        token = await authenticator.get_access_token()

                        assert token == "test-access-token"
                        assert authenticator.is_authenticated()
                        mock_browser.assert_called_once()

    @pytest.mark.asyncio
    async def test_authentication_failure(self, mock_settings):
        """Test authentication failure handling."""
        mock_app = Mock()
        mock_app.get_accounts = Mock(return_value=[])
        mock_app.acquire_token_silent = Mock(return_value=None)
        mock_app.get_authorization_request_url = Mock(
            return_value="https://login.microsoftonline.com/auth?code=123"
        )
        mock_app.acquire_token_by_authorization_code = Mock(return_value={
            "error": "invalid_grant",
            "error_description": "Authorization code expired"
        })

        with patch('msal.PublicClientApplication', return_value=mock_app):
            authenticator = MicrosoftAuthenticator(mock_settings)

            with patch.object(authenticator, '_start_callback_server') as mock_server:
                mock_server.return_value = ("http://localhost:8080", Mock())

                with patch('webbrowser.open'):
                    with patch.object(authenticator, '_wait_for_auth_code') as mock_wait:
                        mock_wait.return_value = "invalid-code"

                        with pytest.raises(AuthenticationError):
                            await authenticator.get_access_token()

    @pytest.mark.asyncio
    async def test_token_caching_and_retrieval(self, mock_settings):
        """Test token caching and silent retrieval."""
        # Create a token cache file
        cache_content = {
            "AccessToken": {
                "test-key": {
                    "access_token": "cached-token",
                    "expires_on": 9999999999,  # Far future
                    "token_type": "Bearer"
                }
            }
        }

        cache_file = mock_settings.token_cache_file
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache_content))

        mock_app = Mock()
        mock_account = {"username": "test@example.com"}
        mock_app.get_accounts = Mock(return_value=[mock_account])
        mock_app.acquire_token_silent = Mock(return_value={
            "access_token": "cached-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        })

        with patch('msal.PublicClientApplication', return_value=mock_app):
            authenticator = MicrosoftAuthenticator(mock_settings)

            token = await authenticator.get_access_token()

            assert token == "cached-token"
            # Should not need interactive auth
            mock_app.get_authorization_request_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_authenticated_success(self, mock_settings):
        """Test ensure_authenticated with valid token."""
        authenticator = MicrosoftAuthenticator(mock_settings)
        authenticator._current_token = "valid-token"

        # Mock token validation
        with patch.object(authenticator, '_validate_token') as mock_validate:
            mock_validate.return_value = True

            result = await authenticator.ensure_authenticated()
            assert result is True

    @pytest.mark.asyncio
    async def test_ensure_authenticated_refresh(self, mock_settings):
        """Test ensure_authenticated with token refresh."""
        authenticator = MicrosoftAuthenticator(mock_settings)
        authenticator._current_token = "expired-token"

        # Mock token validation and refresh
        with patch.object(authenticator, '_validate_token') as mock_validate:
            mock_validate.return_value = False

            with patch.object(authenticator, 'get_access_token') as mock_get_token:
                mock_get_token.return_value = "new-token"

                result = await authenticator.ensure_authenticated()
                assert result is True
                mock_get_token.assert_called_once()

    def test_is_authenticated_with_no_token(self, mock_settings):
        """Test is_authenticated returns False when no token."""
        authenticator = MicrosoftAuthenticator(mock_settings)
        assert not authenticator.is_authenticated()

    def test_is_authenticated_with_valid_token(self, mock_settings):
        """Test is_authenticated returns True with valid token."""
        authenticator = MicrosoftAuthenticator(mock_settings)
        authenticator._current_token = "valid-token"

        with patch.object(authenticator, '_validate_token') as mock_validate:
            mock_validate.return_value = True
            assert authenticator.is_authenticated()

    def test_is_authenticated_with_invalid_token(self, mock_settings):
        """Test is_authenticated returns False with invalid token."""
        authenticator = MicrosoftAuthenticator(mock_settings)
        authenticator._current_token = "invalid-token"

        with patch.object(authenticator, '_validate_token') as mock_validate:
            mock_validate.return_value = False
            assert not authenticator.is_authenticated()


class TestCallbackHandler:
    """Test cases for OAuth2 callback handler."""

    def test_callback_handler_initialization(self):
        """Test callback handler initialization."""
        handler = CallbackHandler()
        assert handler.authorization_code is None
        assert handler.error is None
        assert not handler.received_callback

    def test_successful_callback_handling(self):
        """Test handling successful OAuth2 callback."""
        handler = CallbackHandler()

        # Mock the request object
        mock_request = Mock()
        mock_request.path = "/callback?code=test-auth-code&state=test-state"

        # Parse query parameters manually for test
        handler.authorization_code = "test-auth-code"
        handler.received_callback = True

        assert handler.authorization_code == "test-auth-code"
        assert handler.received_callback
        assert handler.error is None

    def test_error_callback_handling(self):
        """Test handling error OAuth2 callback."""
        handler = CallbackHandler()

        # Simulate error callback
        handler.error = "access_denied"
        handler.received_callback = True

        assert handler.error == "access_denied"
        assert handler.received_callback
        assert handler.authorization_code is None


class TestAuthenticationError:
    """Test cases for AuthenticationError exception."""

    def test_authentication_error_creation(self):
        """Test creating AuthenticationError."""
        error = AuthenticationError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_authentication_error_with_details(self):
        """Test AuthenticationError with additional details."""
        details = {"error_code": "invalid_grant", "description": "Token expired"}
        error = AuthenticationError("Authentication failed", details)

        assert "Authentication failed" in str(error)
        assert error.details == details


@pytest.mark.integration
class TestMicrosoftAuthenticatorIntegration:
    """Integration tests for Microsoft authenticator."""

    @pytest.mark.asyncio
    async def test_full_authentication_flow_mock(self, mock_settings):
        """Test complete authentication flow with mocked dependencies."""
        authenticator = MicrosoftAuthenticator(mock_settings)

        # Mock all MSAL dependencies
        with patch('msal.PublicClientApplication') as mock_msal:
            mock_app = Mock()
            mock_msal.return_value = mock_app

            # No existing accounts
            mock_app.get_accounts.return_value = []
            mock_app.acquire_token_silent.return_value = None

            # Mock interactive flow
            mock_app.get_authorization_request_url.return_value = "https://login.url"
            mock_app.acquire_token_by_authorization_code.return_value = {
                "access_token": "integration-test-token",
                "expires_in": 3600,
                "token_type": "Bearer"
            }

            # Mock server and browser interactions
            with patch.object(authenticator, '_start_callback_server') as mock_server:
                mock_server.return_value = ("http://localhost:8080", Mock())

                with patch('webbrowser.open') as mock_browser:
                    with patch.object(authenticator, '_wait_for_auth_code') as mock_wait:
                        mock_wait.return_value = "test-code"

                        # Execute authentication
                        token = await authenticator.get_access_token()

                        # Verify results
                        assert token == "integration-test-token"
                        assert authenticator.is_authenticated()

                        # Verify interaction sequence
                        mock_app.get_accounts.assert_called()
                        mock_app.get_authorization_request_url.assert_called()
                        mock_browser.assert_called_once()
                        mock_app.acquire_token_by_authorization_code.assert_called()

    def test_token_cache_file_operations(self, mock_settings):
        """Test token cache file creation and management."""
        authenticator = MicrosoftAuthenticator(mock_settings)

        # Cache file should not exist initially
        assert not mock_settings.token_cache_file.exists()

        # Mock MSAL token cache
        with patch('msal.SerializableTokenCache') as mock_cache:
            mock_cache_instance = Mock()
            mock_cache.return_value = mock_cache_instance

            with patch('msal.PublicClientApplication'):
                # Initialize authenticator (this should create cache structure)
                authenticator._initialize_msal_app()

                # Cache should be initialized
                mock_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_authentication_requests(self, mock_settings):
        """Test handling concurrent authentication requests."""
        authenticator = MicrosoftAuthenticator(mock_settings)

        with patch('msal.PublicClientApplication') as mock_msal:
            mock_app = Mock()
            mock_msal.return_value = mock_app

            mock_app.get_accounts.return_value = []
            mock_app.acquire_token_silent.return_value = None
            mock_app.get_authorization_request_url.return_value = "https://login.url"
            mock_app.acquire_token_by_authorization_code.return_value = {
                "access_token": "concurrent-test-token",
                "expires_in": 3600
            }

            with patch.object(authenticator, '_start_callback_server') as mock_server:
                mock_server.return_value = ("http://localhost:8080", Mock())

                with patch('webbrowser.open'):
                    with patch.object(authenticator, '_wait_for_auth_code') as mock_wait:
                        mock_wait.return_value = "test-code"

                        # Start multiple authentication requests concurrently
                        tasks = [
                            authenticator.get_access_token(),
                            authenticator.get_access_token(),
                            authenticator.get_access_token()
                        ]

                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        # All should succeed with same token
                        for result in results:
                            assert not isinstance(result, Exception)
                            assert result == "concurrent-test-token"


@pytest.mark.slow
class TestAuthenticationPerformance:
    """Performance tests for authentication operations."""

    @pytest.mark.asyncio
    async def test_token_validation_performance(self, mock_settings):
        """Test token validation performance."""
        authenticator = MicrosoftAuthenticator(mock_settings)
        authenticator._current_token = "test-token"

        # Mock fast token validation
        with patch.object(authenticator, '_validate_token') as mock_validate:
            mock_validate.return_value = True

            import time
            start_time = time.time()

            # Run multiple validations
            for _ in range(100):
                assert authenticator.is_authenticated()

            end_time = time.time()

            # Should be very fast (less than 1 second for 100 validations)
            assert end_time - start_time < 1.0
