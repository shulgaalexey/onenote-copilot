"""
Semantic search engine for OneNote content.

Provides intelligent content search using vector embeddings and hybrid
search combining semantic similarity with keyword matching.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..config.logging import log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import (HybridSearchResult, OneNotePage, SearchResult,
                              SemanticSearchResult)
from ..storage.vector_store import VectorStore
from ..tools.onenote_search import OneNoteSearchTool
from .content_chunker import ContentChunker
from .embeddings import EmbeddingGenerator
from .query_processor import QueryProcessor
from .relevance_ranker import RelevanceRanker

logger = logging.getLogger(__name__)


class SemanticSearchError(Exception):
    """Exception raised when semantic search operations fail."""
    pass


class SemanticSearchEngine:
    """
    Intelligent semantic search engine for OneNote content.

    Combines vector-based semantic search with traditional keyword search
    for optimal content discovery and relevance ranking.
    """

    def __init__(
        self,
        search_tool: OneNoteSearchTool,
        settings: Optional[Any] = None
    ):
        """
        Initialize the semantic search engine.

        Args:
            search_tool: OneNote search tool for keyword search
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()
        self.search_tool = search_tool

        # Initialize semantic search components
        self.embedding_generator = EmbeddingGenerator(self.settings)
        self.vector_store = VectorStore(self.settings)
        self.content_chunker = ContentChunker(self.settings)
        self.query_processor = QueryProcessor(self.settings)
        self.relevance_ranker = RelevanceRanker(self.settings)

        # Performance tracking
        self._search_count = 0
        self._hybrid_search_count = 0

    @logged("Perform semantic search")
    async def semantic_search(
        self,
        query: str,
        limit: int = None,
        threshold: float = None
    ) -> List[SemanticSearchResult]:
        """
        Perform semantic search on OneNote content.

        Args:
            query: Search query
            limit: Maximum number of results (uses setting default if None)
            threshold: Minimum similarity threshold (uses setting default if None)

        Returns:
            List of semantic search results

        Raises:
            SemanticSearchError: If search fails
        """
        if not query.strip():
            raise SemanticSearchError("Search query cannot be empty")

        limit = limit or self.settings.semantic_search_limit
        threshold = threshold or self.settings.semantic_search_threshold

        start_time = time.time()

        try:
            # Process the query
            processed_query = await self.query_processor.process_query(query)

            # Generate query embedding
            query_embedding = await self.embedding_generator.embed_query(processed_query.processed_query)

            # Search for similar embeddings
            search_results = await self.vector_store.search_similar(
                query_embedding=query_embedding,
                limit=limit,
                threshold=threshold
            )

            # Rank and enhance results
            ranked_results = await self.relevance_ranker.rank_semantic_results(
                search_results,
                processed_query
            )

            self._search_count += 1

            log_performance(
                "semantic_search",
                time.time() - start_time,
                query_length=len(query),
                processed_query_length=len(processed_query.processed_query),
                results_found=len(ranked_results),
                threshold=threshold,
                limit=limit
            )

            logger.info(f"Semantic search for '{query}' found {len(ranked_results)} results")
            return ranked_results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            raise SemanticSearchError(f"Search failed: {e}")

    @logged("Perform hybrid search")
    async def hybrid_search(
        self,
        query: str,
        limit: int = None,
        semantic_weight: float = None
    ) -> HybridSearchResult:
        """
        Perform hybrid search combining semantic and keyword search.

        Args:
            query: Search query
            limit: Maximum number of results (uses setting default if None)
            semantic_weight: Weight for semantic vs keyword results (uses setting default if None)

        Returns:
            Hybrid search result with combined rankings

        Raises:
            SemanticSearchError: If hybrid search fails
        """
        if not query.strip():
            raise SemanticSearchError("Search query cannot be empty")

        limit = limit or self.settings.semantic_search_limit
        semantic_weight = semantic_weight or self.settings.hybrid_search_weight
        keyword_weight = 1.0 - semantic_weight

        start_time = time.time()

        try:
            # Run semantic and keyword searches in parallel
            semantic_task = asyncio.create_task(
                self.semantic_search(query, limit=limit * 2)  # Get more semantic results for merging
            )

            keyword_task = asyncio.create_task(
                self._keyword_search(query, limit=limit * 2)  # Get more keyword results for merging
            )

            # Wait for both searches to complete
            semantic_results, keyword_results = await asyncio.gather(
                semantic_task, keyword_task, return_exceptions=True
            )

            # Handle exceptions
            if isinstance(semantic_results, Exception):
                logger.warning(f"Semantic search failed, using keyword only: {semantic_results}")
                semantic_results = []

            if isinstance(keyword_results, Exception):
                logger.warning(f"Keyword search failed, using semantic only: {keyword_results}")
                keyword_results = []

            # Combine and rank results
            combined_results = await self.relevance_ranker.combine_hybrid_results(
                semantic_results=semantic_results,
                keyword_results=keyword_results,
                semantic_weight=semantic_weight,
                keyword_weight=keyword_weight,
                limit=limit
            )

            hybrid_result = HybridSearchResult(
                semantic_results=semantic_results[:limit],
                keyword_results=keyword_results[:limit],
                combined_results=combined_results,
                semantic_weight=semantic_weight,
                keyword_weight=keyword_weight,
                total_results=len(combined_results),
                search_strategy="hybrid_weighted"
            )

            self._hybrid_search_count += 1

            log_performance(
                "hybrid_search",
                time.time() - start_time,
                query_length=len(query),
                semantic_results=len(semantic_results) if not isinstance(semantic_results, Exception) else 0,
                keyword_results=len(keyword_results) if not isinstance(keyword_results, Exception) else 0,
                combined_results=len(combined_results),
                semantic_weight=semantic_weight,
                limit=limit
            )

            logger.info(f"Hybrid search for '{query}' found {len(combined_results)} combined results")
            return hybrid_result

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise SemanticSearchError(f"Hybrid search failed: {e}")

    async def _keyword_search(self, query: str, limit: int) -> List[SearchResult]:
        """
        Perform keyword search using the OneNote search tool.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of keyword search results
        """
        try:
            # Use the existing OneNote search tool
            search_result = await self.search_tool.search_pages(query, max_results=limit)
            return [search_result] if search_result.pages else []
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    @logged("Index OneNote page content")
    async def index_page(self, page: OneNotePage) -> int:
        """
        Index a single OneNote page for semantic search.

        Args:
            page: OneNote page to index

        Returns:
            Number of chunks created and indexed

        Raises:
            SemanticSearchError: If indexing fails
        """
        if not page or not page.id:
            raise SemanticSearchError("Page must have a valid ID")

        start_time = time.time()

        try:
            # Delete existing embeddings for this page
            await self.vector_store.delete_page_embeddings(page.id)

            # Chunk the page content
            chunks = self.content_chunker.chunk_page_content(page)

            if not chunks:
                logger.warning(f"No chunks generated for page '{page.title}'")
                return 0

            # Optimize chunks for embeddings
            optimized_chunks = self.content_chunker.optimize_chunks_for_embeddings(chunks)

            # Generate embeddings for chunks
            embedded_chunks = await self.embedding_generator.embed_content_chunks(optimized_chunks)

            # Store embeddings in vector database
            await self.vector_store.store_embeddings(embedded_chunks)

            log_performance(
                "index_page",
                time.time() - start_time,
                page_id=page.id,
                page_title=page.title,
                chunks_created=len(chunks),
                chunks_optimized=len(optimized_chunks),
                embeddings_stored=len(embedded_chunks)
            )

            logger.info(f"Indexed page '{page.title}' with {len(embedded_chunks)} chunks")
            return len(embedded_chunks)

        except Exception as e:
            logger.error(f"Error indexing page '{getattr(page, 'title', 'Unknown')}': {e}")
            raise SemanticSearchError(f"Failed to index page: {e}")

    @logged("Index multiple OneNote pages")
    async def index_pages(self, pages: List[OneNotePage]) -> Dict[str, int]:
        """
        Index multiple OneNote pages for semantic search.

        Args:
            pages: List of OneNote pages to index

        Returns:
            Dictionary mapping page IDs to number of chunks indexed

        Raises:
            SemanticSearchError: If indexing fails
        """
        if not pages:
            return {}

        start_time = time.time()
        results = {}

        # Index pages in batches to manage memory and API limits
        batch_size = 5  # Process 5 pages at a time

        for i in range(0, len(pages), batch_size):
            batch = pages[i:i + batch_size]

            # Process batch
            for page in batch:
                try:
                    chunk_count = await self.index_page(page)
                    results[page.id] = chunk_count
                except Exception as e:
                    logger.error(f"Failed to index page '{getattr(page, 'title', 'Unknown')}': {e}")
                    results[page.id] = 0

            # Small delay between batches to respect API limits
            if i + batch_size < len(pages):
                await asyncio.sleep(0.5)

        total_chunks = sum(results.values())

        log_performance(
            "index_pages",
            time.time() - start_time,
            pages_processed=len(pages),
            pages_successful=len([r for r in results.values() if r > 0]),
            total_chunks=total_chunks,
            average_chunks_per_page=total_chunks / len(pages) if pages else 0
        )

        logger.info(f"Indexed {len(pages)} pages with {total_chunks} total chunks")
        return results

    @logged("Search with auto-fallback")
    async def search_with_fallback(
        self,
        query: str,
        limit: int = None,
        prefer_semantic: bool = None
    ) -> List[SemanticSearchResult]:
        """
        Search with automatic fallback from semantic to keyword search.

        Args:
            query: Search query
            limit: Maximum number of results
            prefer_semantic: Whether to prefer semantic search (uses hybrid setting default if None)

        Returns:
            List of search results

        Raises:
            SemanticSearchError: If all search methods fail
        """
        limit = limit or self.settings.semantic_search_limit
        prefer_semantic = prefer_semantic if prefer_semantic is not None else self.settings.enable_hybrid_search

        try:
            if prefer_semantic:
                # Try hybrid search first
                try:
                    hybrid_result = await self.hybrid_search(query, limit=limit)
                    if hybrid_result.combined_results:
                        return hybrid_result.combined_results
                except Exception as e:
                    logger.warning(f"Hybrid search failed, trying semantic only: {e}")

                # Try semantic search
                try:
                    semantic_results = await self.semantic_search(query, limit=limit)
                    if semantic_results:
                        return semantic_results
                except Exception as e:
                    logger.warning(f"Semantic search failed, trying keyword: {e}")

            # Fallback to keyword search
            try:
                keyword_results = await self._keyword_search(query, limit=limit)
                if keyword_results and keyword_results[0].pages:
                    # Convert keyword results to semantic format
                    semantic_results = []
                    for i, page in enumerate(keyword_results[0].pages[:limit]):
                        # Create a simple chunk from page content
                        from ..models.onenote import ContentChunk
                        chunk = ContentChunk(
                            id=f"{page.id}_keyword",
                            page_id=page.id,
                            page_title=page.title,
                            content=getattr(page, 'processed_content', page.content) or page.title,
                            chunk_index=0,
                            start_position=0,
                            end_position=len(page.title)
                        )

                        result = SemanticSearchResult(
                            chunk=chunk,
                            similarity_score=0.8 - (i * 0.1),  # Decreasing score
                            search_type="keyword_fallback",
                            rank=i + 1,
                            page=page
                        )
                        semantic_results.append(result)

                    return semantic_results
            except Exception as e:
                logger.error(f"Keyword search fallback failed: {e}")

            # No results found
            logger.warning(f"All search methods failed for query: {query}")
            return []

        except Exception as e:
            logger.error(f"Search with fallback failed: {e}")
            raise SemanticSearchError(f"All search methods failed: {e}")

    def get_search_stats(self) -> Dict[str, Any]:
        """
        Get search engine statistics.

        Returns:
            Dictionary with search metrics
        """
        return {
            "total_searches": self._search_count,
            "hybrid_searches": self._hybrid_search_count,
            "embedding_stats": self.embedding_generator.get_usage_stats(),
            "vector_store_stats": self.vector_store.get_operation_stats(),
            "settings": {
                "semantic_threshold": self.settings.semantic_search_threshold,
                "hybrid_weight": self.settings.hybrid_search_weight,
                "chunk_size": self.settings.chunk_size,
                "embedding_model": self.settings.embedding_model
            }
        }

    async def reset_index(self) -> None:
        """
        Reset the semantic search index.

        Raises:
            SemanticSearchError: If reset fails
        """
        try:
            await self.vector_store.reset_storage()
            logger.info("Semantic search index reset successfully")
        except Exception as e:
            logger.error(f"Failed to reset semantic search index: {e}")
            raise SemanticSearchError(f"Failed to reset index: {e}")
