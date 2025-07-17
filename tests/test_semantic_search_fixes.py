"""
Tests for semantic search error fixes.

This test suite validates the fixes for:
1. OpenAI client initialization issues
2. log_performance function call signature errors
3. API key validation and error handling
"""

import asyncio
import unittest.mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.settings import get_settings
from src.search.embeddings import EmbeddingError, EmbeddingGenerator
from src.search.relevance_ranker import RelevanceRanker
from src.search.semantic_search import SemanticSearchEngine


class TestEmbeddingGeneratorFixes:
    """Test fixes for EmbeddingGenerator initialization and API calls."""

    def test_embedding_generator_with_no_api_key(self):
        """Test that EmbeddingGenerator handles missing API key gracefully."""
        with patch('src.config.settings.get_settings') as mock_settings:
            settings = MagicMock()
            settings.openai_api_key.get_secret_value.return_value = ""
            mock_settings.return_value = settings

            generator = EmbeddingGenerator(settings)

            # Client should be None when API key is empty
            assert generator.client is None

    def test_embedding_generator_with_invalid_api_key(self):
        """Test that EmbeddingGenerator handles invalid API key gracefully."""
        with patch('src.config.settings.get_settings') as mock_settings:
            settings = MagicMock()
            settings.openai_api_key.get_secret_value.side_effect = Exception("Invalid key")
            mock_settings.return_value = settings

            generator = EmbeddingGenerator(settings)

            # Client should be None when API key access fails
            assert generator.client is None

    @pytest.mark.asyncio
    async def test_generate_embedding_with_no_client(self):
        """Test that generate_embedding fails gracefully when client is None."""
        with patch('src.config.settings.get_settings') as mock_settings:
            settings = MagicMock()
            settings.openai_api_key.get_secret_value.return_value = ""
            mock_settings.return_value = settings

            generator = EmbeddingGenerator(settings)

            # Should raise EmbeddingError when client is None
            with pytest.raises(EmbeddingError) as exc_info:
                await generator.generate_embedding("test content")

            assert "OpenAI client is not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_embedding_api_call_format(self):
        """Test that generate_embedding makes correct API calls without context manager errors."""
        with patch('src.config.settings.get_settings') as mock_settings:
            settings = MagicMock()
            settings.openai_api_key.get_secret_value.return_value = "sk-test-key"
            settings.embedding_model = "text-embedding-3-small"
            settings.embedding_dimensions = 1536
            mock_settings.return_value = settings

            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_openai.return_value = mock_client

                # Mock successful response
                mock_response = MagicMock()
                mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
                mock_response.usage.total_tokens = 10
                mock_client.embeddings.create.return_value = mock_response

                generator = EmbeddingGenerator(settings)

                # Should complete without context manager errors
                result = await generator.generate_embedding("test content")

                assert result == [0.1, 0.2, 0.3]
                mock_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_generate_embeddings_performance_logging(self):
        """Test that batch_generate_embeddings logs performance correctly."""
        with patch('src.config.settings.get_settings') as mock_settings, \
             patch('src.config.logging.log_performance') as mock_log_perf:

            settings = MagicMock()
            settings.openai_api_key.get_secret_value.return_value = "sk-test-key"
            settings.embedding_model = "text-embedding-3-small"
            settings.embedding_dimensions = 1536
            settings.embedding_batch_size = 2
            mock_settings.return_value = settings

            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_openai.return_value = mock_client

                # Mock successful response
                mock_response = MagicMock()
                mock_response.data = [
                    MagicMock(embedding=[0.1, 0.2, 0.3]),
                    MagicMock(embedding=[0.4, 0.5, 0.6])
                ]
                mock_response.usage.total_tokens = 20
                mock_client.embeddings.create.return_value = mock_response

                generator = EmbeddingGenerator(settings)

                # Should complete and log performance with correct signature
                result = await generator.batch_generate_embeddings(["content1", "content2"])

                assert len(result) == 2
                # Verify log_performance was called with correct signature (name, duration, **kwargs)
                mock_log_perf.assert_called()
                call_args = mock_log_perf.call_args
                assert len(call_args[0]) == 2  # Should have exactly 2 positional args
                assert call_args[0][0] == "batch_generate_embeddings"  # Function name
                assert isinstance(call_args[0][1], float)  # Duration


class TestSemanticSearchEngineFixes:
    """Test fixes for SemanticSearchEngine performance logging."""

    @pytest.mark.asyncio
    async def test_semantic_search_performance_logging(self):
        """Test that semantic_search logs performance with correct signature."""
        with patch('src.config.settings.get_settings') as mock_settings, \
             patch('src.config.logging.log_performance') as mock_log_perf:

            settings = MagicMock()
            settings.semantic_search_threshold = 0.75
            settings.semantic_search_limit = 10
            mock_settings.return_value = settings

            # Mock dependencies
            mock_search_tool = MagicMock()

            engine = SemanticSearchEngine(mock_search_tool, settings)

            # Mock all the components
            engine.query_processor = AsyncMock()
            engine.query_processor.process_query.return_value = MagicMock(processed_query="test")

            engine.embedding_generator = AsyncMock()
            engine.embedding_generator.embed_query.return_value = [0.1, 0.2, 0.3]

            engine.vector_store = AsyncMock()
            engine.vector_store.search_similar.return_value = []

            engine.relevance_ranker = AsyncMock()
            engine.relevance_ranker.rank_semantic_results.return_value = []

            # Should complete and log performance with correct signature
            result = await engine.semantic_search("test query")

            assert result == []
            # Verify log_performance was called with correct signature
            mock_log_perf.assert_called()
            call_args = mock_log_perf.call_args
            assert len(call_args[0]) == 2  # Should have exactly 2 positional args
            assert call_args[0][0] == "semantic_search"  # Function name
            assert isinstance(call_args[0][1], float)  # Duration


class TestRelevanceRankerFixes:
    """Test fixes for RelevanceRanker performance logging."""

    @pytest.mark.asyncio
    async def test_combine_hybrid_results_performance_logging(self):
        """Test that combine_hybrid_results logs performance with correct signature."""
        with patch('src.config.settings.get_settings') as mock_settings, \
             patch('src.config.logging.log_performance') as mock_log_perf:

            settings = MagicMock()
            mock_settings.return_value = settings

            ranker = RelevanceRanker(settings)

            # Should complete and log performance with correct signature
            result = await ranker.combine_hybrid_results([], [], 0.6, 0.4, 10)

            assert result == []
            # Verify log_performance was called with correct signature
            mock_log_perf.assert_called()
            call_args = mock_log_perf.call_args
            assert len(call_args[0]) == 2  # Should have exactly 2 positional args
            assert call_args[0][0] == "combine_hybrid_results"  # Function name
            assert isinstance(call_args[0][1], float)  # Duration

    def test_rank_semantic_results_performance_logging(self):
        """Test that rank_semantic_results logs performance with correct signature."""
        with patch('src.config.settings.get_settings') as mock_settings, \
             patch('src.config.logging.log_performance') as mock_log_perf:

            settings = MagicMock()
            mock_settings.return_value = settings

            ranker = RelevanceRanker(settings)

            # Mock query intent
            from src.search.query_processor import QueryIntent
            query_intent = QueryIntent(
                intent_type="search",
                keywords=["test"],
                processed_query="test",
                metadata={}
            )

            # Should complete and log performance with correct signature
            result = ranker.rank_semantic_results([], query_intent)

            assert result == []
            # Verify log_performance was called with correct signature
            mock_log_perf.assert_called()
            call_args = mock_log_perf.call_args
            assert len(call_args[0]) == 2  # Should have exactly 2 positional args
            assert call_args[0][0] == "rank_semantic_results"  # Function name
            assert isinstance(call_args[0][1], float)  # Duration


class TestLogPerformanceFunction:
    """Test the log_performance function signature."""

    def test_log_performance_signature(self):
        """Test that log_performance accepts the correct arguments."""
        from src.config.logging import log_performance

        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            # Should accept function name, duration, and keyword arguments
            log_performance("test_function", 1.234, test_arg="value", count=42)

            # Verify logger was called
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_function" in call_args
            assert "1.234s" in call_args


class TestEndToEndFix:
    """Test the complete fix end-to-end."""

    @pytest.mark.asyncio
    async def test_semantic_search_engine_with_missing_api_key(self):
        """Test that SemanticSearchEngine handles missing API key gracefully."""
        with patch('src.config.settings.get_settings') as mock_settings:
            settings = MagicMock()
            settings.openai_api_key.get_secret_value.return_value = ""
            settings.semantic_search_threshold = 0.75
            settings.semantic_search_limit = 10
            mock_settings.return_value = settings

            mock_search_tool = MagicMock()

            # Should initialize without errors
            engine = SemanticSearchEngine(mock_search_tool, settings)

            # Embedding generator should have None client
            assert engine.embedding_generator.client is None

            # Semantic search should fail gracefully
            with pytest.raises(Exception):  # Will raise during embedding generation
                await engine.semantic_search("test query")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
