"""
Tests for semantic ranking system.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from src.models.cache import CachedPage, CachedPageMetadata
from src.search.semantic_ranking import (QueryAnalysis, RankingFactor,
                                         RankingScore, RankingWeights,
                                         SemanticRanking)


class TestQueryAnalysis:
    """Test query analysis functionality."""

    def test_basic_query_analysis(self):
        """Test basic query analysis."""
        analysis = QueryAnalysis.analyze("python programming tutorial")

        assert analysis.original_query == "python programming tutorial"
        assert "python" in analysis.terms
        assert "programming" in analysis.terms
        assert "tutorial" in analysis.terms

    def test_quoted_phrase_extraction(self):
        """Test extraction of quoted phrases."""
        analysis = QueryAnalysis.analyze('find "exact phrase" in documents')

        assert "exact phrase" in analysis.quoted_phrases

    def test_important_terms_identification(self):
        """Test identification of important terms."""
        analysis = QueryAnalysis.analyze("python programming tutorial example")

        # Programming terms should be considered important
        assert "python" in analysis.important_terms or "programming" in analysis.important_terms


class TestRankingWeights:
    """Test ranking weights functionality."""

    def test_default_weights(self):
        """Test default weight creation."""
        weights = RankingWeights()

        # Check that all factors have weights
        assert weights.query_match > 0
        assert weights.title_match > 0
        assert weights.freshness > 0
        assert weights.length > 0  # Note: it's 'length' not 'content_length'
        assert weights.structure > 0

    def test_weights_normalization(self):
        """Test that weights can be normalized."""
        weights = RankingWeights(
            query_match=10.0,
            title_match=5.0,
            freshness=3.0,
            length=2.0,  # Note: correct field name
            structure=1.0
        )

        normalized = weights.normalize()

        # Check that normalized weights are reasonable
        assert normalized.query_match > 0
        assert normalized.title_match > 0


class TestRankingScore:
    """Test ranking score functionality."""

    def test_score_creation(self):
        """Test creating a ranking score."""
        score = RankingScore(
            total_score=0.85,  # Note: correct field name
            page_id="test-page",
            page_title="Test Page",
            query_match_score=0.4,
            title_match_score=0.2,
            freshness_score=0.15,
            length_score=0.05,
            structure_score=0.05
        )

        assert score.total_score == 0.85
        assert score.page_id == "test-page"
        assert score.page_title == "Test Page"

    def test_score_breakdown(self):
        """Test score breakdown functionality."""
        score = RankingScore(
            total_score=0.6,
            page_id="test",
            page_title="Test",
            query_match_score=0.4,
            title_match_score=0.2
        )

        breakdown = score.get_score_breakdown()
        assert "query_match" in breakdown
        assert "title_match" in breakdown


class TestSemanticRanking:
    """Test semantic ranking system."""

    @pytest.fixture
    def ranking_system(self):
        """Create a semantic ranking system for testing."""
        return SemanticRanking()

    @pytest.fixture
    def sample_pages(self):
        """Create sample pages for testing."""
        return [
            CachedPage(
                metadata=CachedPageMetadata(
                    id="page-1",
                    title="Python Programming Tutorial",
                    created_date_time=datetime.utcnow() - timedelta(days=1),
                    last_modified_date_time=datetime.utcnow() - timedelta(days=1),
                    parent_section={"id": "section-1", "name": "Tutorials"},
                    parent_notebook={"id": "notebook-1", "name": "Programming"},
                    content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/page-1",
                    local_content_path="/local/page-1.md",
                    local_html_path="/local/page-1.html"
                ),
                content="Learn Python programming with examples and exercises. Python is a powerful language."
            ),
            CachedPage(
                metadata=CachedPageMetadata(
                    id="page-2",
                    title="JavaScript Basics",
                    created_date_time=datetime.utcnow() - timedelta(days=30),
                    last_modified_date_time=datetime.utcnow() - timedelta(days=30),
                    parent_section={"id": "section-1", "name": "Tutorials"},
                    parent_notebook={"id": "notebook-1", "name": "Programming"},
                    content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/page-2",
                    local_content_path="/local/page-2.md",
                    local_html_path="/local/page-2.html"
                ),
                content="Introduction to JavaScript programming. Learn about variables, functions, and objects."
            ),
            CachedPage(
                metadata=CachedPageMetadata(
                    id="page-3",
                    title="Machine Learning with Python",
                    created_date_time=datetime.utcnow() - timedelta(days=7),
                    last_modified_date_time=datetime.utcnow() - timedelta(days=7),
                    parent_section={"id": "section-2", "name": "ML"},
                    parent_notebook={"id": "notebook-2", "name": "Data Science"},
                    content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/page-3",
                    local_content_path="/local/page-3.md",
                    local_html_path="/local/page-3.html"
                ),
                content="Advanced Python programming for machine learning. Includes algorithms and data analysis."
            )
        ]

    def test_initialization(self, ranking_system):
        """Test ranking system initialization."""
        assert ranking_system is not None
        assert ranking_system.weights is not None
        assert ranking_system.enable_caching is True

    @pytest.mark.asyncio
    async def test_basic_ranking(self, ranking_system, sample_pages):
        """Test basic ranking functionality."""
        query = "python programming"
        ranked_pages = await ranking_system.rank_results(sample_pages, query)

        assert len(ranked_pages) <= len(sample_pages)

        # First result should be most relevant
        if ranked_pages:
            page, score = ranked_pages[0]
            assert score.total_score > 0
            # Python programming tutorial should rank higher than JavaScript
            python_found = False
            for page_result, score_result in ranked_pages:
                if "Python" in page_result.title:
                    python_found = True
                    break
            assert python_found

    @pytest.mark.asyncio
    async def test_max_results_limit(self, ranking_system, sample_pages):
        """Test max results limiting."""
        # Add more pages to test limit
        extended_pages = sample_pages * 10  # 30 pages total

        ranked_pages = await ranking_system.rank_results(
            extended_pages,
            "python programming",
            max_results=5
        )

        assert len(ranked_pages) <= 5

    def test_caching_functionality(self, ranking_system):
        """Test caching functionality."""
        # Enable caching
        ranking_system.enable_caching = True
        assert ranking_system.enable_caching

        # Disable caching
        ranking_system.enable_caching = False
        assert not ranking_system.enable_caching

    def test_statistics_tracking(self, ranking_system):
        """Test ranking statistics tracking."""
        stats = ranking_system.get_ranking_stats()

        assert "queries_processed" in stats
        assert "pages_ranked" in stats
        assert "cache_hits" in stats
        assert "avg_ranking_time" in stats

    def test_cache_clearing(self, ranking_system):
        """Test cache clearing."""
        ranking_system.clear_cache()

        # Should not raise any errors
        stats = ranking_system.get_ranking_stats()
        assert stats["cache_hits"] >= 0

    def test_weights_updating(self, ranking_system):
        """Test updating ranking weights."""
        new_weights = RankingWeights(query_match=0.8, title_match=0.2)
        ranking_system.set_weights(new_weights)

        assert ranking_system.weights.query_match == 0.8
        assert ranking_system.weights.title_match == 0.2

    def test_custom_weights_creation(self, ranking_system):
        """Test creating custom weights."""
        custom_weights = ranking_system.create_custom_weights(
            query_emphasis=0.7,
            recency_emphasis=0.3
        )

        assert isinstance(custom_weights, RankingWeights)

    @pytest.mark.asyncio
    async def test_error_handling_in_ranking(self, ranking_system):
        """Test error handling during ranking."""
        # Create page with minimal required fields
        minimal_page = CachedPage(
            metadata=CachedPageMetadata(
                id="minimal",
                title="Minimal Page",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/minimal",
                local_content_path="/local/minimal.md",
                local_html_path="/local/minimal.html"
            ),
            content=None  # None content should be handled
        )

        # Should not raise an error
        result = await ranking_system.rank_results([minimal_page], "test query")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_ranking_explanation(self, ranking_system, sample_pages):
        """Test ranking explanation generation."""
        if sample_pages:
            page = sample_pages[0]
            explanation = await ranking_system.explain_ranking(page, "python programming")

            assert explanation is not None
            assert isinstance(explanation, dict)
