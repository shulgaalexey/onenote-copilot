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


@pytest.mark.embedding
@pytest.mark.unit
class TestEmbeddingGeneratorFixes:
    """Test fixes for EmbeddingGenerator initialization and API calls."""

    @pytest.mark.fast
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
    @pytest.mark.slow
    async def test_generate_embedding_with_no_client_original(self):
        """Test that generate_embedding fails gracefully when client is None - original slow version."""
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
    @pytest.mark.fast
    async def test_generate_embedding_with_no_client(self, mock_network_delays):
        """Test that generate_embedding fails gracefully when client is None - fast version."""
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
             patch('src.search.embeddings.log_performance') as mock_log_perf:

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
             patch('src.search.semantic_search.log_performance') as mock_log_perf:

            settings = MagicMock()
            settings.semantic_search_threshold = 0.75
            settings.semantic_search_limit = 10
            settings.chunk_size = 1000
            settings.chunk_overlap = 100
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
             patch('src.search.relevance_ranker.log_performance') as mock_log_perf:

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

    @pytest.mark.asyncio
    async def test_rank_semantic_results_performance_logging(self):
        """Test that rank_semantic_results logs performance with correct signature."""
        with patch('src.config.settings.get_settings') as mock_settings, \
             patch('src.search.relevance_ranker.log_performance') as mock_log_perf:

            settings = MagicMock()
            mock_settings.return_value = settings

            ranker = RelevanceRanker(settings)

            # Mock query intent
            from src.search.query_processor import QueryIntent
            query_intent = QueryIntent(
                original_query="test",
                processed_query="test",
                intent_type="search",
                confidence=0.9,
                keywords=["test"]
            )

            # Should complete and log performance with correct signature
            # Create a mock result so the method doesn't exit early
            from datetime import datetime

            from src.models.onenote import (ContentChunk, OneNotePage,
                                            SemanticSearchResult)
            mock_page = OneNotePage(
                id="test-page",
                title="Test Page",
                content="Test content",
                createdDateTime=datetime.now(),
                lastModifiedDateTime=datetime.now()
            )
            mock_chunk = ContentChunk(
                id="test-chunk",
                content="Test content",
                page_id="test-page",
                page_title="Test Page",
                chunk_index=0,
                start_position=0,
                end_position=12,
                metadata={}
            )
            mock_result = SemanticSearchResult(
                chunk=mock_chunk,
                similarity_score=0.8,
                search_type="semantic",
                rank=1,
                page=mock_page
            )
            result = await ranker.rank_semantic_results([mock_result], query_intent)

            assert len(result) == 1
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
            assert "1.23s" in call_args  # Should be rounded to 2 decimal places


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


class TestSemanticSearchIndexPagesUpdates:
    """Test the updated index_pages method that returns detailed results."""

    @pytest.mark.asyncio
    async def test_index_pages_returns_detailed_results(self):
        """Test that index_pages returns detailed statistics."""
        from src.models.onenote import OneNotePage

        # Mock settings
        settings = MagicMock()
        settings.openai_api_key.get_secret_value.return_value = "test-key"
        settings.semantic_search_limit = 10
        settings.semantic_search_threshold = 0.7

        # Mock search tool
        mock_search_tool = MagicMock()

        # Create engine
        engine = SemanticSearchEngine(mock_search_tool, settings)

        # Mock the index_page method to return different chunk counts
        engine.index_page = AsyncMock(side_effect=[3, 0, 2])  # Success, failure, success

        # Create test pages
        pages = [
            OneNotePage(
                id="page1",
                title="Test Page 1",
                createdDateTime="2025-01-01T10:00:00Z",
                lastModifiedDateTime="2025-01-02T15:30:00Z"
            ),
            OneNotePage(
                id="page2",
                title="Test Page 2",
                createdDateTime="2025-01-01T11:00:00Z",
                lastModifiedDateTime="2025-01-02T16:30:00Z"
            ),
            OneNotePage(
                id="page3",
                title="Test Page 3",
                createdDateTime="2025-01-01T12:00:00Z",
                lastModifiedDateTime="2025-01-02T17:30:00Z"
            )
        ]

        # Test indexing
        result = await engine.index_pages(pages)

        # Verify the result structure
        assert isinstance(result, dict)
        assert 'successful' in result
        assert 'failed' in result
        assert 'total_chunks' in result
        assert 'page_results' in result

        # Verify the counts
        assert result['successful'] == 2  # Pages 1 and 3 succeeded
        assert result['failed'] == 1     # Page 2 failed
        assert result['total_chunks'] == 5  # 3 + 0 + 2 = 5
        assert len(result['page_results']) == 3

        # Verify page-specific results
        assert result['page_results']['page1'] == 3
        assert result['page_results']['page2'] == 0
        assert result['page_results']['page3'] == 2

    @pytest.mark.asyncio
    async def test_index_pages_empty_list(self):
        """Test index_pages with empty page list."""
        # Mock settings
        settings = MagicMock()
        settings.openai_api_key.get_secret_value.return_value = "test-key"

        # Mock search tool
        mock_search_tool = MagicMock()

        # Create engine
        engine = SemanticSearchEngine(mock_search_tool, settings)

        # Test with empty list
        result = await engine.index_pages([])

        # Verify empty result
        assert result['successful'] == 0
        assert result['failed'] == 0
        assert result['total_chunks'] == 0
        assert result['page_results'] == {}

    @pytest.mark.asyncio
    async def test_index_pages_all_successful(self):
        """Test index_pages when all pages are successfully indexed."""
        from src.models.onenote import OneNotePage

        # Mock settings
        settings = MagicMock()
        settings.openai_api_key.get_secret_value.return_value = "test-key"

        # Mock search tool
        mock_search_tool = MagicMock()

        # Create engine
        engine = SemanticSearchEngine(mock_search_tool, settings)

        # Mock the index_page method to always succeed
        engine.index_page = AsyncMock(return_value=2)

        # Create test pages
        pages = [
            OneNotePage(
                id="page1",
                title="Test Page 1",
                createdDateTime="2025-01-01T10:00:00Z",
                lastModifiedDateTime="2025-01-02T15:30:00Z"
            ),
            OneNotePage(
                id="page2",
                title="Test Page 2",
                createdDateTime="2025-01-01T11:00:00Z",
                lastModifiedDateTime="2025-01-02T16:30:00Z"
            )
        ]

        # Test indexing
        result = await engine.index_pages(pages)

        # Verify all succeeded
        assert result['successful'] == 2
        assert result['failed'] == 0
        assert result['total_chunks'] == 4  # 2 pages * 2 chunks each
        assert len(result['page_results']) == 2


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
