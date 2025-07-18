"""
Microsoft authentication module using MSAL for personal Microsoft accounts.

Provides browser-based OAuth2 authentication with token caching and automatic
refresh. Designed specifically for personal Microsoft accounts accessing OneNote
through Microsoft Graph API.
"""

import asyncio
import json
import logging
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import httpx
from msal import PublicClientApplication
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.logging import log_api_call, log_performance
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP server handler for OAuth2 callback from Microsoft."""

    def __init__(self, auth_code_container: Dict[str, str], *args, **kwargs):
        self.auth_code_container = auth_code_container
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        """Handle GET request with authorization code."""
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        if "code" in query_params:
            self.auth_code_container["code"] = query_params["code"][0]

            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()

            success_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OneNote Copilot - Authentication Success</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        .success { color: #28a745; font-size: 24px; margin-bottom: 20px; }
        .instruction { color: #666; font-size: 16px; }
    </style>
</head>
<body>
    <div class="success">✅ Authentication Successful!</div>
    <div class="instruction">
        You can now close this browser window and return to the OneNote Copilot CLI.
    </div>
</body>
</html>"""

            self.wfile.write(success_html.encode('utf-8'))
        elif "error" in query_params:
            error = query_params.get("error", ["unknown"])[0]
            error_description = query_params.get("error_description", [""])[0]

            self.auth_code_container["error"] = error
            self.auth_code_container["error_description"] = error_description

            # Send error response
            self.send_response(400)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()

            error_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OneNote Copilot - Authentication Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
        .error {{ color: #dc3545; font-size: 24px; margin-bottom: 20px; }}
        .details {{ color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="error">❌ Authentication Failed</div>
    <div class="details">Error: {error}</div>
    <div class="details">{error_description}</div>
    <div class="details">Please close this window and try again in the CLI.</div>
</body>
</html>"""

            self.wfile.write(error_html.encode('utf-8'))

    def log_message(self, format: str, *args) -> None:
        """Suppress default HTTP server logging."""
        pass


class MicrosoftAuthenticator:
    """
    Microsoft authentication manager using MSAL for personal accounts.

    Handles browser-based OAuth2 flow with token caching and automatic refresh.
    Designed specifically for OneNote access through Microsoft Graph API.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the Microsoft authenticator.

        Args:
            settings: Optional settings instance (defaults to global settings)
        """
        self.settings = settings or get_settings()

        # Initialize MSAL PublicClientApplication (set to None initially for tests)
        self.app: Optional[PublicClientApplication] = None
        self.http_server: Optional[HTTPServer] = None

        # Authentication state
        self._current_account: Optional[Dict[str, Any]] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _initialize_app(self) -> None:
        """Initialize MSAL PublicClientApplication when needed."""
        if self.app is None:
            self.app = PublicClientApplication(
                client_id=self.settings.azure_client_id,
                authority=self.settings.msal_authority,
                token_cache=self._get_token_cache()
            )

    def _get_token_cache(self):
        """Get or create MSAL token cache."""
        from msal.token_cache import SerializableTokenCache

        cache = SerializableTokenCache()
        cache_file = self.settings.token_cache_path

        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache.deserialize(f.read())
                logger.debug(f"Loaded token cache from {cache_file}")
            except Exception as e:
                logger.warning(f"Failed to load token cache: {e}")

        return cache

    def _save_token_cache(self) -> None:
        """Save token cache to disk."""
        if self.app and self.app.token_cache.has_state_changed:
            try:
                cache_file = self.settings.token_cache_path
                cache_file.parent.mkdir(parents=True, exist_ok=True)

                with open(cache_file, 'w', encoding='utf-8') as f:
                    f.write(self.app.token_cache.serialize())

                logger.debug(f"Saved token cache to {cache_file}")
            except Exception as e:
                logger.error(f"Failed to save token cache: {e}")

    async def get_access_token(self) -> str:
        """
        Get access token (alias for authenticate for test compatibility).

        Returns:
            Valid access token for Microsoft Graph API

        Raises:
            AuthenticationError: If authentication fails
        """
        return await self.authenticate()

    async def authenticate(self) -> str:
        """
        Authenticate user and get access token.

        Returns:
            Valid access token for Microsoft Graph API

        Raises:
            AuthenticationError: If authentication fails
        """
        self._initialize_app()

        try:
            # Try silent authentication first (using cached tokens)
            token = await self._try_silent_authentication()
            if token:
                logger.info("Authentication successful using cached tokens")
                return token

            # Fall back to interactive authentication
            logger.info("Starting interactive authentication flow")
            token = await self._interactive_authentication()

            if not token:
                raise AuthenticationError("Interactive authentication failed")

            logger.info("Interactive authentication successful")
            return token

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(f"Authentication failed: {e}")

    async def _validate_token(self, token: str) -> bool:
        """
        Internal token validation method for testing.

        Args:
            token: Access token to validate

        Returns:
            True if token is valid, False otherwise
        """
        return await self.validate_token(token)

    async def _try_silent_authentication(self) -> Optional[str]:
        """
        Try to authenticate silently using cached tokens.

        Returns:
            Access token if successful, None otherwise
        """
        if not self.app:
            return None

        try:
            accounts = self.app.get_accounts()
            if not accounts:
                logger.debug("No cached accounts found")
                return None

            # Use the first account (for personal accounts, there's typically only one)
            account = accounts[0]
            logger.debug(f"Trying silent authentication for account: {account.get('username', 'unknown')}")

            result = self.app.acquire_token_silent(
                scopes=self.settings.msal_scopes,
                account=account
            )

            if result and "access_token" in result:
                self._update_auth_state(result, account)
                self._save_token_cache()
                return result["access_token"]

            if result and "error" in result:
                logger.debug(f"Silent authentication failed: {result.get('error_description', result['error'])}")

            return None

        except Exception as e:
            logger.debug(f"Silent authentication failed: {e}")
            return None

    async def _interactive_authentication(self) -> Optional[str]:
        """
        Perform interactive browser-based authentication.

        Returns:
            Access token if successful, None otherwise
        """
        if not self.app:
            return None

        try:
            # Start local callback server
            auth_code_container: Dict[str, str] = {}
            server = self._start_callback_server(auth_code_container)

            try:
                # Get authorization URL and open browser
                auth_url = self.app.get_authorization_request_url(
                    scopes=self.settings.msal_scopes,
                    redirect_uri=self.settings.msal_redirect_uri
                )

                logger.info("Opening browser for authentication...")
                webbrowser.open(auth_url)

                # Wait for callback with timeout
                auth_code = await self._wait_for_auth_code(auth_code_container, timeout=300)

                if not auth_code:
                    return None

                # Exchange authorization code for tokens
                result = self.app.acquire_token_by_authorization_code(
                    code=auth_code,
                    scopes=self.settings.msal_scopes,
                    redirect_uri=self.settings.msal_redirect_uri
                )

                if result and "access_token" in result:
                    # Get account info
                    accounts = self.app.get_accounts()
                    account = accounts[0] if accounts else None

                    self._update_auth_state(result, account)
                    self._save_token_cache()
                    return result["access_token"]

                if result and "error" in result:
                    error_msg = result.get("error_description", result["error"])
                    logger.error(f"Token exchange failed: {error_msg}")

                return None

            finally:
                server.shutdown()

        except Exception as e:
            logger.error(f"Interactive authentication failed: {e}")
            return None

    def _start_callback_server(self, auth_code_container: Dict[str, str]) -> HTTPServer:
        """Start local HTTP server for OAuth2 callback."""
        # Parse redirect URI to get port
        redirect_uri = urlparse(self.settings.msal_redirect_uri)
        port = redirect_uri.port or 8080

        # Create server with custom handler
        def handler_factory(*args, **kwargs):
            return CallbackHandler(auth_code_container, *args, **kwargs)

        server = HTTPServer(("localhost", port), handler_factory)

        # Start server in background thread
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        logger.debug(f"Started callback server on port {port}")
        return server

    async def _wait_for_auth_code(self, auth_code_container: Dict[str, str], timeout: int = 300) -> Optional[str]:
        """
        Wait for authorization code from callback.

        Args:
            auth_code_container: Container to receive auth code
            timeout: Timeout in seconds

        Returns:
            Authorization code if received, None otherwise
        """
        for _ in range(timeout):
            await asyncio.sleep(1)

            if "code" in auth_code_container:
                return auth_code_container["code"]

            if "error" in auth_code_container:
                error = auth_code_container.get("error")
                error_desc = auth_code_container.get("error_description", "")
                logger.error(f"OAuth2 error: {error} - {error_desc}")

                # Provide specific guidance for server_error
                if error == "server_error":
                    logger.error("Microsoft server_error detected. This often indicates:")
                    logger.error("1. Session conflict from previous user logout")
                    logger.error("2. Browser cache issues with Microsoft authentication")
                    logger.error("3. Timing issues with OAuth2 session cleanup")
                    logger.error("Suggested fixes:")
                    logger.error("- Clear browser cache for login.microsoftonline.com")
                    logger.error("- Try incognito/private browsing mode")
                    logger.error("- Wait 5-10 minutes for Microsoft session cleanup")
                    logger.error("- Use: Remove-Item '$env:USERPROFILE\\.onenote_copilot' -Recurse -Force")

                return None

        logger.error("Authentication timeout - no response received")
        return None

    def _update_auth_state(self, token_result: Dict[str, Any], account: Optional[Dict[str, Any]]) -> None:
        """Update internal authentication state."""
        self._access_token = token_result["access_token"]
        self._current_account = account

        # Calculate token expiration using timedelta
        expires_in = token_result.get("expires_in", 3600)  # Default 1 hour
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    async def get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token

        Raises:
            AuthenticationError: If unable to get valid token
        """
        # Check if we have a valid token
        if self._access_token and self._token_expires_at:
            # Add 5-minute buffer before expiration using timedelta
            buffer_time = datetime.now(timezone.utc) + timedelta(minutes=5)

            if self._token_expires_at > buffer_time:
                return self._access_token

        # Token expired or doesn't exist, re-authenticate
        logger.debug("Token expired or missing, re-authenticating")
        return await self.authenticate()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def validate_token(self, token: str) -> bool:
        """
        Validate access token by making a test API call.

        Args:
            token: Access token to validate

        Returns:
            True if token is valid, False otherwise
        """
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Make a simple API call to validate token
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.get(
                    self.settings.get_graph_endpoint("/me"),
                    headers=headers
                )

                if response.status_code == 200:
                    user_info = response.json()
                    logger.debug(f"Token validated for user: {user_info.get('displayName', 'unknown')}")
                    return True
                elif response.status_code == 401:
                    logger.debug("Token validation failed: unauthorized")
                    return False
                else:
                    logger.warning(f"Token validation returned status {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return False

    def get_current_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the currently authenticated user.

        Returns:
            User account information if available, None otherwise
        """
        return self._current_account

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated.

        Returns:
            True if authenticated with valid token, False otherwise
        """
        if not hasattr(self, '_access_token') or not hasattr(self, '_token_expires_at'):
            return False

        return (
            self._access_token is not None and
            self._token_expires_at is not None and
            self._token_expires_at > datetime.now(timezone.utc)
        )

    async def ensure_authenticated(self) -> bool:
        """
        Ensure user is authenticated with a valid token.

        Returns:
            True if authentication is successful, False otherwise
        """
        try:
            if self.is_authenticated():
                # Check if token is still valid
                if hasattr(self, '_access_token') and self._access_token:
                    is_valid = await self._validate_token(self._access_token)
                    if is_valid:
                        return True

            # Need to authenticate or refresh token
            await self.authenticate()
            return True

        except Exception as e:
            logger.error(f"Failed to ensure authentication: {e}")
            return False

    def clear_cache(self) -> None:
        """Clear all cached tokens and authentication state."""
        try:
            # Clear internal state
            self._access_token = None
            self._current_account = None
            self._token_expires_at = None

            # Clear MSAL cache
            if hasattr(self.app.token_cache, 'clear'):
                self.app.token_cache.clear()

            # Remove cache file
            cache_file = self.settings.token_cache_path
            if cache_file.exists():
                cache_file.unlink()
                logger.info("Token cache cleared")

        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

    async def logout(self) -> bool:
        """
        Perform complete user logout and clear all authentication data.

        This method:
        - Clears the current access token and user session
        - Removes MSAL token cache from memory and disk
        - Resets the authenticator state
        - Provides guidance for complete session cleanup

        Returns:
            True if logout was successful, False otherwise
        """
        try:
            logger.info("Starting user logout process...")

            # Clear current session data
            self._access_token = None
            self._current_account = None
            self._token_expires_at = None

            # Clear in-memory token cache
            if self.app and hasattr(self.app.token_cache, 'clear'):
                self.app.token_cache.clear()
                logger.debug("Cleared in-memory token cache")

            # Remove token cache file from disk
            cache_file = self.settings.token_cache_path
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Removed token cache file: {cache_file}")

            # Reset the MSAL app to ensure clean state
            self.app = None

            logger.info("✅ User logout completed successfully")
            logger.info("📋 To ensure complete session cleanup for next user:")
            logger.info("   1. Clear browser cache for login.microsoftonline.com")
            logger.info("   2. Consider using incognito/private browsing for next login")
            logger.info("   3. If issues persist, wait 5-10 minutes for Microsoft session cleanup")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to logout user: {e}")
            return False

    def force_clear_all_auth_state(self) -> bool:
        """
        Force clear all authentication state including cached tokens.

        Use this method when experiencing authentication conflicts or server_error.
        This is more aggressive than normal logout and clears all possible state.

        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            logger.info("🔧 Force clearing all authentication state...")

            # Clear in-memory state
            self._access_token = None
            self._current_account = None
            self._token_expires_at = None
            self.app = None

            # Clear all possible cache locations
            cache_locations = [
                self.settings.token_cache_path,
                Path.home() / ".onenote_copilot" / ".msal_token_cache.json",
                Path.cwd() / ".onenote_copilot" / ".msal_token_cache.json"
            ]

            cleared_files = 0
            for cache_path in cache_locations:
                try:
                    if cache_path.exists():
                        cache_path.unlink()
                        logger.info(f"Removed cache file: {cache_path}")
                        cleared_files += 1
                except Exception as e:
                    logger.debug(f"Could not remove {cache_path}: {e}")

            # Clear cache directories if empty
            cache_dirs = [
                Path.home() / ".onenote_copilot",
                Path.cwd() / ".onenote_copilot"
            ]

            for cache_dir in cache_dirs:
                try:
                    if cache_dir.exists() and not any(cache_dir.iterdir()):
                        cache_dir.rmdir()
                        logger.info(f"Removed empty cache directory: {cache_dir}")
                except Exception as e:
                    logger.debug(f"Could not remove directory {cache_dir}: {e}")

            logger.info(f"✅ Force cleanup completed. Cleared {cleared_files} cache files.")
            logger.info("📋 Additional recommendations for server_error resolution:")
            logger.info("   1. Clear browser data for *.microsoftonline.com")
            logger.info("   2. Try authentication in incognito/private browsing mode")
            logger.info("   3. Restart the browser completely")
            logger.info("   4. Wait 5-10 minutes for Microsoft's session cleanup")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to force clear authentication state: {e}")
            return False

    async def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get detailed user profile information from Microsoft Graph API.

        Returns:
            User profile information if available, None otherwise
        """
        try:
            if not self.is_authenticated():
                logger.debug("User not authenticated, cannot get profile")
                return None

            # Use the existing access token
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.get(
                    self.settings.get_graph_endpoint("/me"),
                    headers=headers
                )

                if response.status_code == 200:
                    user_profile = response.json()
                    logger.debug(f"Retrieved user profile for: {user_profile.get('displayName', 'unknown')}")
                    return user_profile
                else:
                    logger.warning(f"Failed to get user profile: HTTP {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None


class AuthenticationError(Exception):
    """Exception raised when authentication fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


async def get_authenticated_token() -> str:
    """
    Convenience function to get an authenticated token.

    Returns:
        Valid access token for Microsoft Graph API

    Raises:
        AuthenticationError: If authentication fails
    """
    authenticator = MicrosoftAuthenticator()
    return await authenticator.get_valid_token()


if __name__ == "__main__":
    """Test authentication flow."""
    async def test_auth():
        try:
            authenticator = MicrosoftAuthenticator()

            print("Testing authentication...")
            token = await authenticator.authenticate()

            print("Testing token validation...")
            is_valid = await authenticator.validate_token(token)

            if is_valid:
                user_info = authenticator.get_current_user_info()
                username = user_info.get("username", "unknown") if user_info else "unknown"
                print(f"✅ Authentication successful for user: {username}")
            else:
                print("❌ Token validation failed")

        except Exception as e:
            print(f"❌ Authentication test failed: {e}")

    asyncio.run(test_auth())
