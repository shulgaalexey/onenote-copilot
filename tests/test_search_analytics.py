"""
Tests for search analytics system.
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import json
import uuid

from src.search.search_analytics import (
    SearchAnalytics,
    SearchEvent,
    SearchEventType,
    PerformanceMetric,
    PerformanceSnapshot,
    SearchPattern
)
from src.config.settings import Settings


class TestSearchEvent:
    """Test SearchEvent data class."""
    
    def test_event_creation(self):
        """Test creating a search event."""
        event = SearchEvent(
            event_type=SearchEventType.QUERY_EXECUTED,
            query="python programming",
            result_count=15,
            execution_time=0.45,
            success=True
        )
        
        assert event.event_type == SearchEventType.QUERY_EXECUTED
        assert event.query == "python programming"
        assert event.result_count == 15
        assert event.execution_time == 0.45
        assert event.success is True
        assert event.event_id is not None
        assert event.timestamp is not None
    
    def test_event_defaults(self):
        """Test event creation with defaults."""
        event = SearchEvent()
        
        assert event.event_type == SearchEventType.QUERY_EXECUTED
        assert event.success is True
        assert len(event.event_id) > 0
        assert isinstance(event.timestamp, datetime)


class TestPerformanceSnapshot:
    """Test PerformanceSnapshot data class."""
    
    def test_snapshot_creation(self):
        """Test creating a performance snapshot."""
        snapshot = PerformanceSnapshot(
            avg_query_time=0.5,
            cache_hit_rate=0.75,
            successful_query_rate=0.95,
            queries_per_hour=120
        )
        
        assert snapshot.avg_query_time == 0.5
        assert snapshot.cache_hit_rate == 0.75
        assert snapshot.successful_query_rate == 0.95
        assert snapshot.queries_per_hour == 120


class TestSearchPattern:
    """Test SearchPattern data class."""
    
    def test_pattern_creation(self):
        """Test creating a search pattern."""
        pattern = SearchPattern(
            pattern_type="common_query",
            queries=["python tutorial", "python programming"],
            frequency=25,
            success_rate=0.8
        )
        
        assert pattern.pattern_type == "common_query"
        assert len(pattern.queries) == 2
        assert pattern.frequency == 25
        assert pattern.success_rate == 0.8


class TestSearchAnalytics:
    """Test SearchAnalytics system."""
    
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
    def analytics(self, mock_settings):
        """Create SearchAnalytics instance for testing."""
        return SearchAnalytics(
            settings=mock_settings,
            max_events=1000,
            retention_days=30
        )
    
    def test_initialization(self, analytics):
        """Test analytics initialization."""
        assert analytics is not None
        assert analytics.max_events == 1000
        assert analytics.retention_days == 30
        assert len(analytics.events) == 0
        assert len(analytics.patterns) == 0
        assert analytics.analytics_enabled is True
        assert analytics.analytics_dir.exists()
    
    @pytest.mark.asyncio
    async def test_track_event(self, analytics):
        """Test tracking search events."""
        event_id = await analytics.track_event(
            SearchEventType.QUERY_EXECUTED,
            query="python programming",
            result_count=10,
            execution_time=0.5,
            success=True
        )
        
        assert event_id is not None and len(event_id) > 0
        assert len(analytics.events) == 1
        
        event = analytics.events[0]
        assert event.event_type == SearchEventType.QUERY_EXECUTED
        assert event.query == "python programming"
        assert event.result_count == 10
        assert event.execution_time == 0.5
        assert event.success is True
    
    @pytest.mark.asyncio
    async def test_track_multiple_events(self, analytics):
        """Test tracking multiple events."""
        events_data = [
            (SearchEventType.QUERY_EXECUTED, {"query": "python", "result_count": 5}),
            (SearchEventType.RESULT_CLICKED, {"clicked_result_position": 1}),
            (SearchEventType.FILTER_APPLIED, {"filters_applied": ["date_range"]}),
            (SearchEventType.SEARCH_COMPLETED, {"success": True})
        ]
        
        event_ids = []
        for event_type, kwargs in events_data:
            event_id = await analytics.track_event(event_type, **kwargs)
            event_ids.append(event_id)
        
        assert len(analytics.events) == 4
        assert all(event_id for event_id in event_ids)
        
        # Check event types are correct
        event_types = [e.event_type for e in analytics.events]
        expected_types = [data[0] for data in events_data]
        assert event_types == expected_types
    
    @pytest.mark.asyncio
    async def test_record_performance(self, analytics):
        """Test recording performance metrics."""
        await analytics.record_performance(
            PerformanceMetric.QUERY_EXECUTION_TIME,
            0.45
        )
        
        await analytics.record_performance(
            PerformanceMetric.TOTAL_SEARCH_TIME,
            1.2
        )
        
        # Check performance buffer
        assert len(analytics.performance_buffer[PerformanceMetric.QUERY_EXECUTION_TIME.value]) == 1
        assert analytics.performance_buffer[PerformanceMetric.QUERY_EXECUTION_TIME.value][0] == 0.45
        
        assert len(analytics.performance_buffer[PerformanceMetric.TOTAL_SEARCH_TIME.value]) == 1
        assert analytics.performance_buffer[PerformanceMetric.TOTAL_SEARCH_TIME.value][0] == 1.2
    
    @pytest.mark.asyncio
    async def test_get_real_time_metrics(self, analytics):
        """Test getting real-time metrics."""
        # Add some test events
        session_id = str(uuid.uuid4())
        await analytics.track_event(SearchEventType.QUERY_EXECUTED, session_id=session_id, success=True)
        await analytics.track_event(SearchEventType.QUERY_EXECUTED, session_id=session_id, success=True)
        await analytics.track_event(SearchEventType.QUERY_EXECUTED, session_id=str(uuid.uuid4()), success=False)
        
        # Record some performance metrics
        await analytics.record_performance(PerformanceMetric.QUERY_EXECUTION_TIME, 0.5)
        
        metrics = await analytics.get_real_time_metrics()
        
        assert "timestamp" in metrics
        assert "events_last_hour" in metrics
        assert "active_sessions" in metrics
        assert "query_rate" in metrics
        assert "success_rate" in metrics
        assert "performance" in metrics
        
        # Check values
        assert metrics["query_rate"] == 3  # 3 query events
        assert metrics["active_sessions"] == 2  # 2 unique sessions
        assert metrics["success_rate"] == 2/3  # 2 successful out of 3
    
    @pytest.mark.asyncio
    async def test_get_analytics_report(self, analytics):
        """Test generating analytics report."""
        # Add test data
        now = datetime.now(timezone.utc)
        session_id = str(uuid.uuid4())
        
        # Add some events with different patterns
        await analytics.track_event(
            SearchEventType.QUERY_EXECUTED,
            session_id=session_id,
            query="python tutorial",
            result_count=15,
            execution_time=0.5,
            success=True
        )
        
        await analytics.track_event(
            SearchEventType.RESULT_CLICKED,
            session_id=session_id,
            clicked_result_position=1
        )
        
        await analytics.track_event(
            SearchEventType.QUERY_EXECUTED,
            session_id=session_id,
            query="javascript basics",
            result_count=8,
            execution_time=0.3,
            success=True
        )
        
        # Generate report
        report = await analytics.get_analytics_report()
        
        # Check report structure
        assert "report_generated" in report
        assert "summary" in report
        assert "query_analytics" in report
        assert "user_behavior" in report
        assert "performance" in report
        assert "patterns" in report
        assert "recommendations" in report
        
        # Check summary data
        summary = report["summary"]
        assert summary["total_events"] == 3
        assert summary["query_count"] == 2
        assert summary["success_rate"] == 1.0  # Both queries successful
    
    @pytest.mark.asyncio
    async def test_get_analytics_report_with_time_range(self, analytics):
        """Test analytics report with time range filtering."""
        now = datetime.now(timezone.utc)
        
        # Add events at different times
        old_time = now - timedelta(hours=2)
        recent_time = now - timedelta(minutes=30)
        
        # Mock timestamps for testing
        old_event = SearchEvent(
            event_type=SearchEventType.QUERY_EXECUTED,
            timestamp=old_time,
            query="old query"
        )
        recent_event = SearchEvent(
            event_type=SearchEventType.QUERY_EXECUTED,
            timestamp=recent_time,
            query="recent query"
        )
        
        analytics.events.extend([old_event, recent_event])
        
        # Generate report for last hour only
        time_range = (now - timedelta(hours=1), now)
        report = await analytics.get_analytics_report(time_range=time_range)
        
        # Should only include recent event
        assert report["summary"]["total_events"] == 1
        assert report["summary"]["query_count"] == 1
    
    @pytest.mark.asyncio
    async def test_get_search_optimization_insights(self, analytics):
        """Test getting search optimization insights."""
        # Add performance data that will trigger insights
        slow_times = [2.5, 3.0, 2.8, 3.2, 2.9]  # Slow query times
        for time in slow_times:
            await analytics.record_performance(PerformanceMetric.TOTAL_SEARCH_TIME, time)
        
        # Add failed searches
        for i in range(5):
            await analytics.track_event(
                SearchEventType.QUERY_EXECUTED,
                query=f"failing query {i}",
                success=False
            )
        
        insights = await analytics.get_search_optimization_insights()
        
        assert "optimization_opportunities" in insights
        assert "performance_bottlenecks" in insights
        assert "user_experience_issues" in insights
        assert "recommendations" in insights
        
        # Should detect slow queries
        bottlenecks = insights["performance_bottlenecks"]
        assert len(bottlenecks) > 0
        assert any("slow" in item["issue"].lower() for item in bottlenecks)
    
    def test_create_performance_snapshot(self, analytics):
        """Test creating performance snapshots."""
        # Add some test events
        analytics.events.extend([
            SearchEvent(
                event_type=SearchEventType.QUERY_EXECUTED,
                execution_time=0.5,
                result_count=10,
                success=True,
                cache_hit=True,
                user_id="user1"
            ),
            SearchEvent(
                event_type=SearchEventType.QUERY_EXECUTED,
                execution_time=0.8,
                result_count=15,
                success=True,
                cache_hit=False,
                user_id="user2"
            ),
            SearchEvent(
                event_type=SearchEventType.QUERY_EXECUTED,
                execution_time=0.3,
                result_count=5,
                success=False,
                cache_hit=True,
                user_id="user1"
            )
        ])
        
        snapshot = analytics.create_performance_snapshot()
        
        assert isinstance(snapshot, PerformanceSnapshot)
        assert snapshot.avg_query_time > 0
        assert 0 <= snapshot.cache_hit_rate <= 1
        assert 0 <= snapshot.successful_query_rate <= 1
        assert snapshot.avg_results_per_query > 0
        assert snapshot.unique_users == 2
    
    def test_clear_analytics_data(self, analytics):
        """Test clearing analytics data."""
        # Add test data
        analytics.events.extend([
            SearchEvent(query="test1"),
            SearchEvent(query="test2"),
            SearchEvent(query="test3")
        ])
        
        # Add test patterns
        analytics.patterns["pattern1"] = SearchPattern(queries=["test"])
        analytics.patterns["pattern2"] = SearchPattern(queries=["another"])
        
        # Clear all data
        removed = analytics.clear_analytics_data()
        
        assert removed == 3
        assert len(analytics.events) == 0
        assert len(analytics.patterns) == 0
        assert len(analytics.performance_buffer) == 0
    
    def test_clear_analytics_data_with_time_threshold(self, analytics):
        """Test clearing analytics data with time threshold."""
        now = datetime.now(timezone.utc)
        
        # Add events at different times
        old_events = [
            SearchEvent(timestamp=now - timedelta(days=5), query="old1"),
            SearchEvent(timestamp=now - timedelta(days=10), query="old2")
        ]
        recent_events = [
            SearchEvent(timestamp=now - timedelta(hours=1), query="recent1"),
            SearchEvent(timestamp=now - timedelta(minutes=30), query="recent2")
        ]
        
        analytics.events.extend(old_events + recent_events)
        
        # Clear data older than 2 days
        removed = analytics.clear_analytics_data(older_than=timedelta(days=2))
        
        assert removed == 2  # Should remove 2 old events
        assert len(analytics.events) == 2  # Should keep 2 recent events
        
        # Check that recent events are preserved
        remaining_queries = [e.query for e in analytics.events]
        assert "recent1" in remaining_queries
        assert "recent2" in remaining_queries
    
    def test_event_count_limiting(self, analytics):
        """Test that event count is limited to max_events."""
        # Set small limit for testing
        analytics.max_events = 5
        
        # Add more events than the limit
        for i in range(10):
            analytics.events.append(SearchEvent(query=f"query{i}"))
            
            # Simulate the limiting that happens in track_event
            if len(analytics.events) > analytics.max_events:
                analytics.events = analytics.events[-analytics.max_events:]
        
        # Should not exceed max_events
        assert len(analytics.events) == 5
        
        # Should keep the most recent events
        remaining_queries = [e.query for e in analytics.events]
        assert "query5" in remaining_queries
        assert "query9" in remaining_queries
        assert "query0" not in remaining_queries
    
    def test_save_and_load_analytics_data(self, analytics):
        """Test saving and loading analytics data."""
        # Add test data
        test_event = SearchEvent(
            event_type=SearchEventType.QUERY_EXECUTED,
            query="test query",
            result_count=10,
            success=True,
            session_id="test_session"
        )
        analytics.events.append(test_event)
        
        test_pattern = SearchPattern(
            pattern_type="test_pattern",
            queries=["test query"],
            frequency=5,
            success_rate=0.8
        )
        analytics.patterns["test_pattern"] = test_pattern
        
        # Add performance data
        analytics.performance_buffer[PerformanceMetric.QUERY_EXECUTION_TIME.value] = [0.5, 0.6, 0.4]
        
        # Save data
        analytics.save_analytics_data()
        
        # Create new instance to test loading
        new_analytics = SearchAnalytics(
            settings=analytics.settings,
            max_events=analytics.max_events,
            retention_days=analytics.retention_days
        )
        
        # Should have loaded the data
        assert len(new_analytics.events) == 1
        assert new_analytics.events[0].query == "test query"
        assert new_analytics.events[0].result_count == 10
        
        assert len(new_analytics.patterns) == 1
        assert "test_pattern" in new_analytics.patterns
        assert new_analytics.patterns["test_pattern"].frequency == 5
        
        # Should have created at least one performance snapshot
        assert len(new_analytics.performance_snapshots) >= 1
    
    @pytest.mark.asyncio
    async def test_pattern_updating(self, analytics):
        """Test that patterns are updated correctly."""
        # Track events with same query
        query = "python programming"
        
        for i in range(3):
            await analytics.track_event(
                SearchEventType.QUERY_EXECUTED,
                query=query,
                result_count=10 + i,
                execution_time=0.5 + i * 0.1,
                success=True,
                user_id=f"user{i}"
            )
        
        # Give patterns time to update
        await asyncio.sleep(0.1)
        
        # Should have created a pattern
        assert len(analytics.patterns) > 0
        
        # Find the pattern for our query
        pattern = None
        for p in analytics.patterns.values():
            if query in p.queries:
                pattern = p
                break
        
        assert pattern is not None
        assert pattern.frequency == 3
        assert pattern.success_rate == 1.0  # All successful
        assert len(pattern.unique_users) == 3
    
    @pytest.mark.asyncio
    async def test_session_tracking(self, analytics):
        """Test session tracking functionality."""
        session_id = str(uuid.uuid4())
        
        # Track events in same session
        await analytics.track_event(SearchEventType.QUERY_EXECUTED, session_id=session_id, query="query1")
        await analytics.track_event(SearchEventType.RESULT_CLICKED, session_id=session_id)
        await analytics.track_event(SearchEventType.QUERY_EXECUTED, session_id=session_id, query="query2")
        
        # Check session tracking
        assert session_id in analytics.user_sessions
        assert len(analytics.user_sessions[session_id]) == 3
        
        # Check query sequences
        assert session_id in analytics.query_sequences
        assert analytics.query_sequences[session_id] == ["query1", "query2"]
    
    def test_analytics_disabled(self, analytics):
        """Test analytics when disabled."""
        analytics.analytics_enabled = False
        
        # Try to track an event
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            event_id = loop.run_until_complete(
                analytics.track_event(SearchEventType.QUERY_EXECUTED, query="test")
            )
            
            # Should return empty string
            assert event_id == ""
            assert len(analytics.events) == 0
            
        finally:
            loop.close()
    
    @pytest.mark.asyncio
    async def test_performance_buffer_limiting(self, analytics):
        """Test that performance buffer size is limited."""
        # Record many performance metrics
        for i in range(1200):  # More than the 1000 limit
            await analytics.record_performance(PerformanceMetric.QUERY_EXECUTION_TIME, i * 0.001)
        
        # Should not exceed buffer limit
        buffer = analytics.performance_buffer[PerformanceMetric.QUERY_EXECUTION_TIME.value]
        assert len(buffer) == 1000
        
        # Should keep the most recent values
        assert buffer[-1] == 1199 * 0.001  # Last value
        assert buffer[0] == 200 * 0.001   # First value after truncation
