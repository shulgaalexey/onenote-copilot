"""
Vector storage package for OneNote Copilot.

Provides efficient storage and retrieval of embeddings using ChromaDB
with caching and indexing capabilities.
"""

from .content_indexer import ContentIndexer
from .embedding_cache import EmbeddingCache
from .vector_store import VectorStore

__all__ = [
    "VectorStore",
    "EmbeddingCache",
    "ContentIndexer"
]
