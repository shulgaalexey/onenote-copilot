"""
Embedding generation service for OneNote content.

Provides OpenAI embeddings generation with batching, caching, and error handling.
Optimized for OneNote content processing with rate limiting and retry logic.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import openai
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.logging import log_api_call, log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import ContentChunk, EmbeddedChunk

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict[str, Any]] = None):
        """
        Initialize EmbeddingError with optional context.

        Args:
            message: Error message
            status_code: Optional HTTP status code
            response_data: Optional response data from API
        """
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class EmbeddingGenerator:
    """
    OpenAI embeddings generation service.

    Handles embedding generation for OneNote content with batching,
    caching, rate limiting, and comprehensive error handling.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the embedding generator.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()

        # Initialize OpenAI client with validation
        try:
            api_key = self.settings.openai_api_key.get_secret_value()
            if not api_key or api_key.strip() == "":
                raise ValueError("OpenAI API key is empty or not set")

            self.client = openai.AsyncOpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self.client = None

        # Performance tracking
        self._api_call_count = 0
        self._total_tokens_used = 0
        self._cache_hits = 0
        self._cache_misses = 0

    @logged("Generate embedding for content")
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def generate_embedding(self, content: str) -> List[float]:
        """
        Generate embedding for a single piece of content.

        Args:
            content: Text content to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not content.strip():
            raise EmbeddingError("Cannot generate embedding for empty content")

        if self.client is None:
            raise EmbeddingError("OpenAI client is not initialized. Please check your API key configuration.")

        start_time = time.time()

        try:
            # Log the API call start
            log_api_call("POST", f"OpenAI Embeddings API ({content[:50]}...)")

            response = await self.client.embeddings.create(
                input=content,
                model=self.settings.embedding_model,
                dimensions=self.settings.embedding_dimensions
            )

            self._api_call_count += 1
            self._total_tokens_used += response.usage.total_tokens

            embedding = response.data[0].embedding

            # Calculate duration and log performance
            duration = time.time() - start_time
            log_performance(
                "generate_embedding",
                duration,
                content_length=len(content),
                embedding_dimensions=len(embedding),
                tokens_used=response.usage.total_tokens,
                model=self.settings.embedding_model
            )

            return embedding

        except openai.APIError as e:
            logger.error(f"OpenAI API error generating embedding: {e}")
            raise EmbeddingError(f"API error: {e}", status_code=getattr(e, 'status_code', None))
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit, retrying: {e}")
            raise EmbeddingError(f"Rate limit error: {e}", status_code=429)
        except Exception as e:
            logger.error(f"Unexpected error generating embedding: {e}")
            raise EmbeddingError(f"Unexpected error: {e}")

    @logged("Generate embeddings for batch")
    async def batch_generate_embeddings(self, contents: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple pieces of content in batches.

        Args:
            contents: List of text content to embed

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingError: If batch generation fails
        """
        if not contents:
            return []

        # Filter out empty content
        valid_contents = [content for content in contents if content.strip()]
        if not valid_contents:
            raise EmbeddingError("No valid content provided for embedding")

        batch_size = self.settings.embedding_batch_size
        all_embeddings = []

        # Process in batches to respect API limits
        for i in range(0, len(valid_contents), batch_size):
            batch = valid_contents[i:i + batch_size]

            start_time = time.time()

            try:
                with log_api_call("openai_embedding_batch", f"{len(batch)} items"):
                    response = await self.client.embeddings.create(
                        input=batch,
                        model=self.settings.embedding_model,
                        dimensions=self.settings.embedding_dimensions
                    )

                    self._api_call_count += 1
                    self._total_tokens_used += response.usage.total_tokens

                    batch_embeddings = [data.embedding for data in response.data]
                    all_embeddings.extend(batch_embeddings)

                    duration = time.time() - start_time
                    log_performance(
                        "batch_generate_embeddings",
                        duration,
                        batch_size=len(batch),
                        total_items=len(valid_contents),
                        tokens_used=response.usage.total_tokens,
                        model=self.settings.embedding_model
                    )

                    # Rate limiting between batches
                    if i + batch_size < len(valid_contents):
                        await asyncio.sleep(0.1)

            except openai.APIError as e:
                logger.error(f"OpenAI API error in batch embedding: {e}")
                raise EmbeddingError(f"Batch API error: {e}", status_code=getattr(e, 'status_code', None))
            except Exception as e:
                logger.error(f"Unexpected error in batch embedding: {e}")
                raise EmbeddingError(f"Unexpected batch error: {e}")

        return all_embeddings

    @logged("Generate embeddings for content chunks")
    async def embed_content_chunks(self, chunks: List[ContentChunk]) -> List[EmbeddedChunk]:
        """
        Generate embeddings for a list of content chunks.

        Args:
            chunks: List of content chunks to embed

        Returns:
            List of embedded chunks with vectors

        Raises:
            EmbeddingError: If chunk embedding fails
        """
        if not chunks:
            return []

        start_time = time.time()

        # Extract content from chunks
        contents = [chunk.content for chunk in chunks]

        try:
            # Generate embeddings in batches
            embeddings = await self.batch_generate_embeddings(contents)

            # Create embedded chunks
            embedded_chunks = []
            for chunk, embedding in zip(chunks, embeddings):
                embedded_chunk = EmbeddedChunk(
                    chunk=chunk,
                    embedding=embedding,
                    embedding_model=self.settings.embedding_model,
                    embedding_dimensions=len(embedding)
                )
                embedded_chunks.append(embedded_chunk)

            duration = time.time() - start_time
            log_performance(
                "embed_content_chunks",
                duration,
                chunks_processed=len(chunks),
                total_embeddings=len(embeddings),
                average_content_length=sum(len(c.content) for c in chunks) / len(chunks)
            )

            return embedded_chunks

        except EmbeddingError:
            raise
        except Exception as e:
            logger.error(f"Error embedding content chunks: {e}")
            raise EmbeddingError(f"Chunk embedding error: {e}")

    @logged("Generate query embedding")
    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Query embedding vector

        Raises:
            EmbeddingError: If query embedding fails
        """
        if not query.strip():
            raise EmbeddingError("Cannot generate embedding for empty query")

        try:
            return await self.generate_embedding(query.strip())
        except EmbeddingError:
            raise
        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            raise EmbeddingError(f"Query embedding error: {e}")

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for the embedding generator.

        Returns:
            Dictionary with usage metrics
        """
        return {
            "api_calls": self._api_call_count,
            "total_tokens": self._total_tokens_used,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses) * 100
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
            "model": self.settings.embedding_model,
            "dimensions": self.settings.embedding_dimensions
        }

    async def test_connection(self) -> bool:
        """
        Test the connection to OpenAI embeddings API.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            test_embedding = await self.generate_embedding("test connection")
            return len(test_embedding) == self.settings.embedding_dimensions
        except Exception as e:
            logger.error(f"Embedding API connection test failed: {e}")
            return False
