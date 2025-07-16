"""
Additional coverage tests for authentication module - file operations and error handling.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from src.auth.microsoft_auth import MicrosoftAuthenticator


class TestAuthenticationFileOperations:
    """Test file operations and error handling in authentication."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock()
        settings.microsoft_client_id = "test_client_id"
        settings.microsoft_scopes = ["https://graph.microsoft.com/.default"]
        settings.token_cache_path = Path(tempfile.gettempdir()) / "test_token_cache.json"
        return settings

    def test_load_token_cache_file_exists(self, mock_settings):
        """Test loading token cache when file exists."""
        # Create a temporary cache file
        cache_content = '{"access_token": "test_token"}'

        with patch('builtins.open', mock_open(read_data=cache_content)):
            with patch.object(mock_settings.token_cache_path, 'exists', return_value=True):
                auth = MicrosoftAuthenticator(mock_settings)
                cache = auth._load_token_cache()

                # Verify cache was created
                assert cache is not None

    def test_load_token_cache_file_read_error(self, mock_settings):
        """Test loading token cache when file read fails."""
        with patch.object(mock_settings.token_cache_path, 'exists', return_value=True):
            with patch('builtins.open', side_effect=IOError("File read error")):
                with patch('src.auth.microsoft_auth.logger') as mock_logger:
                    auth = MicrosoftAuthenticator(mock_settings)
                    cache = auth._load_token_cache()

                    # Verify warning was logged
                    mock_logger.warning.assert_called()
                    assert cache is not None

    def test_load_token_cache_file_not_exists(self, mock_settings):
        """Test loading token cache when file doesn't exist."""
        with patch.object(mock_settings.token_cache_path, 'exists', return_value=False):
            auth = MicrosoftAuthenticator(mock_settings)
            cache = auth._load_token_cache()

            # Verify cache was still created
            assert cache is not None

    def test_save_token_cache_success(self, mock_settings):
        """Test saving token cache successfully."""
        auth = MicrosoftAuthenticator(mock_settings)

        # Mock app with token cache that has changed
        mock_app = Mock()
        mock_app.token_cache.has_state_changed = True
        mock_app.token_cache.serialize.return_value = '{"test": "data"}'
        auth.app = mock_app

        with patch('builtins.open', mock_open()) as mock_file:
            with patch.object(mock_settings.token_cache_path.parent, 'mkdir'):
                auth._save_token_cache()

                # Verify file was written
                mock_file.assert_called_once()

    def test_save_token_cache_no_state_change(self, mock_settings):
        """Test saving token cache when no state change."""
        auth = MicrosoftAuthenticator(mock_settings)

        # Mock app with token cache that hasn't changed
        mock_app = Mock()
        mock_app.token_cache.has_state_changed = False
        auth.app = mock_app

        with patch('builtins.open', mock_open()) as mock_file:
            auth._save_token_cache()

            # Verify file was not written
            mock_file.assert_not_called()

    def test_save_token_cache_write_error(self, mock_settings):
        """Test saving token cache when write fails."""
        auth = MicrosoftAuthenticator(mock_settings)

        # Mock app with token cache that has changed
        mock_app = Mock()
        mock_app.token_cache.has_state_changed = True
        mock_app.token_cache.serialize.return_value = '{"test": "data"}'
        auth.app = mock_app

        with patch('builtins.open', side_effect=IOError("Write error")):
            with patch('src.auth.microsoft_auth.logger') as mock_logger:
                auth._save_token_cache()

                # Verify error was logged
                mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_get_access_token_alias(self, mock_settings):
        """Test get_access_token as alias for authenticate."""
        auth = MicrosoftAuthenticator(mock_settings)

        with patch.object(auth, 'authenticate', return_value="test_token"):
            token = await auth.get_access_token()
            assert token == "test_token"
