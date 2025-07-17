"""
Semantic search package for OneNote Copilot.

Provides vector-based content search capabilities using OpenAI embeddings
and ChromaDB for intelligent content discovery.
"""

from .content_chunker import ContentChunker
from .embeddings import EmbeddingGenerator
from .query_processor import QueryProcessor
from .relevance_ranker import RelevanceRanker
from .semantic_search import SemanticSearchEngine

__all__ = [
    "EmbeddingGenerator",
    "SemanticSearchEngine",
    "QueryProcessor",
    "ContentChunker",
    "RelevanceRanker"
]
