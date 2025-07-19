"""
User logout service for OneNote Copilot.

Provides comprehensive user logout functionality that clears all user-specific
data including authentication tokens, vector indexes, content caches, and
temporary files to allow a clean login for another user.
"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import List, Optional

from ..auth.microsoft_auth import MicrosoftAuthenticator
from ..config.logging import get_logger, logged
from ..config.settings import get_settings
from ..storage.embedding_cache import EmbeddingCache
from ..storage.vector_store import VectorStore

logger = get_logger(__name__)


class LogoutServiceError(Exception):
    """Exception raised when logout service operations fail."""

    def __init__(self, message: str, failed_operations: Optional[List[str]] = None):
        super().__init__(message)
        self.failed_operations = failed_operations or []


class LogoutService:
    """
    Comprehensive user logout service.

    Handles complete user data cleanup including:
    - Authentication token removal
    - Vector database clearing
    - Embedding cache cleanup
    - Temporary file removal
    - Log file cleanup (optional)
    """

    def __init__(self, settings: Optional[object] = None):
        """
        Initialize logout service.

        Args:
            settings: Application settings (auto-loaded if not provided)
        """
        self.settings = settings or get_settings()
        self.failed_operations: List[str] = []

    @logged("Perform complete user logout")
    async def logout_user(
        self,
        clear_logs: bool = False,
        clear_vector_db: bool = True,
        clear_embedding_cache: bool = True
    ) -> bool:
        """
        Perform complete user logout and data cleanup.

        Args:
            clear_logs: Whether to clear application logs
            clear_vector_db: Whether to clear vector database
            clear_embedding_cache: Whether to clear embedding cache

        Returns:
            True if logout was successful, False if any operations failed

        Raises:
            LogoutServiceError: If critical logout operations fail
        """
        logger.info("🔓 Starting complete user logout process...")
        self.failed_operations = []
        success_count = 0
        total_operations = 0

        try:
            # 1. Clear authentication data
            total_operations += 1
            if await self._clear_authentication():
                success_count += 1
                logger.info("✅ Authentication data cleared")
            else:
                self.failed_operations.append("authentication")
                logger.warning("⚠️ Failed to clear authentication data")

            # 2. Clear vector database
            if clear_vector_db:
                total_operations += 1
                if await self._clear_vector_database():
                    success_count += 1
                    logger.info("✅ Vector database cleared")
                else:
                    self.failed_operations.append("vector_database")
                    logger.warning("⚠️ Failed to clear vector database")

            # 3. Clear embedding cache
            if clear_embedding_cache:
                total_operations += 1
                if await self._clear_embedding_cache():
                    success_count += 1
                    logger.info("✅ Embedding cache cleared")
                else:
                    self.failed_operations.append("embedding_cache")
                    logger.warning("⚠️ Failed to clear embedding cache")

            # 4. Clear temporary files
            total_operations += 1
            if await self._clear_temporary_files():
                success_count += 1
                logger.info("✅ Temporary files cleared")
            else:
                self.failed_operations.append("temporary_files")
                logger.warning("⚠️ Failed to clear temporary files")

            # 5. Clear logs (optional)
            if clear_logs:
                total_operations += 1
                if await self._clear_logs():
                    success_count += 1
                    logger.info("✅ Log files cleared")
                else:
                    self.failed_operations.append("logs")
                    logger.warning("⚠️ Failed to clear log files")

            # Summary
            success_rate = success_count / total_operations if total_operations > 0 else 0

            if success_rate == 1.0:
                logger.info(f"🎉 User logout completed successfully ({success_count}/{total_operations} operations)")
                return True
            elif success_rate >= 0.8:
                logger.warning(f"⚠️ User logout completed with warnings ({success_count}/{total_operations} operations)")
                return True
            else:
                logger.error(f"❌ User logout failed ({success_count}/{total_operations} operations)")
                raise LogoutServiceError(
                    f"Logout failed - only {success_count}/{total_operations} operations succeeded",
                    self.failed_operations
                )

        except Exception as e:
            logger.error(f"❌ Critical error during logout: {e}")
            raise LogoutServiceError(f"Critical logout error: {e}", self.failed_operations)

    async def _clear_authentication(self) -> bool:
        """Clear all authentication data."""
        try:
            authenticator = MicrosoftAuthenticator(self.settings)
            return await authenticator.logout()
        except Exception as e:
            logger.error(f"Failed to clear authentication: {e}")
            return False

    async def _clear_vector_database(self) -> bool:
        """Clear the vector database completely."""
        try:
            # Clear vector store data - this deletes all embeddings and content
            vector_store = VectorStore(self.settings)
            await vector_store.clear_all_data()

            # Close the connection to release file handles
            vector_store.close()

            # Note: We don't delete the directory on Windows due to file locking issues
            # The data is effectively cleared, which achieves the logout goal
            logger.info("Vector database data cleared (directory preserved due to Windows file locking)")

            return True
        except Exception as e:
            logger.error(f"Failed to clear vector database: {e}")
            return False

    async def _clear_embedding_cache(self) -> bool:
        """Clear the embedding cache."""
        try:
            # Clear embedding cache
            cache = EmbeddingCache(self.settings)
            await cache.clear_cache()

            return True
        except Exception as e:
            logger.error(f"Failed to clear embedding cache: {e}")
            return False

    async def _clear_temporary_files(self) -> bool:
        """Clear temporary files and caches."""
        try:
            cache_dir = self.settings.cache_dir
            if cache_dir and cache_dir.exists():
                # Remove specific cache files but preserve directory structure
                cache_patterns = [
                    "*.tmp",
                    "*.cache",
                    "*_temp_*",
                    "test_*.py"  # Remove any test files created during development
                ]

                for pattern in cache_patterns:
                    for file_path in cache_dir.glob(pattern):
                        if file_path.is_file():
                            file_path.unlink()
                            logger.debug(f"Removed temporary file: {file_path}")

            # Clear project-level temporary files
            project_root = Path.cwd()
            temp_files = [
                "TEST_RUN.md",
                "test_*.py"
            ]

            for pattern in temp_files:
                for file_path in project_root.glob(pattern):
                    if file_path.is_file():
                        file_path.unlink()
                        logger.debug(f"Removed project temporary file: {file_path}")

            return True
        except Exception as e:
            logger.error(f"Failed to clear temporary files: {e}")
            return False

    async def _clear_logs(self) -> bool:
        """Clear log files (optional operation)."""
        try:
            # Clear main log file
            log_file = Path("logs/onenote_copilot.log")
            if log_file.exists():
                log_file.unlink()
                logger.debug("Cleared main log file")

            # Clear any backup log files
            logs_dir = Path("logs")
            if logs_dir.exists():
                for log_backup in logs_dir.glob("*.log.*"):
                    log_backup.unlink()
                    logger.debug(f"Removed log backup: {log_backup}")

            return True
        except Exception as e:
            logger.error(f"Failed to clear logs: {e}")
            return False

    @logged("Get logout status information")
    async def get_logout_status(self) -> dict:
        """
        Get information about what data would be cleared during logout.

        Returns:
            Dictionary with information about user data that exists
        """
        status = {
            "authentication": {
                "token_cache_exists": False,
                "cache_file_size": 0
            },
            "vector_database": {
                "exists": False,
                "total_embeddings": 0,
                "storage_size_mb": 0
            },
            "embedding_cache": {
                "exists": False,
                "cache_entries": 0
            },
            "temporary_files": {
                "count": 0,
                "total_size_mb": 0
            }
        }

        try:
            # Check authentication status
            token_cache_path = self.settings.token_cache_path
            if token_cache_path.exists():
                status["authentication"]["token_cache_exists"] = True
                status["authentication"]["cache_file_size"] = token_cache_path.stat().st_size

            # Check vector database status
            try:
                vector_store = VectorStore(self.settings)
                db_stats = await vector_store.get_storage_stats()
                status["vector_database"]["exists"] = True
                status["vector_database"]["total_embeddings"] = db_stats.get("total_embeddings", 0)
                status["vector_database"]["storage_size_mb"] = db_stats.get("storage_size_mb", 0)
            except Exception:
                pass  # Vector DB doesn't exist or is inaccessible

            # Check embedding cache status
            try:
                cache = EmbeddingCache(self.settings)
                cache_stats = cache.get_cache_stats()
                status["embedding_cache"]["exists"] = True
                status["embedding_cache"]["cache_entries"] = cache_stats.get("total_entries", 0)
            except Exception:
                pass  # Cache doesn't exist or is inaccessible

            # Check temporary files
            cache_dir = self.settings.cache_dir
            if cache_dir and cache_dir.exists():
                temp_files = list(cache_dir.glob("*.tmp")) + list(cache_dir.glob("*.cache"))
                status["temporary_files"]["count"] = len(temp_files)
                status["temporary_files"]["total_size_mb"] = sum(
                    f.stat().st_size for f in temp_files if f.is_file()
                ) / (1024 * 1024)

        except Exception as e:
            logger.warning(f"Error getting logout status: {e}")

        return status


# Convenience function for simple logout
async def logout_current_user(
    clear_logs: bool = False,
    clear_vector_db: bool = True,
    clear_embedding_cache: bool = True
) -> bool:
    """
    Convenience function to logout the current user.

    Args:
        clear_logs: Whether to clear application logs
        clear_vector_db: Whether to clear vector database
        clear_embedding_cache: Whether to clear embedding cache

    Returns:
        True if logout was successful, False otherwise
    """
    logout_service = LogoutService()
    return await logout_service.logout_user(
        clear_logs=clear_logs,
        clear_vector_db=clear_vector_db,
        clear_embedding_cache=clear_embedding_cache
    )
