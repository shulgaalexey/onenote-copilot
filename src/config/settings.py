"""
Configuration settings for OneNote Copilot CLI.

Manages environment variables, API keys, and application settings using Pydantic.
Follows Windows/PowerShell best practices and includes comprehensive validation.
"""

import os
from pathlib import Path
from typing import Optional, Union

from pydantic import (ConfigDict, Field, SecretStr, computed_field,
                      field_validator)
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings with environment variable validation.

    Loads configuration from environment variables with proper validation
    and type conversion. Follows security best practices for credential handling.
    """

    # OpenAI Configuration (Required for LangGraph agent)
    openai_api_key: SecretStr = Field(
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
        min_length=1,
        alias="AZURE_CLIENT_ID"
    )
    graph_api_base_url: str = Field(
        default="https://graph.microsoft.com/v1.0",
        description="Microsoft Graph API base URL"
    )
    msal_authority: str = Field(
        default="https://login.microsoftonline.com/common",
        description="MSAL authority URL for personal Microsoft accounts"
    )
    msal_scopes_raw: str = Field(
        default="Notes.Read,User.Read",
        description="Required scopes for OneNote access (comma-separated)",
        alias="MSAL_SCOPES"
    )
    msal_redirect_uri: str = Field(
        default="http://localhost:8080",
        description="OAuth2 redirect URI for browser authentication"
    )

    # Cache and Storage Configuration
    cache_dir: Optional[Path] = Field(
        default=None,
        description="Custom cache directory path (defaults to user home)"
    )
    config_dir: Optional[Path] = Field(
        default=None,
        description="Custom config directory path (defaults to user home)"
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
    log_file_enabled: bool = Field(
        default=True,
        description="Enable file logging to local project directory"
    )
    log_file_max_size_mb: int = Field(
        default=10,
        description="Maximum log file size in MB before rotation",
        gt=0,
        le=100
    )
    log_file_backup_count: int = Field(
        default=5,
        description="Number of backup log files to keep",
        gt=0,
        le=20
    )
    log_clear_on_startup: bool = Field(
        default=True,
        description="Clear log file on application startup"
    )
    log_performance_enabled: bool = Field(
        default=True,
        description="Enable performance logging for API calls and functions"
    )
    debug_enabled: bool = Field(
        default=False,
        description="Enable debug mode for detailed logging and error output",
        alias="ONENOTE_DEBUG"
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

    # OneNote Local Cache Configuration
    onenote_cache_root: Path = Field(
        default_factory=lambda: Path.cwd() / "data" / "onenote_cache",
        description="Root directory for OneNote local cache"
    )
    onenote_cache_max_size_gb: int = Field(
        default=5,
        description="Maximum cache size in gigabytes",
        gt=0,
        le=100
    )
    onenote_sync_interval_hours: int = Field(
        default=24,
        description="Automatic sync interval in hours",
        gt=0,
        le=168  # 1 week max
    )
    onenote_enable_background_sync: bool = Field(
        default=True,
        description="Enable automatic background synchronization"
    )
    onenote_download_images: bool = Field(
        default=True,
        description="Download and cache OneNote images locally"
    )
    onenote_download_attachments: bool = Field(
        default=True,
        description="Download and cache OneNote file attachments locally"
    )
    onenote_preserve_html: bool = Field(
        default=True,
        description="Keep original HTML content alongside markdown"
    )
    onenote_markdown_format: str = Field(
        default="github",
        description="Markdown format style (github, commonmark, etc.)"
    )
    onenote_batch_download_size: int = Field(
        default=20,  # Increased from 10 for better performance with large caches
        description="Number of pages to download in parallel",
        gt=1,
        le=50
    )
    onenote_retry_attempts: int = Field(
        default=2,  # Reduced from 3 for faster failure handling with fallbacks
        description="Number of retry attempts for failed downloads",
        gt=0,
        le=10
    )
    onenote_cleanup_orphaned_assets: bool = Field(
        default=True,
        description="Automatically clean up orphaned assets"
    )
    onenote_enable_compression: bool = Field(
        default=True,  # Enabled by default for space efficiency with large caches
        description="Compress cached content to save space"
    )
    onenote_cache_index_batch_size: int = Field(
        default=100,  # New setting for bulk search indexing operations
        description="Batch size for search index operations",
        gt=10,
        le=1000
    )
    onenote_memory_cache_size_mb: int = Field(
        default=50,  # New setting for in-memory cache of frequently accessed content
        description="In-memory cache size in MB for hot content",
        gt=1,
        le=500
    )

    # Semantic Search Configuration
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI model for generating embeddings"
    )
    embedding_dimensions: int = Field(
        default=1536,
        description="Embedding vector dimensions",
        gt=0,
        le=3072
    )
    embedding_batch_size: int = Field(
        default=200,  # Increased from 100 for better throughput with large caches
        description="Batch size for embedding generation",
        gt=0,
        le=2048
    )
    vector_db_path: str = Field(
        default="./data/vector_store",
        description="Path to ChromaDB vector database"
    )
    vector_db_collection_name: str = Field(
        default="onenote_content",
        description="ChromaDB collection name for OneNote content"
    )
    semantic_search_threshold: float = Field(
        default=0.4,
        description="Minimum similarity threshold for semantic search",
        ge=0.0,
        le=1.0
    )
    semantic_search_limit: int = Field(
        default=20,  # Increased from 10 for better large cache coverage
        description="Maximum number of semantic search results",
        gt=0,
        le=100
    )
    hybrid_search_weight: float = Field(
        default=0.6,
        description="Weight for semantic vs keyword search in hybrid mode (0.0=all keyword, 1.0=all semantic)",
        ge=0.0,
        le=1.0
    )
    max_chunks_per_page: int = Field(
        default=8,  # Increased from 5 for better large page handling
        description="Maximum number of text chunks per OneNote page",
        gt=0,
        le=20
    )
    chunk_size: int = Field(
        default=1500,  # Increased from 1000 for fewer chunks with large caches
        description="Size of text chunks for embedding",
        gt=100,
        le=8000
    )
    chunk_overlap: int = Field(
        default=300,  # Increased proportionally with chunk_size
        description="Overlap between text chunks",
        ge=0,
        le=500
    )
    enable_hybrid_search: bool = Field(
        default=True,
        description="Enable hybrid search combining semantic and keyword search"
    )
    cache_embeddings: bool = Field(
        default=True,
        description="Cache embeddings to reduce API calls"
    )
    background_indexing: bool = Field(
        default=True,  # Enabled for better large cache performance
        description="Enable background indexing of new content"
    )

    @computed_field
    @property
    def onenote_cache_full_path(self) -> Path:
        """Get the full path to the OneNote cache directory."""
        if self.onenote_cache_root.is_absolute():
            return self.onenote_cache_root
        else:
            # Relative to project root
            return Path.cwd() / self.onenote_cache_root

    @computed_field
    @property
    def vector_db_full_path(self) -> Path:
        """Get the full path to the vector database directory."""
        if Path(self.vector_db_path).is_absolute():
            return Path(self.vector_db_path)
        else:
            # Relative to project root
            return Path.cwd() / self.vector_db_path

    @computed_field
    @property
    def msal_scopes(self) -> list[str]:
        """Parse msal_scopes from the raw string value."""
        return [scope.strip() for scope in self.msal_scopes_raw.split(",") if scope.strip()]

    @computed_field
    @property
    def token_cache_file(self) -> Path:
        """Get the full path to the MSAL token cache file."""
        return self.token_cache_path

    @computed_field
    @property
    def graph_api_url(self) -> str:
        """Get the Microsoft Graph API base URL (alias for graph_api_base_url)."""
        return self.graph_api_base_url

    @computed_field
    @property
    def search_url(self) -> str:
        """Get the OneNote search API endpoint URL."""
        return f"{self.graph_api_base_url}/me/onenote/pages"

    @computed_field
    @property
    def graph_api_scopes(self) -> list[str]:
        """Get the Microsoft Graph API scopes as full URLs."""
        base_url = "https://graph.microsoft.com"
        return [f"{base_url}/{scope}" for scope in ["Notes.Read", "Notes.Read.All"]]

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard logging levels."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of: {', '.join(valid_levels)}")
        return v.upper()

    @field_validator("onenote_enable_background_sync", mode="before")
    @classmethod
    def validate_onenote_enable_background_sync(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("onenote_download_images", mode="before")
    @classmethod
    def validate_onenote_download_images(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("onenote_download_attachments", mode="before")
    @classmethod
    def validate_onenote_download_attachments(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("onenote_preserve_html", mode="before")
    @classmethod
    def validate_onenote_preserve_html(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("onenote_cleanup_orphaned_assets", mode="before")
    @classmethod
    def validate_onenote_cleanup_orphaned_assets(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("onenote_enable_compression", mode="before")
    @classmethod
    def validate_onenote_enable_compression(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("onenote_cache_root", mode="before")
    @classmethod
    def validate_onenote_cache_root(cls, v: Union[str, Path]) -> Path:
        """Convert cache root to Path and validate it can be created."""
        cache_path = Path(v) if isinstance(v, str) else v

        # Create directory if it doesn't exist
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise ValueError(f"Cannot create OneNote cache directory {cache_path}: {e}")

        return cache_path

    @field_validator("debug_enabled", mode="before")
    @classmethod
    def validate_debug_enabled(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("cli_welcome_enabled", mode="before")
    @classmethod
    def validate_cli_welcome_enabled(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("cli_color_enabled", mode="before")
    @classmethod
    def validate_cli_color_enabled(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("cli_markdown_enabled", mode="before")
    @classmethod
    def validate_cli_markdown_enabled(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("enable_hybrid_search", mode="before")
    @classmethod
    def validate_enable_hybrid_search(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("cache_embeddings", mode="before")
    @classmethod
    def validate_cache_embeddings(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("background_indexing", mode="before")
    @classmethod
    def validate_background_indexing(cls, v) -> bool:
        """Parse boolean from environment variable."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on", "enable", "enabled")
        return bool(v)

    @field_validator("cache_dir", mode="before")
    @classmethod
    def validate_cache_dir(cls, v: Optional[str]) -> Optional[Path]:
        """Convert cache_dir string to Path and validate it exists or can be created."""
        if v is None:
            # Default to user home directory, handle test environments gracefully
            try:
                return Path.home() / ".onenote_copilot"
            except RuntimeError:
                # Fallback for test environments where home directory isn't available
                return Path.cwd() / ".onenote_copilot"

        cache_path = Path(v)

        # Create directory if it doesn't exist
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise ValueError(f"Cannot create cache directory {cache_path}: {e}")

        return cache_path

    @field_validator("config_dir", mode="before")
    @classmethod
    def validate_config_dir(cls, v: Optional[str]) -> Optional[Path]:
        """Convert config_dir string to Path and validate it exists or can be created."""
        if v is None:
            # Default to user home directory, handle test environments gracefully
            try:
                return Path.home() / ".onenote_copilot"
            except RuntimeError:
                # Fallback for test environments where home directory isn't available
                return Path.cwd() / ".onenote_copilot"

        config_path = Path(v)

        # Create directory if it doesn't exist
        try:
            config_path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise ValueError(f"Cannot create config directory {config_path}: {e}")

        return config_path

    @property
    def token_cache_path(self) -> Path:
        """Get the full path to the MSAL token cache file."""
        try:
            cache_dir = self.cache_dir or (Path.home() / ".onenote_copilot")
        except RuntimeError:
            cache_dir = self.cache_dir or (Path.cwd() / ".onenote_copilot")
        return cache_dir / self.token_cache_filename

    @property
    def credentials_dir(self) -> Path:
        """Get the credentials directory path."""
        try:
            cache_dir = self.cache_dir or (Path.home() / ".onenote_copilot")
        except RuntimeError:
            cache_dir = self.cache_dir or (Path.cwd() / ".onenote_copilot")
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

    model_config = ConfigDict(
        env_file=[".env.local", ".env"],  # Try .env.local first, then fallback to .env
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="",
        extra="allow",  # Allow extra fields for test compatibility
        env_nested_delimiter=None  # Disable JSON parsing for environment variables
    )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings(force_reload: bool = False) -> Settings:
    """
    Get the global settings instance.

    This function provides a way to access settings throughout the application
    while allowing for dependency injection in tests.

    Args:
        force_reload: If True, force reload settings from environment

    Returns:
        Global settings instance
    """
    global _settings
    if _settings is None or force_reload:
        _settings = Settings()
    return _settings


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
        if not settings.openai_api_key.get_secret_value().startswith(('sk-', 'sk-proj-')):
            raise ValueError("OpenAI API key appears to be invalid (should start with 'sk-')")

        if len(settings.azure_client_id) != 36:
            raise ValueError("Azure client ID appears to be invalid (should be 36 characters)")

        # Ensure cache directory is writable
        cache_dir = settings.cache_dir
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            test_file = cache_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
        except (OSError, PermissionError):
            raise ValueError(f"Cache directory is not writable: {cache_dir}")

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
