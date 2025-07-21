"""
Tests for search suggestions system.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import json

from src.search.search_suggestions import (
    SearchSuggestions,
    SearchSuggestion,
    SearchHistory,
    SuggestionType
)
from src.config.settings import Settings


class TestSearchSuggestion:
    """Test SearchSuggestion data class."""
    
    def test_suggestion_creation(self):
        """Test creating a search suggestion."""
        suggestion = SearchSuggestion(
            query="python programming",
            suggestion_type=SuggestionType.HISTORY,
            score=0.8,
            frequency=5
        )
        
        assert suggestion.query == "python programming"
        assert suggestion.suggestion_type == SuggestionType.HISTORY
        assert suggestion.score == 0.8
        assert suggestion.frequency == 5


class TestSearchHistory:
    """Test SearchHistory data class."""
    
    def test_history_creation(self):
        """Test creating a search history entry."""
        timestamp = datetime.utcnow()
        history = SearchHistory(
            query="machine learning",
            timestamp=timestamp,
            result_count=15,
            success=True,
            execution_time=0.45
        )
        
        assert history.query == "machine learning"
        assert history.timestamp == timestamp
        assert history.result_count == 15
        assert history.success is True
        assert history.execution_time == 0.45


class TestSearchSuggestions:
    """Test SearchSuggestions system."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_settings(self, temp_cache_dir):
        """Create mock settings with temporary cache directory."""
        settings = Mock(spec=Settings)
        settings.cache_path = temp_cache_dir
        return settings
    
    @pytest.fixture
    def mock_local_search(self):
        """Create mock local search."""
        return Mock()
    
    @pytest.fixture
    def search_suggestions(self, mock_settings, mock_local_search):
        """Create SearchSuggestions instance for testing."""
        return SearchSuggestions(
            settings=mock_settings,
            local_search=mock_local_search,
            max_history=100,
            max_suggestions=10
        )
    
    def test_initialization(self, search_suggestions):
        """Test search suggestions initialization."""
        assert search_suggestions is not None
        assert search_suggestions.max_history == 100
        assert search_suggestions.max_suggestions == 10
        assert len(search_suggestions.search_history) == 0
        assert len(search_suggestions.suggestion_cache) == 0
    
    @pytest.mark.asyncio
    async def test_record_search(self, search_suggestions):
        """Test recording a search query."""
        await search_suggestions.record_search(
            query="python tutorial",
            result_count=25,
            success=True,
            execution_time=0.5,
            clicked_results=3
        )
        
        assert len(search_suggestions.search_history) == 1
        
        history_entry = search_suggestions.search_history[0]
        assert history_entry.query == "python tutorial"
        assert history_entry.result_count == 25
        assert history_entry.success is True
        assert history_entry.execution_time == 0.5
        assert history_entry.clicked_results == 3
    
    @pytest.mark.asyncio
    async def test_get_history_suggestions(self, search_suggestions):
        """Test getting history-based suggestions."""
        # Add some search history
        await search_suggestions.record_search("python programming", 10, True)
        await search_suggestions.record_search("python tutorial", 15, True)
        await search_suggestions.record_search("javascript basics", 8, True)
        
        # Test getting suggestions for "python"
        suggestions = await search_suggestions.get_suggestions(
            "python", 
            suggestion_types=[SuggestionType.HISTORY]
        )
        
        # Should get python programming and python tutorial
        python_suggestions = [s for s in suggestions if s.query.startswith("python")]
        assert len(python_suggestions) >= 2
        
        # Check suggestion properties
        for suggestion in python_suggestions:
            assert suggestion.suggestion_type == SuggestionType.HISTORY
            assert suggestion.score > 0
    
    @pytest.mark.asyncio
    async def test_get_autocomplete_suggestions(self, search_suggestions):
        """Test getting autocomplete suggestions."""
        # Populate term frequency
        search_suggestions.term_frequency.update([
            "programming", "python", "program", "project", "process"
        ])
        
        suggestions = await search_suggestions.get_suggestions(
            "prog", 
            suggestion_types=[SuggestionType.AUTO_COMPLETE]
        )
        
        # Should get suggestions starting with "prog"
        autocomplete_suggestions = [
            s for s in suggestions 
            if s.suggestion_type == SuggestionType.AUTO_COMPLETE
        ]
        
        assert len(autocomplete_suggestions) > 0
        for suggestion in autocomplete_suggestions:
            assert suggestion.query.lower().startswith("prog")
    
    @pytest.mark.asyncio
    async def test_get_similar_suggestions(self, search_suggestions):
        """Test getting similar query suggestions."""
        # Add query patterns
        search_suggestions.query_patterns["python machine learning"] = 5
        search_suggestions.query_patterns["machine learning python"] = 3
        search_suggestions.query_patterns["deep learning python"] = 2
        
        suggestions = await search_suggestions.get_suggestions(
            "python learning", 
            suggestion_types=[SuggestionType.SIMILAR]
        )
        
        similar_suggestions = [
            s for s in suggestions 
            if s.suggestion_type == SuggestionType.SIMILAR
        ]
        
        assert len(similar_suggestions) > 0
        
        # Should include queries with overlapping terms
        suggestion_queries = [s.query for s in similar_suggestions]
        assert any("machine learning" in query for query in suggestion_queries)
    
    @pytest.mark.asyncio
    async def test_get_popular_suggestions(self, search_suggestions):
        """Test getting popular query suggestions."""
        # Add popular query patterns
        search_suggestions.query_patterns["python tutorial"] = 10
        search_suggestions.query_patterns["javascript tutorial"] = 8
        search_suggestions.query_patterns["machine learning tutorial"] = 6
        
        suggestions = await search_suggestions.get_suggestions(
            "tutorial", 
            suggestion_types=[SuggestionType.POPULAR]
        )
        
        popular_suggestions = [
            s for s in suggestions 
            if s.suggestion_type == SuggestionType.POPULAR
        ]
        
        assert len(popular_suggestions) > 0
        
        # Should include popular queries containing "tutorial"
        for suggestion in popular_suggestions:
            assert "tutorial" in suggestion.query.lower()
    
    @pytest.mark.asyncio
    async def test_get_contextual_suggestions(self, search_suggestions):
        """Test getting contextual suggestions."""
        suggestions = await search_suggestions.get_suggestions(
            "python", 
            suggestion_types=[SuggestionType.CONTEXTUAL]
        )
        
        contextual_suggestions = [
            s for s in suggestions 
            if s.suggestion_type == SuggestionType.CONTEXTUAL
        ]
        
        # Should get contextual suggestions for python
        assert len(contextual_suggestions) > 0
        
        # Should include related terms
        suggestion_text = " ".join(s.query for s in contextual_suggestions)
        assert any(term in suggestion_text for term in ["programming", "code", "tutorial"])
    
    @pytest.mark.asyncio
    async def test_suggestion_deduplication(self, search_suggestions):
        """Test that duplicate suggestions are removed."""
        # Add duplicate entries to history
        await search_suggestions.record_search("python tutorial", 10, True)
        await search_suggestions.record_search("Python Tutorial", 12, True)  # Same query, different case
        
        suggestions = await search_suggestions.get_suggestions("python")
        
        # Should not have duplicates (case-insensitive)
        suggestion_queries = [s.query.lower() for s in suggestions]
        unique_queries = set(suggestion_queries)
        assert len(suggestion_queries) == len(unique_queries)
    
    @pytest.mark.asyncio
    async def test_suggestion_ranking(self, search_suggestions):
        """Test that suggestions are properly ranked."""
        # Add history with different success rates
        await search_suggestions.record_search("highly successful", 20, True, clicked_results=5)
        await search_suggestions.record_search("not successful", 2, False, clicked_results=0)
        await search_suggestions.record_search("moderately successful", 10, True, clicked_results=2)
        
        suggestions = await search_suggestions.get_suggestions(
            "success", 
            suggestion_types=[SuggestionType.HISTORY]
        )
        
        # Should be ranked by relevance score
        if len(suggestions) > 1:
            for i in range(len(suggestions) - 1):
                assert suggestions[i].score >= suggestions[i + 1].score
    
    @pytest.mark.asyncio
    async def test_get_search_history(self, search_suggestions):
        """Test retrieving search history."""
        # Add some history
        await search_suggestions.record_search("query1", 10, True)
        await search_suggestions.record_search("query2", 5, False)
        await search_suggestions.record_search("query3", 15, True)
        
        # Get all history
        history = await search_suggestions.get_search_history()
        assert len(history) == 3
        
        # Get successful only
        successful_history = await search_suggestions.get_search_history(successful_only=True)
        assert len(successful_history) == 2
        assert all(h.success for h in successful_history)
        
        # Test limit
        limited_history = await search_suggestions.get_search_history(limit=2)
        assert len(limited_history) == 2
    
    @pytest.mark.asyncio
    async def test_get_popular_queries(self, search_suggestions):
        """Test getting popular queries."""
        # Add multiple instances of queries
        queries = ["python tutorial", "javascript basics", "python tutorial", 
                  "machine learning", "python tutorial"]
        
        for query in queries:
            await search_suggestions.record_search(query, 10, True)
        
        popular = await search_suggestions.get_popular_queries(limit=5)
        
        assert len(popular) > 0
        
        # Most popular should be "python tutorial" (3 occurrences)
        most_popular_query, most_popular_count = popular[0]
        assert "python tutorial" in most_popular_query.lower()
        assert most_popular_count == 3
    
    @pytest.mark.asyncio
    async def test_suggestion_caching(self, search_suggestions):
        """Test suggestion result caching."""
        # First call should generate suggestions
        suggestions1 = await search_suggestions.get_suggestions("python")
        
        # Second call should use cache
        suggestions2 = await search_suggestions.get_suggestions("python")
        
        # Should be identical (from cache)
        assert len(suggestions1) == len(suggestions2)
        assert search_suggestions.stats["cache_hits"] > 0
    
    def test_clear_history(self, search_suggestions):
        """Test clearing search history."""
        # Add some history
        search_suggestions.search_history.extend([
            SearchHistory("query1", datetime.utcnow(), 10, True),
            SearchHistory("query2", datetime.utcnow() - timedelta(days=10), 5, True),
            SearchHistory("query3", datetime.utcnow() - timedelta(days=40), 8, True)
        ])
        
        initial_count = len(search_suggestions.search_history)
        assert initial_count == 3
        
        # Clear old history (older than 30 days)
        removed = search_suggestions.clear_history(older_than=timedelta(days=30))
        
        assert removed == 1  # Should remove 1 entry (40 days old)
        assert len(search_suggestions.search_history) == 2
        
        # Clear all history
        removed_all = search_suggestions.clear_history()
        assert removed_all == 2
        assert len(search_suggestions.search_history) == 0
    
    @pytest.mark.asyncio
    async def test_get_suggestion_analytics(self, search_suggestions):
        """Test getting suggestion analytics."""
        # Add some data for analytics
        await search_suggestions.record_search("python", 10, True)
        await search_suggestions.record_search("java", 5, False)
        
        # Generate some suggestions to update stats
        await search_suggestions.get_suggestions("programming")
        
        analytics = await search_suggestions.get_suggestion_analytics()
        
        assert "statistics" in analytics
        assert "usage_rate" in analytics
        assert "success_rate" in analytics
        assert "average_results" in analytics
        assert "total_history_entries" in analytics
        assert "pattern_analysis" in analytics
        
        # Check that stats are reasonable
        assert analytics["total_history_entries"] == 2
        assert 0.0 <= analytics["success_rate"] <= 1.0
    
    def test_history_size_limit(self, search_suggestions):
        """Test that history size is limited."""
        # Set small limit for testing
        search_suggestions.max_history = 5
        
        # Add more entries than the limit
        for i in range(10):
            search_suggestions.search_history.append(
                SearchHistory(f"query{i}", datetime.utcnow(), 1, True)
            )
            
            # Simulate the size limiting that happens in record_search
            if len(search_suggestions.search_history) > search_suggestions.max_history:
                search_suggestions.search_history = search_suggestions.search_history[-search_suggestions.max_history:]
        
        # Should not exceed max_history
        assert len(search_suggestions.search_history) == 5
        
        # Should keep the most recent entries
        assert search_suggestions.search_history[0].query == "query5"
        assert search_suggestions.search_history[-1].query == "query9"
    
    def test_save_and_load_history(self, search_suggestions):
        """Test saving and loading search history."""
        # Add some history
        search_suggestions.search_history.extend([
            SearchHistory("test query", datetime.utcnow(), 10, True, 0.5, 3, "session1"),
            SearchHistory("another query", datetime.utcnow() - timedelta(hours=1), 5, False, 0.3, 1, "session2")
        ])
        
        # Rebuild frequency data
        search_suggestions._rebuild_frequency_data()
        
        # Save to disk
        search_suggestions.save_data()
        
        # Create new instance to test loading
        new_suggestions = SearchSuggestions(
            settings=search_suggestions.settings,
            local_search=search_suggestions.local_search
        )
        
        # Should have loaded the history
        assert len(new_suggestions.search_history) == 2
        assert new_suggestions.search_history[0].query == "test query"
        assert new_suggestions.search_history[1].query == "another query"
        
        # Should have rebuilt frequency data
        assert len(new_suggestions.term_frequency) > 0
        assert len(new_suggestions.query_patterns) > 0
    
    @pytest.mark.asyncio
    async def test_max_results_limiting(self, search_suggestions):
        """Test that max results parameter works."""
        # Add many history entries
        for i in range(20):
            await search_suggestions.record_search(f"test query {i}", 10, True)
        
        # Request limited suggestions
        suggestions = await search_suggestions.get_suggestions(
            "test", 
            max_results=5
        )
        
        # Should not exceed max_results
        assert len(suggestions) <= 5
    
    @pytest.mark.asyncio
    async def test_time_range_filtering(self, search_suggestions):
        """Test filtering history by time range."""
        now = datetime.utcnow()
        
        # Add history at different times
        search_suggestions.search_history.extend([
            SearchHistory("recent", now, 10, True),
            SearchHistory("old", now - timedelta(days=10), 5, True),
            SearchHistory("very old", now - timedelta(days=20), 8, True)
        ])
        
        # Filter to last 15 days
        time_range = (now - timedelta(days=15), now)
        filtered_history = await search_suggestions.get_search_history(
            time_range=time_range
        )
        
        # Should only include recent and old, not very old
        assert len(filtered_history) == 2
        assert all(h.query in ["recent", "old"] for h in filtered_history)
    
    def test_term_extraction(self, search_suggestions):
        """Test term extraction from queries."""
        terms = search_suggestions._extract_terms("Python programming tutorial!")
        
        assert "python" in terms
        assert "programming" in terms
        assert "tutorial" in terms
        # Should not include punctuation or very short terms
        assert "!" not in terms
    
    def test_query_normalization(self, search_suggestions):
        """Test query normalization."""
        normalized = search_suggestions._normalize_query("Python Programming Tutorial!")
        
        assert normalized == "python programming tutorial"
        # Should be lowercase and cleaned
        assert normalized.islower()
        assert "!" not in normalized
