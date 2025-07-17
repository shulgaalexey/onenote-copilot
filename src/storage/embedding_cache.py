"""
Embedding cache service for OneNote content.

Provides persistent caching of embeddings to reduce API calls and improve
performance for semantic search operations.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.logging import log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import EmbeddedChunk

logger = logging.getLogger(__name__)


class EmbeddingCacheError(Exception):
    """Exception raised when embedding cache operations fail."""
    pass


class EmbeddingCache:
    """
    Persistent cache for content embeddings.

    Provides efficient storage and retrieval of embeddings with expiration
    and invalidation support to minimize API usage.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the embedding cache.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()

        # Cache configuration
        self.cache_dir = self.settings.vector_db_full_path / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.cache_file = self.cache_dir / "embedding_cache.json"
        self.metadata_file = self.cache_dir / "cache_metadata.json"

        # Performance tracking
        self._hits = 0
        self._misses = 0
        self._writes = 0

        # In-memory cache for frequently accessed embeddings
        self._memory_cache: Dict[str, EmbeddedChunk] = {}
        self._memory_cache_max_size = 100

    @logged("Load embedding from cache")
    async def get_embedding(self, content_hash: str) -> Optional[EmbeddedChunk]:
        """
        Get embedding from cache by content hash.

        Args:
            content_hash: Hash of the content to look up

        Returns:
            Cached embedded chunk if found, None otherwise
        """
        # Check memory cache first
        if content_hash in self._memory_cache:
            self._hits += 1
            logger.debug(f"Cache hit (memory) for {content_hash}")
            return self._memory_cache[content_hash]

        # Check persistent cache
        try:
            cache_data = await self._load_cache()

            if content_hash in cache_data:
                entry = cache_data[content_hash]

                # Check if entry is still valid
                if self._is_entry_valid(entry):
                    embedded_chunk = self._deserialize_embedded_chunk(entry["data"])

                    # Add to memory cache
                    self._add_to_memory_cache(content_hash, embedded_chunk)

                    self._hits += 1
                    logger.debug(f"Cache hit (disk) for {content_hash}")
                    return embedded_chunk
                else:
                    # Entry expired, remove it
                    logger.debug(f"Cache entry expired for {content_hash}")
                    await self._remove_entry(content_hash)

            self._misses += 1
            logger.debug(f"Cache miss for {content_hash}")
            return None

        except Exception as e:
            logger.error(f"Error reading from embedding cache: {e}")
            self._misses += 1
            return None

    @logged("Store embedding in cache")
    async def store_embedding(
        self,
        content_hash: str,
        embedded_chunk: EmbeddedChunk
    ) -> None:
        """
        Store embedding in cache.

        Args:
            content_hash: Hash of the content
            embedded_chunk: Embedded chunk to cache

        Raises:
            EmbeddingCacheError: If storage fails
        """
        try:
            # Add to memory cache
            self._add_to_memory_cache(content_hash, embedded_chunk)

            # Store in persistent cache
            cache_data = await self._load_cache()

            cache_entry = {
                "data": self._serialize_embedded_chunk(embedded_chunk),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "access_count": 1,
                "last_accessed": datetime.now(timezone.utc).isoformat()
            }

            cache_data[content_hash] = cache_entry

            await self._save_cache(cache_data)

            self._writes += 1
            logger.debug(f"Stored embedding in cache for {content_hash}")

        except Exception as e:
            logger.error(f"Error storing embedding in cache: {e}")
            raise EmbeddingCacheError(f"Failed to store embedding: {e}")

    @logged("Store multiple embeddings in cache")
    async def store_embeddings_batch(
        self,
        embeddings_map: Dict[str, EmbeddedChunk]
    ) -> None:
        """
        Store multiple embeddings in cache efficiently.

        Args:
            embeddings_map: Map of content hash to embedded chunk

        Raises:
            EmbeddingCacheError: If batch storage fails
        """
        if not embeddings_map:
            return

        start_time = time.time()

        try:
            cache_data = await self._load_cache()

            current_time = datetime.now(timezone.utc).isoformat()

            for content_hash, embedded_chunk in embeddings_map.items():
                # Add to memory cache
                self._add_to_memory_cache(content_hash, embedded_chunk)

                # Add to persistent cache
                cache_entry = {
                    "data": self._serialize_embedded_chunk(embedded_chunk),
                    "created_at": current_time,
                    "access_count": 1,
                    "last_accessed": current_time
                }

                cache_data[content_hash] = cache_entry

            await self._save_cache(cache_data)

            self._writes += len(embeddings_map)

            log_performance(
                "store_embeddings_batch",
                start_time,
                {
                    "embeddings_count": len(embeddings_map),
                    "cache_size": len(cache_data)
                }
            )

            logger.info(f"Stored {len(embeddings_map)} embeddings in cache")

        except Exception as e:
            logger.error(f"Error in batch embedding storage: {e}")
            raise EmbeddingCacheError(f"Failed to store embeddings batch: {e}")

    @logged("Remove embedding from cache")
    async def remove_embedding(self, content_hash: str) -> bool:
        """
        Remove embedding from cache.

        Args:
            content_hash: Hash of the content to remove

        Returns:
            True if embedding was removed, False if not found

        Raises:
            EmbeddingCacheError: If removal fails
        """
        try:
            # Remove from memory cache
            if content_hash in self._memory_cache:
                del self._memory_cache[content_hash]

            # Remove from persistent cache
            return await self._remove_entry(content_hash)

        except Exception as e:
            logger.error(f"Error removing embedding from cache: {e}")
            raise EmbeddingCacheError(f"Failed to remove embedding: {e}")

    @logged("Clear embedding cache")
    async def clear_cache(self) -> None:
        """
        Clear all cached embeddings.

        Raises:
            EmbeddingCacheError: If cache clearing fails
        """
        try:
            # Clear memory cache
            self._memory_cache.clear()

            # Clear persistent cache
            if self.cache_file.exists():
                self.cache_file.unlink()

            if self.metadata_file.exists():
                self.metadata_file.unlink()

            logger.info("Cleared embedding cache")

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            raise EmbeddingCacheError(f"Failed to clear cache: {e}")

    async def _load_cache(self) -> Dict[str, Any]:
        """Load cache data from disk."""
        try:
            if not self.cache_file.exists():
                return {}

            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load cache file: {e}")
            return {}

    async def _save_cache(self, cache_data: Dict[str, Any]) -> None:
        """Save cache data to disk."""
        try:
            # Write to temporary file first for atomic operation
            temp_file = self.cache_file.with_suffix('.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)

            # Atomic replace
            temp_file.replace(self.cache_file)

            # Update metadata
            await self._update_metadata(len(cache_data))

        except Exception as e:
            logger.error(f"Error saving cache: {e}")
            raise

    async def _remove_entry(self, content_hash: str) -> bool:
        """Remove a single entry from persistent cache."""
        try:
            cache_data = await self._load_cache()

            if content_hash in cache_data:
                del cache_data[content_hash]
                await self._save_cache(cache_data)
                return True

            return False

        except Exception as e:
            logger.error(f"Error removing cache entry: {e}")
            return False

    def _is_entry_valid(self, entry: Dict[str, Any]) -> bool:
        """Check if a cache entry is still valid."""
        # For now, embeddings don't expire (content-based cache)
        # Could add expiration logic here if needed
        return True

    def _serialize_embedded_chunk(self, embedded_chunk: EmbeddedChunk) -> Dict[str, Any]:
        """Serialize embedded chunk for storage."""
        return {
            "chunk": {
                "id": embedded_chunk.chunk.id,
                "page_id": embedded_chunk.chunk.page_id,
                "page_title": embedded_chunk.chunk.page_title,
                "content": embedded_chunk.chunk.content,
                "chunk_index": embedded_chunk.chunk.chunk_index,
                "start_position": embedded_chunk.chunk.start_position,
                "end_position": embedded_chunk.chunk.end_position,
                "metadata": embedded_chunk.chunk.metadata,
                "created_at": embedded_chunk.chunk.created_at.isoformat()
            },
            "embedding": embedded_chunk.embedding,
            "embedding_model": embedded_chunk.embedding_model,
            "embedding_dimensions": embedded_chunk.embedding_dimensions,
            "created_at": embedded_chunk.created_at.isoformat()
        }

    def _deserialize_embedded_chunk(self, data: Dict[str, Any]) -> EmbeddedChunk:
        """Deserialize embedded chunk from storage."""
        from ..models.onenote import ContentChunk

        chunk_data = data["chunk"]
        chunk = ContentChunk(
            id=chunk_data["id"],
            page_id=chunk_data["page_id"],
            page_title=chunk_data["page_title"],
            content=chunk_data["content"],
            chunk_index=chunk_data["chunk_index"],
            start_position=chunk_data["start_position"],
            end_position=chunk_data["end_position"],
            metadata=chunk_data["metadata"],
            created_at=datetime.fromisoformat(chunk_data["created_at"])
        )

        return EmbeddedChunk(
            chunk=chunk,
            embedding=data["embedding"],
            embedding_model=data["embedding_model"],
            embedding_dimensions=data["embedding_dimensions"],
            created_at=datetime.fromisoformat(data["created_at"])
        )

    def _add_to_memory_cache(self, content_hash: str, embedded_chunk: EmbeddedChunk) -> None:
        """Add embedding to memory cache with size limit."""
        # Remove oldest entry if cache is full
        if len(self._memory_cache) >= self._memory_cache_max_size:
            # Remove the first (oldest) entry
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]

        self._memory_cache[content_hash] = embedded_chunk

    async def _update_metadata(self, cache_size: int) -> None:
        """Update cache metadata."""
        try:
            metadata = {
                "cache_size": cache_size,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "hits": self._hits,
                "misses": self._misses,
                "writes": self._writes
            }

            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

        except Exception as e:
            logger.warning(f"Could not update cache metadata: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Dictionary with cache metrics
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "writes": self._writes,
            "hit_rate_percent": hit_rate,
            "memory_cache_size": len(self._memory_cache),
            "memory_cache_max_size": self._memory_cache_max_size,
            "cache_dir": str(self.cache_dir),
            "cache_file_exists": self.cache_file.exists(),
            "metadata_file_exists": self.metadata_file.exists()
        }
