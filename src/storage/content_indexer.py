"""
Content indexing service for OneNote pages.

Provides automated indexing of OneNote content for semantic search with
incremental updates and background processing capabilities.
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from ..config.logging import log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import EmbeddedChunk, OneNotePage
from ..search.content_chunker import ContentChunker
from ..search.embeddings import EmbeddingGenerator
from ..storage.embedding_cache import EmbeddingCache
from ..storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class ContentIndexerError(Exception):
    """Exception raised when content indexing operations fail."""
    pass


class ContentIndexer:
    """
    Automated content indexing for OneNote pages.

    Manages the process of converting OneNote content into searchable embeddings
    with incremental updates and efficient caching.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the content indexer.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()

        # Initialize components
        self.content_chunker = ContentChunker(self.settings)
        self.embedding_generator = EmbeddingGenerator(self.settings)
        self.vector_store = VectorStore(self.settings)
        self.embedding_cache = EmbeddingCache(self.settings)

        # Indexing state
        self._indexed_pages: Set[str] = set()
        self._page_hashes: Dict[str, str] = {}

        # Performance tracking
        self._pages_indexed = 0
        self._chunks_created = 0
        self._embeddings_generated = 0
        self._cache_hits = 0

    @logged("Index single OneNote page")
    async def index_page(
        self,
        page: OneNotePage,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Index a single OneNote page for semantic search.

        Args:
            page: OneNote page to index
            force_reindex: Force reindexing even if content hasn't changed

        Returns:
            Dictionary with indexing results

        Raises:
            ContentIndexerError: If indexing fails
        """
        if not page or not page.id:
            raise ContentIndexerError("Page must have a valid ID")

        start_time = time.time()
        page_id = page.id

        try:
            # Generate content hash to detect changes
            content_hash = self._generate_content_hash(page)

            # Check if page needs reindexing
            if not force_reindex and self._is_page_current(page_id, content_hash):
                logger.debug(f"Page '{page.title}' is already indexed and current")
                return {
                    "page_id": page_id,
                    "status": "skipped",
                    "reason": "already_current",
                    "chunks_created": 0,
                    "embeddings_generated": 0,
                    "cache_hits": 0
                }

            # Remove existing embeddings for this page
            deleted_count = await self.vector_store.delete_page_embeddings(page_id)
            if deleted_count > 0:
                logger.debug(f"Removed {deleted_count} existing embeddings for page '{page.title}'")

            # Chunk the page content
            chunks = self.content_chunker.chunk_page_content(page)

            if not chunks:
                logger.warning(f"No content chunks generated for page '{page.title}'")
                self._update_page_hash(page_id, content_hash)
                return {
                    "page_id": page_id,
                    "status": "completed",
                    "reason": "no_content",
                    "chunks_created": 0,
                    "embeddings_generated": 0,
                    "cache_hits": 0
                }

            # Optimize chunks for embeddings
            optimized_chunks = self.content_chunker.optimize_chunks_for_embeddings(chunks)

            # Process chunks with caching
            embedded_chunks = []
            cache_hits = 0
            embeddings_generated = 0

            for chunk in optimized_chunks:
                chunk_hash = self._generate_chunk_hash(chunk.content)

                # Try to get embedding from cache
                cached_embedding = await self.embedding_cache.get_embedding(chunk_hash)

                if cached_embedding and not force_reindex:
                    # Update chunk with page-specific information
                    updated_chunk = chunk
                    updated_chunk.id = chunk.id  # Keep new chunk ID

                    embedded_chunk = type(cached_embedding)(
                        chunk=updated_chunk,
                        embedding=cached_embedding.embedding,
                        embedding_model=cached_embedding.embedding_model,
                        embedding_dimensions=cached_embedding.embedding_dimensions,
                        created_at=cached_embedding.created_at
                    )
                    embedded_chunks.append(embedded_chunk)
                    cache_hits += 1
                else:
                    # Generate new embedding
                    chunk_embeddings = await self.embedding_generator.embed_content_chunks([chunk])

                    if chunk_embeddings:
                        embedded_chunk = chunk_embeddings[0]
                        embedded_chunks.append(embedded_chunk)

                        # Cache the embedding
                        await self.embedding_cache.store_embedding(chunk_hash, embedded_chunk)
                        embeddings_generated += 1

            # Store embeddings in vector database
            if embedded_chunks:
                await self.vector_store.store_embeddings(embedded_chunks)

            # Update tracking
            self._update_page_hash(page_id, content_hash)
            self._indexed_pages.add(page_id)
            self._pages_indexed += 1
            self._chunks_created += len(chunks)
            self._embeddings_generated += embeddings_generated
            self._cache_hits += cache_hits

            result = {
                "page_id": page_id,
                "status": "completed",
                "reason": "success",
                "chunks_created": len(chunks),
                "chunks_optimized": len(optimized_chunks),
                "embeddings_generated": embeddings_generated,
                "cache_hits": cache_hits,
                "total_embeddings": len(embedded_chunks)
            }

            log_performance(
                "index_page",
                start_time,
                {
                    **result,
                    "page_title": page.title,
                    "content_length": len(getattr(page, 'content', '') or '')
                }
            )

            logger.info(f"Indexed page '{page.title}': {len(embedded_chunks)} embeddings ({embeddings_generated} new, {cache_hits} cached)")
            return result

        except Exception as e:
            logger.error(f"Error indexing page '{getattr(page, 'title', 'Unknown')}': {e}")
            raise ContentIndexerError(f"Failed to index page: {e}")

    @logged("Index multiple OneNote pages")
    async def index_pages_batch(
        self,
        pages: List[OneNotePage],
        batch_size: int = 5,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Index multiple OneNote pages in batches.

        Args:
            pages: List of OneNote pages to index
            batch_size: Number of pages to process in each batch
            force_reindex: Force reindexing even if content hasn't changed

        Returns:
            Dictionary with batch indexing results

        Raises:
            ContentIndexerError: If batch indexing fails
        """
        if not pages:
            return {
                "total_pages": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "total_chunks": 0,
                "total_embeddings": 0,
                "total_cache_hits": 0,
                "results": []
            }

        start_time = time.time()
        results = []
        successful = 0
        failed = 0
        skipped = 0
        total_chunks = 0
        total_embeddings = 0
        total_cache_hits = 0

        # Process pages in batches
        for i in range(0, len(pages), batch_size):
            batch = pages[i:i + batch_size]

            logger.info(f"Processing batch {i // batch_size + 1}: pages {i + 1}-{min(i + batch_size, len(pages))} of {len(pages)}")

            # Process batch
            for page in batch:
                try:
                    result = await self.index_page(page, force_reindex=force_reindex)
                    results.append(result)

                    if result["status"] == "completed":
                        if result["reason"] == "success":
                            successful += 1
                        elif result["reason"] == "no_content":
                            successful += 1  # Count as successful but no content
                    elif result["status"] == "skipped":
                        skipped += 1

                    total_chunks += result.get("chunks_created", 0)
                    total_embeddings += result.get("total_embeddings", 0)
                    total_cache_hits += result.get("cache_hits", 0)

                except Exception as e:
                    logger.error(f"Failed to index page '{getattr(page, 'title', 'Unknown')}': {e}")
                    failed += 1
                    results.append({
                        "page_id": getattr(page, 'id', 'unknown'),
                        "status": "failed",
                        "reason": str(e),
                        "chunks_created": 0,
                        "embeddings_generated": 0,
                        "cache_hits": 0
                    })

            # Small delay between batches to respect API limits
            if i + batch_size < len(pages):
                await asyncio.sleep(0.5)

        batch_result = {
            "total_pages": len(pages),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "total_chunks": total_chunks,
            "total_embeddings": total_embeddings,
            "total_cache_hits": total_cache_hits,
            "results": results
        }

        log_performance(
            "index_pages_batch",
            start_time,
            {
                **batch_result,
                "batch_size": batch_size,
                "force_reindex": force_reindex
            }
        )

        logger.info(f"Batch indexing completed: {successful} successful, {failed} failed, {skipped} skipped out of {len(pages)} pages")
        return batch_result

    @logged("Check if page needs reindexing")
    def needs_reindexing(self, page: OneNotePage) -> bool:
        """
        Check if a page needs to be reindexed.

        Args:
            page: OneNote page to check

        Returns:
            True if page needs reindexing, False otherwise
        """
        if not page or not page.id:
            return False

        content_hash = self._generate_content_hash(page)
        return not self._is_page_current(page.id, content_hash)

    def _generate_content_hash(self, page: OneNotePage) -> str:
        """
        Generate a hash of page content for change detection.

        Args:
            page: OneNote page

        Returns:
            Content hash string
        """
        # Create hash based on content and last modified time
        content = getattr(page, 'content', '') or ''
        title = page.title or ''
        modified = page.last_modified_date_time.isoformat() if page.last_modified_date_time else ''

        hash_content = f"{title}|{content}|{modified}"
        return hashlib.sha256(hash_content.encode('utf-8')).hexdigest()[:16]

    def _generate_chunk_hash(self, content: str) -> str:
        """
        Generate a hash for chunk content for caching.

        Args:
            content: Chunk content

        Returns:
            Content hash string
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

    def _is_page_current(self, page_id: str, content_hash: str) -> bool:
        """
        Check if a page is current (hasn't changed since last indexing).

        Args:
            page_id: Page ID
            content_hash: Current content hash

        Returns:
            True if page is current, False otherwise
        """
        return (
            page_id in self._indexed_pages and
            page_id in self._page_hashes and
            self._page_hashes[page_id] == content_hash
        )

    def _update_page_hash(self, page_id: str, content_hash: str) -> None:
        """
        Update the stored hash for a page.

        Args:
            page_id: Page ID
            content_hash: New content hash
        """
        self._page_hashes[page_id] = content_hash

    @logged("Get content indexer statistics")
    async def get_indexing_stats(self) -> Dict[str, Any]:
        """
        Get indexing statistics and status.

        Returns:
            Dictionary with indexing metrics
        """
        # Get vector store stats
        vector_stats = await self.vector_store.get_storage_stats()

        # Get cache stats
        cache_stats = self.embedding_cache.get_cache_stats()

        # Get embedding generator stats
        embedding_stats = self.embedding_generator.get_usage_stats()

        return {
            "indexer_stats": {
                "pages_indexed": self._pages_indexed,
                "total_indexed_pages": len(self._indexed_pages),
                "chunks_created": self._chunks_created,
                "embeddings_generated": self._embeddings_generated,
                "cache_hits": self._cache_hits
            },
            "vector_store_stats": {
                "total_embeddings": vector_stats.total_embeddings,
                "total_pages_indexed": vector_stats.total_pages_indexed,
                "storage_size_mb": vector_stats.storage_size_mb
            },
            "cache_stats": cache_stats,
            "embedding_stats": embedding_stats,
            "settings": {
                "chunk_size": self.settings.chunk_size,
                "chunk_overlap": self.settings.chunk_overlap,
                "max_chunks_per_page": self.settings.max_chunks_per_page,
                "embedding_model": self.settings.embedding_model,
                "cache_embeddings": self.settings.cache_embeddings
            }
        }

    @logged("Reset indexer state")
    async def reset_indexer(self) -> None:
        """
        Reset the indexer state and clear all indexed content.

        Raises:
            ContentIndexerError: If reset fails
        """
        try:
            # Clear vector store
            await self.vector_store.reset_storage()

            # Clear embedding cache
            await self.embedding_cache.clear_cache()

            # Reset internal state
            self._indexed_pages.clear()
            self._page_hashes.clear()
            self._pages_indexed = 0
            self._chunks_created = 0
            self._embeddings_generated = 0
            self._cache_hits = 0

            logger.info("Content indexer reset successfully")

        except Exception as e:
            logger.error(f"Failed to reset content indexer: {e}")
            raise ContentIndexerError(f"Failed to reset indexer: {e}")

    def get_indexed_pages(self) -> Set[str]:
        """
        Get set of indexed page IDs.

        Returns:
            Set of page IDs that have been indexed
        """
        return self._indexed_pages.copy()

    async def store_page_embeddings(self, page_id: str, embedded_chunks: List[EmbeddedChunk]) -> None:
        """
        Store embeddings for a page directly in the vector database.

        Args:
            page_id: The OneNote page ID
            embedded_chunks: List of embedded chunks with metadata

        Raises:
            ContentIndexerError: If storage fails
        """
        try:
            logger.debug(f"Storing {len(embedded_chunks)} embeddings for page {page_id}")

            # Store embeddings in vector store
            await self.vector_store.store_embeddings(embedded_chunks)

            # Update tracking
            self._indexed_pages.add(page_id)
            self._chunks_created += len(embedded_chunks)

            logger.info(f"Successfully stored {len(embedded_chunks)} embeddings for page {page_id}")

        except Exception as e:
            logger.error(f"Failed to store embeddings for page {page_id}: {e}")
            raise ContentIndexerError(f"Failed to store embeddings: {e}")
