"""
Vector storage service using ChromaDB.

Provides efficient storage and retrieval of embeddings with metadata
for semantic search capabilities in OneNote Copilot.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings

from ..config.logging import log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import EmbeddedChunk, SemanticSearchResult, StorageStats

logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    """Exception raised when vector store operations fail."""
    pass


class VectorStore:
    """
    ChromaDB-based vector storage for OneNote content embeddings.

    Provides persistent storage and efficient similarity search for
    content embeddings with metadata support.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the vector store.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()
        self.db_path = self.settings.vector_db_full_path
        self.collection_name = self.settings.vector_db_collection_name

        # Ensure database directory exists
        self.db_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self._client = None
        self._collection = None

        # Performance tracking
        self._operation_count = 0

    @property
    def client(self) -> chromadb.ClientAPI:
        """Get or create ChromaDB client."""
        if self._client is None:
            try:
                self._client = chromadb.PersistentClient(
                    path=str(self.db_path),
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                        allow_reset=True  # Allow collection reset operations
                    )
                )
                logger.info(f"Initialized ChromaDB client at {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB client: {e}")
                raise VectorStoreError(f"Cannot initialize vector store: {e}")
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        """Get or create ChromaDB collection."""
        if self._collection is None:
            try:
                # Try to get existing collection first
                try:
                    self._collection = self.client.get_collection(
                        name=self.collection_name
                    )
                    logger.info(f"Loaded existing collection '{self.collection_name}'")
                except Exception:
                    # Create new collection if it doesn't exist
                    self._collection = self.client.create_collection(
                        name=self.collection_name,
                        metadata={"description": "OneNote content embeddings"}
                    )
                    logger.info(f"Created new collection '{self.collection_name}'")
            except Exception as e:
                logger.error(f"Failed to get/create collection: {e}")
                raise VectorStoreError(f"Cannot access collection: {e}")
        return self._collection

    @logged("Store embeddings in vector database")
    async def store_embeddings(self, embedded_chunks: List[EmbeddedChunk]) -> None:
        """
        Store embedded chunks in the vector database.

        Args:
            embedded_chunks: List of embedded chunks to store

        Raises:
            VectorStoreError: If storage fails
        """
        if not embedded_chunks:
            logger.warning("No embedded chunks provided for storage")
            return

        start_time = time.time()

        try:
            # Prepare data for ChromaDB
            ids = []
            embeddings = []
            metadatas = []
            documents = []

            for embedded_chunk in embedded_chunks:
                chunk = embedded_chunk.chunk

                # Use chunk ID as document ID
                ids.append(chunk.id)
                embeddings.append(embedded_chunk.embedding)
                documents.append(chunk.content)

                # Prepare metadata (ChromaDB requires string values)
                metadata = {
                    "page_id": chunk.page_id,
                    "page_title": chunk.page_title,
                    "chunk_index": chunk.chunk_index,
                    "start_position": chunk.start_position,
                    "end_position": chunk.end_position,
                    "embedding_model": embedded_chunk.embedding_model,
                    "embedding_dimensions": embedded_chunk.embedding_dimensions,
                    "created_at": embedded_chunk.created_at.isoformat(),
                }

                # Add chunk metadata if available
                if chunk.metadata:
                    for key, value in chunk.metadata.items():
                        if isinstance(value, (str, int, float, bool)):
                            metadata[f"chunk_{key}"] = str(value)

                metadatas.append(metadata)

            # Store in ChromaDB (using upsert to handle duplicates)
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )

            self._operation_count += 1

            duration = time.time() - start_time
            log_performance(
                "store_embeddings",
                duration,
                chunks_stored=len(embedded_chunks),
                collection_name=self.collection_name,
                embedding_dimensions=embedded_chunks[0].embedding_dimensions if embedded_chunks else 0
            )

            logger.info(f"Stored {len(embedded_chunks)} embeddings in collection '{self.collection_name}'")

        except Exception as e:
            logger.error(f"Error storing embeddings: {e}")
            raise VectorStoreError(f"Failed to store embeddings: {e}")

    @logged("Search similar embeddings")
    async def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 10,
        threshold: float = 0.0,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SemanticSearchResult]:
        """
        Search for similar embeddings using cosine similarity.

        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results to return
            threshold: Minimum similarity threshold
            filter_metadata: Optional metadata filters

        Returns:
            List of semantic search results

        Raises:
            VectorStoreError: If search fails
        """
        if not query_embedding:
            raise VectorStoreError("Query embedding cannot be empty")

        start_time = time.time()

        try:
            # Prepare query parameters
            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": limit
            }

            # Add metadata filter if provided
            if filter_metadata:
                query_params["where"] = filter_metadata

            # Perform similarity search
            results = self.collection.query(**query_params)

            # Process results
            search_results = []

            if results["ids"] and results["ids"][0]:
                ids = results["ids"][0]
                distances = results["distances"][0] if results["distances"] else [0.0] * len(ids)
                metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
                documents = results["documents"][0] if results["documents"] else [""] * len(ids)

                for rank, (chunk_id, distance, metadata, document) in enumerate(zip(ids, distances, metadatas, documents)):
                    # Convert distance to similarity score (ChromaDB returns squared Euclidean distance)
                    similarity_score = max(0.0, 1.0 - distance)

                    # Apply threshold filter
                    if similarity_score < threshold:
                        continue

                    # Create ContentChunk from stored data
                    from ..models.onenote import ContentChunk
                    chunk = ContentChunk(
                        id=chunk_id,
                        page_id=metadata.get("page_id", ""),
                        page_title=metadata.get("page_title", ""),
                        content=document,
                        chunk_index=int(metadata.get("chunk_index", 0)),
                        start_position=int(metadata.get("start_position", 0)),
                        end_position=int(metadata.get("end_position", 0)),
                        metadata={k.replace("chunk_", ""): v for k, v in metadata.items() if k.startswith("chunk_")}
                    )

                    search_result = SemanticSearchResult(
                        chunk=chunk,
                        similarity_score=similarity_score,
                        search_type="semantic",
                        rank=rank + 1
                    )
                    search_results.append(search_result)

            self._operation_count += 1

            duration = time.time() - start_time
            log_performance(
                "search_similar",
                duration,
                query_dimensions=len(query_embedding),
                results_found=len(search_results),
                limit=limit,
                threshold=threshold,
                collection_name=self.collection_name
            )

            logger.info(f"Found {len(search_results)} similar embeddings (threshold: {threshold})")
            return search_results

        except Exception as e:
            logger.error(f"Error searching similar embeddings: {e}")
            raise VectorStoreError(f"Failed to search embeddings: {e}")

    @logged("Delete page embeddings")
    async def delete_page_embeddings(self, page_id: str) -> int:
        """
        Delete all embeddings for a specific page.

        Args:
            page_id: OneNote page ID

        Returns:
            Number of embeddings deleted

        Raises:
            VectorStoreError: If deletion fails
        """
        if not page_id:
            raise VectorStoreError("Page ID cannot be empty")

        try:
            # Query for all chunks belonging to this page
            results = self.collection.get(
                where={"page_id": page_id}
            )

            if not results["ids"]:
                logger.info(f"No embeddings found for page {page_id}")
                return 0

            # Delete the embeddings
            self.collection.delete(ids=results["ids"])

            deleted_count = len(results["ids"])
            self._operation_count += 1

            logger.info(f"Deleted {deleted_count} embeddings for page {page_id}")
            return deleted_count

        except Exception as e:
            logger.error(f"Error deleting page embeddings: {e}")
            raise VectorStoreError(f"Failed to delete page embeddings: {e}")

    @logged("Get vector storage statistics")
    async def get_storage_stats(self) -> StorageStats:
        """
        Get statistics about the vector storage.

        Returns:
            Storage statistics

        Raises:
            VectorStoreError: If stats retrieval fails
        """
        try:
            # Get collection count
            count_result = self.collection.count()
            total_embeddings = count_result if isinstance(count_result, int) else 0

            # Get unique pages
            all_metadata = self.collection.get(include=["metadatas"])
            unique_pages = set()

            if all_metadata["metadatas"]:
                for metadata in all_metadata["metadatas"]:
                    if metadata and "page_id" in metadata:
                        unique_pages.add(metadata["page_id"])

            # Calculate storage size (approximate)
            storage_size_mb = 0.0
            try:
                # Calculate size of database directory
                for file_path in self.db_path.rglob("*"):
                    if file_path.is_file():
                        storage_size_mb += file_path.stat().st_size
                storage_size_mb = storage_size_mb / (1024 * 1024)  # Convert to MB
            except Exception as e:
                logger.warning(f"Could not calculate storage size: {e}")

            # Get embedding dimensions from first record
            embedding_dimensions = self.settings.embedding_dimensions
            if total_embeddings > 0:
                try:
                    sample_result = self.collection.get(limit=1, include=["metadatas"])
                    if sample_result["metadatas"] and sample_result["metadatas"][0]:
                        metadata = sample_result["metadatas"][0]
                        if "embedding_dimensions" in metadata:
                            embedding_dimensions = int(metadata["embedding_dimensions"])
                except Exception:
                    pass

            return StorageStats(
                total_embeddings=total_embeddings,
                total_chunks=total_embeddings,  # Same as embeddings
                total_pages_indexed=len(unique_pages),
                embedding_dimensions=embedding_dimensions,
                storage_size_mb=storage_size_mb,
                cache_hit_rate=0.0  # Will be updated by cache layer
            )

        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            raise VectorStoreError(f"Failed to get storage stats: {e}")

    @logged("Reset vector store")
    async def reset_storage(self) -> None:
        """
        Reset the vector storage by deleting all data.

        Raises:
            VectorStoreError: If reset fails
        """
        try:
            # Try to delete existing collection
            try:
                self.client.delete_collection(self.collection_name)
                logger.info(f"Deleted existing collection '{self.collection_name}'")
            except Exception as e:
                # Collection might not exist, which is fine
                logger.debug(f"Collection deletion not needed or failed: {e}")

            # Reset internal references
            self._collection = None

            # Create new empty collection
            try:
                self._collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "OneNote content embeddings"}
                )
                logger.info(f"Created new collection '{self.collection_name}'")
            except Exception as e:
                # If creation fails due to existing collection, try to get it
                if "already exists" in str(e).lower():
                    logger.info(f"Collection '{self.collection_name}' already exists, getting existing one")
                    self._collection = self.client.get_collection(self.collection_name)
                else:
                    raise e

            logger.info(f"Reset vector store collection '{self.collection_name}'")

        except Exception as e:
            logger.error(f"Error resetting vector store: {e}")
            raise VectorStoreError(f"Failed to reset vector store: {e}")

    def get_operation_stats(self) -> Dict[str, Any]:
        """
        Get operation statistics for the vector store.

        Returns:
            Dictionary with operation metrics
        """
        return {
            "total_operations": self._operation_count,
            "collection_name": self.collection_name,
            "db_path": str(self.db_path),
            "client_initialized": self._client is not None,
            "collection_initialized": self._collection is not None
        }
