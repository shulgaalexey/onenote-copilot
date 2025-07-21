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

        assert "exact phrase" in analysis.phrases
        assert analysis.terms == ["find", "exact phrase", "in", "documents"]

    def test_important_terms_identification(self):
        """Test identification of important terms."""
        analysis = QueryAnalysis.analyze("python programming tutorial example")

        # Programming terms should be considered important
        assert "python" in analysis.important_terms
        assert "programming" in analysis.important_terms

    def test_intent_detection(self):
        """Test query intent detection."""
        tutorial_analysis = QueryAnalysis.analyze("how to learn python")
        assert tutorial_analysis.intent == "tutorial"

        reference_analysis = QueryAnalysis.analyze("python syntax reference")
        assert reference_analysis.intent == "reference"

        example_analysis = QueryAnalysis.analyze("python code examples")
        assert example_analysis.intent == "example"

    def test_phrase_extraction(self):
        """Test phrase extraction from query."""
        analysis = QueryAnalysis.analyze("machine learning algorithms")

        assert "machine learning" in analysis.phrases

    def test_complex_query_analysis(self):
        """Test analysis of complex queries."""
        analysis = QueryAnalysis.analyze('find "neural networks" in machine learning tutorials')

        assert "neural networks" in analysis.phrases
        assert "machine learning" in analysis.phrases
        assert analysis.intent == "tutorial"
        assert len(analysis.terms) > 3


class TestRankingWeights:
    """Test ranking weights functionality."""

    def test_default_weights(self):
        """Test default weight creation."""
        weights = RankingWeights()

        # Check that all factors have weights
        assert weights.query_match > 0
        assert weights.title_match > 0
        assert weights.freshness > 0
        assert weights.content_length > 0
        assert weights.structure > 0

    def test_weights_normalization(self):
        """Test that weights can be normalized."""
        weights = RankingWeights(
            query_match=10.0,
            title_match=5.0,
            freshness=3.0,
            content_length=2.0,
            structure=1.0
        )

        normalized = weights.normalize()
        total = (normalized.query_match + normalized.title_match +
                normalized.freshness + normalized.content_length +
                normalized.structure)

        assert abs(total - 1.0) < 0.01  # Should sum to 1.0

    def test_zero_weights_normalization(self):
        """Test handling of zero weights during normalization."""
        weights = RankingWeights(
            query_match=0.0,
            title_match=0.0,
            freshness=0.0,
            content_length=0.0,
            structure=0.0
        )

        # Should not raise an error
        normalized = weights.normalize()
        assert normalized.query_match >= 0


class TestRankingScore:
    """Test ranking score functionality."""

    def test_score_creation(self):
        """Test creating a ranking score."""
        score = RankingScore(
            total=0.85,
            breakdown={
                RankingFactor.QUERY_MATCH: 0.4,
                RankingFactor.TITLE_MATCH: 0.2,
                RankingFactor.FRESHNESS: 0.15,
                RankingFactor.CONTENT_LENGTH: 0.05,
                RankingFactor.STRUCTURE: 0.05
            },
            explanation="High relevance due to strong query match"
        )

        assert score.total == 0.85
        assert len(score.breakdown) == 5
        assert score.explanation is not None

    def test_score_breakdown(self):
        """Test score breakdown functionality."""
        breakdown = {
            RankingFactor.QUERY_MATCH: 0.4,
            RankingFactor.TITLE_MATCH: 0.2
        }

        score = RankingScore(total=0.6, breakdown=breakdown)

        assert score.breakdown[RankingFactor.QUERY_MATCH] == 0.4
        assert score.breakdown[RankingFactor.TITLE_MATCH] == 0.2


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
        assert ranking_system.cache_enabled is True

    @pytest.mark.asyncio
    async def test_basic_ranking(self, ranking_system, sample_pages):
        """Test basic ranking functionality."""
        query = "python programming"
        ranked_pages = await ranking_system.rank_pages(sample_pages, query)

        assert len(ranked_pages) <= len(sample_pages)

        # First result should be most relevant
        if ranked_pages:
            assert ranked_pages[0].score.total > 0
            # Python programming tutorial should rank higher than JavaScript
            python_page = next((p for p in ranked_pages if "Python" in p.page.title), None)
            js_page = next((p for p in ranked_pages if "JavaScript" in p.page.title), None)

            if python_page and js_page:
                assert python_page.score.total > js_page.score.total

    @pytest.mark.asyncio
    async def test_query_relevance_ranking(self, ranking_system, sample_pages):
        """Test query relevance ranking."""
        # Query that should favor Python content
        python_query = "python tutorial"
        python_results = await ranking_system.rank_pages(sample_pages, python_query)

        if python_results:
            # Python tutorial should be first
            assert "Python" in python_results[0].page.title

        # Query that should favor ML content
        ml_query = "machine learning"
        ml_results = await ranking_system.rank_pages(sample_pages, ml_query)

        if ml_results:
            # ML page should be highly ranked
            assert any("Machine Learning" in result.page.title for result in ml_results[:2])

    @pytest.mark.asyncio
    async def test_title_matching_bonus(self, ranking_system):
        """Test title matching bonus."""
        page_with_title_match = CachedPage(
            metadata=CachedPageMetadata(
                id="title-match",
                title="Python Programming Guide",  # Exact match
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/title-match",
                local_content_path="/local/title-match.md",
                local_html_path="/local/title-match.html"
            ),
            content="Some content about programming"
        )

        page_no_title_match = CachedPage(
            metadata=CachedPageMetadata(
                id="no-match",
                title="Random Topic",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/no-match",
                local_content_path="/local/no-match.md",
                local_html_path="/local/no-match.html"
            ),
            content="Python programming content but title doesn't match"
        )

        pages = [page_with_title_match, page_no_title_match]
        ranked = await ranking_system.rank_pages(pages, "python programming")

        if len(ranked) >= 2:
            # Page with title match should rank higher
            assert ranked[0].page.title == "Python Programming Guide"

    @pytest.mark.asyncio
    async def test_freshness_scoring(self, ranking_system):
        """Test freshness scoring."""
        # Recent page
        recent_page = CachedPage(
            metadata=CachedPageMetadata(
                id="recent",
                title="Recent Page",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/recent",
                local_content_path="/local/recent.md",
                local_html_path="/local/recent.html"
            ),
            content="Recent content"
        )

        # Old page
        old_page = CachedPage(
            metadata=CachedPageMetadata(
                id="old",
                title="Old Page",
                created_date_time=datetime.utcnow() - timedelta(days=365),
                last_modified_date_time=datetime.utcnow() - timedelta(days=365),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/old",
                local_content_path="/local/old.md",
                local_html_path="/local/old.html"
            ),
            content="Old content"
        )

        recent_score = await ranking_system._score_freshness(recent_page)
        old_score = await ranking_system._score_freshness(old_page)

        assert recent_score > old_score

    @pytest.mark.asyncio
    async def test_content_length_scoring(self, ranking_system):
        """Test content length scoring."""
        # Optimal length page
        optimal_page = CachedPage(
            metadata=CachedPageMetadata(
                id="optimal",
                title="Optimal Page",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/optimal",
                local_content_path="/local/optimal.md",
                local_html_path="/local/optimal.html"
            ),
            content="A" * 500  # Optimal length
        )

        # Too short page
        short_page = CachedPage(
            metadata=CachedPageMetadata(
                id="short",
                title="Short Page",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/short",
                local_content_path="/local/short.md",
                local_html_path="/local/short.html"
            ),
            content="Short"  # Too short
        )

        optimal_score = await ranking_system._score_content_length(optimal_page)
        short_score = await ranking_system._score_content_length(short_page)

        assert optimal_score > short_score

    @pytest.mark.asyncio
    async def test_structure_scoring(self, ranking_system):
        """Test structure scoring."""
        # Well-structured page
        structured_page = CachedPage(
            metadata=CachedPageMetadata(
                id="structured",
                title="Well Structured Page",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/structured",
                local_content_path="/local/structured.md",
                local_html_path="/local/structured.html"
            ),
            content="<h1>Header</h1><p>Content</p><ul><li>List item</li></ul>"
        )

        # Poorly structured page
        unstructured_page = CachedPage(
            metadata=CachedPageMetadata(
                id="unstructured",
                title="Poorly Structured Page",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/unstructured",
                local_content_path="/local/unstructured.md",
                local_html_path="/local/unstructured.html"
            ),
            content="Just plain text without any structure"
        )

        structured_score = await ranking_system._score_structure(structured_page)
        unstructured_score = await ranking_system._score_structure(unstructured_page)

        assert structured_score > unstructured_score

    @pytest.mark.asyncio
    async def test_max_results_limit(self, ranking_system, sample_pages):
        """Test max results limiting."""
        # Add more pages to test limit
        extended_pages = sample_pages * 10  # 30 pages total

        ranked_pages = await ranking_system.rank_pages(
            extended_pages,
            "python programming",
            max_results=5
        )

        assert len(ranked_pages) <= 5

    def test_caching_functionality(self, ranking_system):
        """Test caching functionality."""
        # Enable caching
        ranking_system.cache_enabled = True
        assert ranking_system.cache_enabled

        # Disable caching
        ranking_system.cache_enabled = False
        assert not ranking_system.cache_enabled

    @pytest.mark.asyncio
    async def test_ranking_explanation(self, ranking_system, sample_pages):
        """Test ranking explanation generation."""
        ranked_pages = await ranking_system.rank_pages(
            sample_pages[:1],
            "python programming"
        )

        if ranked_pages:
            result = ranked_pages[0]
            assert result.score.explanation is not None
            assert len(result.score.explanation) > 0

    def test_custom_weights_creation(self):
        """Test creating ranking system with custom weights."""
        custom_weights = RankingWeights(
            query_match=0.6,
            title_match=0.2,
            freshness=0.1,
            content_length=0.05,
            structure=0.05
        )

        ranking_system = SemanticRanking(weights=custom_weights)
        assert ranking_system.weights.query_match == 0.6

    def test_statistics_tracking(self, ranking_system):
        """Test ranking statistics tracking."""
        stats = ranking_system.get_stats()

        assert "total_queries" in stats
        assert "cache_hits" in stats
        assert "average_ranking_time" in stats

    def test_cache_clearing(self, ranking_system):
        """Test cache clearing."""
        ranking_system.clear_cache()

        # Should not raise any errors
        stats = ranking_system.get_stats()
        assert stats["cache_hits"] >= 0

    def test_weights_updating(self, ranking_system):
        """Test updating ranking weights."""
        new_weights = RankingWeights(query_match=0.8, title_match=0.2)
        ranking_system.update_weights(new_weights)

        assert ranking_system.weights.query_match == 0.8
        assert ranking_system.weights.title_match == 0.2

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
        result = await ranking_system.rank_pages([minimal_page], "test query")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_semantic_similarity_scoring(self, ranking_system):
        """Test semantic similarity scoring."""
        query_analysis = QueryAnalysis.analyze("python programming")

        # Page with related content
        related_page = CachedPage(
            metadata=CachedPageMetadata(
                id="related",
                title="Programming with Python",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/related",
                local_content_path="/local/related.md",
                local_html_path="/local/related.html"
            ),
            content="Python coding and development techniques"
        )

        # Page with unrelated content
        unrelated_page = CachedPage(
            metadata=CachedPageMetadata(
                id="unrelated",
                title="Cooking Recipes",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/unrelated",
                local_content_path="/local/unrelated.md",
                local_html_path="/local/unrelated.html"
            ),
            content="How to cook pasta and make sauce"
        )

        related_score = await ranking_system._score_semantic_similarity(
            related_page, query_analysis
        )
        unrelated_score = await ranking_system._score_semantic_similarity(
            unrelated_page, query_analysis
        )

        assert related_score > unrelated_score

    @pytest.mark.asyncio
    async def test_keyword_density_scoring(self, ranking_system):
        """Test keyword density scoring."""
        query_analysis = QueryAnalysis.analyze("python")

        # Page with optimal keyword density
        optimal_page = CachedPage(
            metadata=CachedPageMetadata(
                id="optimal",
                title="Python Tutorial",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/optimal",
                local_content_path="/local/optimal.md",
                local_html_path="/local/optimal.html"
            ),
            content=" ".join(["python programming"] * 2 + ["other content"] * 100)  # ~2% density
        )

        # Page with too high density (spam)
        spam_page = CachedPage(
            metadata=CachedPageMetadata(
                id="spam",
                title="Python Spam",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/spam",
                local_content_path="/local/spam.md",
                local_html_path="/local/spam.html"
            ),
            content="python " * 100  # Very high density
        )

        optimal_score = await ranking_system._score_keyword_density(
            optimal_page, query_analysis
        )
        spam_score = await ranking_system._score_keyword_density(
            spam_page, query_analysis
        )

        assert optimal_score > spam_score

    @pytest.mark.asyncio
    async def test_position_bonus_scoring(self, ranking_system):
        """Test position bonus scoring."""
        query_analysis = QueryAnalysis.analyze("important")

        # Page with keyword at the beginning
        early_page = CachedPage(
            metadata=CachedPageMetadata(
                id="early",
                title="Page Title",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/early",
                local_content_path="/local/early.md",
                local_html_path="/local/early.html"
            ),
            content="important information at the beginning of content"
        )

        # Page with keyword at the end
        late_page = CachedPage(
            metadata=CachedPageMetadata(
                id="late",
                title="Page Title",
                created_date_time=datetime.utcnow(),
                last_modified_date_time=datetime.utcnow(),
                parent_section={"id": "section-1", "name": "Test"},
                parent_notebook={"id": "notebook-1", "name": "Test"},
                content_url="https://graph.microsoft.com/v1.0/me/onenote/pages/late",
                local_content_path="/local/late.md",
                local_html_path="/local/late.html"
            ),
            content="lots of other content before the keyword important appears"
        )

        early_score = await ranking_system._score_position_bonus(
            early_page, query_analysis
        )
        late_score = await ranking_system._score_position_bonus(
            late_page, query_analysis
        )

        assert early_score > late_score
