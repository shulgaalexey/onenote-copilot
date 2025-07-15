"""
Configuration settings for OneNote Copilot CLI.

Manages environment variables, API keys, and application settings using Pydantic.
Follows Windows/PowerShell best practices and includes comprehensive validation.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings with environment variable validation.

    Loads configuration from environment variables with proper validation
    and type conversion. Follows security best practices for credential handling.
    """

    # OpenAI Configuration (Required for LangGraph agent)
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key for LangGraph agent functionality",
        min_length=1
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use for chat completions"
    )
    openai_temperature: float = Field(
        default=0.1,
        description="Temperature for OpenAI model responses",
        ge=0.0,
        le=2.0
    )

    # Microsoft Graph API Configuration (Required for OneNote access)
    azure_client_id: str = Field(
        ...,
        description="Azure application client ID for Microsoft Graph API",
        min_length=1
    )
    graph_api_base_url: str = Field(
        default="https://graph.microsoft.com/v1.0",
        description="Microsoft Graph API base URL"
    )
    msal_authority: str = Field(
        default="https://login.microsoftonline.com/common",
        description="MSAL authority URL for personal Microsoft accounts"
    )
    msal_scopes: list[str] = Field(
        default=["Notes.Read", "User.Read"],
        description="Required scopes for OneNote access"
    )
    msal_redirect_uri: str = Field(
        default="http://localhost:8080/callback",
        description="OAuth2 redirect URI for browser authentication"
    )

    # Cache and Storage Configuration
    cache_dir: Optional[Path] = Field(
        default=None,
        description="Custom cache directory path (defaults to user home)"
    )
    token_cache_filename: str = Field(
        default=".msal_token_cache.json",
        description="Filename for MSAL token cache"
    )

    # Application Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    max_search_results: int = Field(
        default=20,
        description="Maximum number of OneNote pages to return in search",
        gt=0,
        le=100
    )
    request_timeout: int = Field(
        default=30,
        description="HTTP request timeout in seconds",
        gt=0
    )
    retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for failed API calls",
        gt=0,
        le=10
    )

    # CLI Configuration
    cli_welcome_enabled: bool = Field(
        default=True,
        description="Whether to show welcome message on CLI startup"
    )
    cli_color_enabled: bool = Field(
        default=True,
        description="Whether to enable colored output in CLI"
    )
    cli_markdown_enabled: bool = Field(
        default=True,
        description="Whether to enable markdown rendering in CLI"
    )

    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard logging levels."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of: {', '.join(valid_levels)}")
        return v.upper()

    @validator("cache_dir", pre=True)
    def validate_cache_dir(cls, v: Optional[str]) -> Optional[Path]:
        """Convert cache_dir string to Path and validate it exists or can be created."""
        if v is None:
            # Default to user home directory
            return Path.home() / ".onenote_copilot"

        cache_path = Path(v)

        # Create directory if it doesn't exist
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise ValueError(f"Cannot create cache directory {cache_path}: {e}")

        return cache_path

    @property
    def token_cache_path(self) -> Path:
        """Get the full path to the MSAL token cache file."""
        cache_dir = self.cache_dir or Path.home() / ".onenote_copilot"
        return cache_dir / self.token_cache_filename

    @property
    def credentials_dir(self) -> Path:
        """Get the credentials directory path."""
        cache_dir = self.cache_dir or Path.home() / ".onenote_copilot"
        creds_dir = cache_dir / "credentials"
        creds_dir.mkdir(exist_ok=True)
        return creds_dir

    def get_graph_endpoint(self, path: str) -> str:
        """
        Get a complete Microsoft Graph API endpoint URL.

        Args:
            path: API path (e.g., '/me/onenote/pages')

        Returns:
            Complete URL for the Graph API endpoint
        """
        if not path.startswith('/'):
            path = '/' + path
        return f"{self.graph_api_base_url}{path}"

    class Config:
        """Pydantic configuration."""
        env_file = ".env.local"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Allow environment variables to override .env file
        env_prefix = ""


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get the global settings instance.

    This function provides a way to access settings throughout the application
    while allowing for dependency injection in tests.

    Returns:
        Global settings instance
    """
    return settings


def validate_environment() -> None:
    """
    Validate that all required environment variables are properly configured.

    Raises:
        ValueError: If required configuration is missing or invalid
    """
    try:
        # This will trigger validation of all fields
        settings = get_settings()

        # Additional validation checks
        if not settings.openai_api_key.startswith(('sk-', 'sk-proj-')):
            raise ValueError("OpenAI API key appears to be invalid (should start with 'sk-')")

        if len(settings.azure_client_id) != 36:
            raise ValueError("Azure client ID appears to be invalid (should be 36 characters)")

        # Ensure cache directory is writable
        test_file = settings.cache_dir / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except (OSError, PermissionError):
            raise ValueError(f"Cache directory is not writable: {settings.cache_dir}")

    except Exception as e:
        raise ValueError(f"Environment validation failed: {e}")


if __name__ == "__main__":
    """Test configuration loading and validation."""
    try:
        validate_environment()
        settings = get_settings()
        print("✅ Configuration loaded successfully!")
        print(f"OpenAI Model: {settings.openai_model}")
        print(f"Cache Directory: {settings.cache_dir}")
        print(f"Token Cache Path: {settings.token_cache_path}")
        print(f"Graph API Base: {settings.graph_api_base_url}")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        exit(1)
