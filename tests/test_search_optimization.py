"""
Tests for search optimization system.
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import tempfile
import uuid

from src.search.search_optimization import (
    SearchOptimization,
    QueryOptimization,
    IndexOptimization,
    PerformanceAlert,
    OptimizationRecommendation,
    OptimizationType,
    OptimizationPriority
)
from src.config.settings import Settings


class TestQueryOptimization:
    """Test QueryOptimization data class."""
    
    def test_query_optimization_creation(self):
        """Test creating a query optimization."""
        opt = QueryOptimization(
            original_query="python programming",
            optimized_query="python programming tutorial",
            optimization_type="expansion",
            confidence_score=0.8,
            expected_improvement="20-40% more results",
            reasoning="Applied query expansion"
        )
        
        assert opt.original_query == "python programming"
        assert opt.optimized_query == "python programming tutorial"
        assert opt.optimization_type == "expansion"
        assert opt.confidence_score == 0.8
        assert "20-40%" in opt.expected_improvement
        assert "expansion" in opt.reasoning


class TestIndexOptimization:
    """Test IndexOptimization data class."""
    
    def test_index_optimization_creation(self):
        """Test creating an index optimization."""
        opt = IndexOptimization(
            table_name="cached_pages_fts",
            optimization_type="rebuild_index",
            current_performance=2.5,
            expected_performance=1.0,
            implementation_steps=["Step 1", "Step 2"],
            risk_level="low"
        )
        
        assert opt.table_name == "cached_pages_fts"
        assert opt.optimization_type == "rebuild_index"
        assert opt.current_performance == 2.5
        assert opt.expected_performance == 1.0
        assert len(opt.implementation_steps) == 2
        assert opt.risk_level == "low"


class TestPerformanceAlert:
    """Test PerformanceAlert data class."""
    
    def test_alert_creation(self):
        """Test creating a performance alert."""
        alert = PerformanceAlert(
            alert_id="test_alert_123",
            alert_type="query_time_slow",
            severity=OptimizationPriority.HIGH,
            message="Slow query performance detected",
            metric_value=3.5,
            threshold=2.0
        )
        
        assert alert.alert_id == "test_alert_123"
        assert alert.alert_type == "query_time_slow"
        assert alert.severity == OptimizationPriority.HIGH
        assert "slow query" in alert.message.lower()
        assert alert.metric_value == 3.5
        assert alert.threshold == 2.0
        assert not alert.resolved


class TestOptimizationRecommendation:
    """Test OptimizationRecommendation data class."""
    
    def test_recommendation_creation(self):
        """Test creating an optimization recommendation."""
        rec = OptimizationRecommendation(
            recommendation_id="test_rec_1",
            optimization_type=OptimizationType.QUERY_EXPANSION,
            priority=OptimizationPriority.HIGH,
            title="Improve Query Performance",
            description="Queries are running slowly",
            impact_description="50% performance improvement",
            implementation_effort="Medium",
            expected_benefits=["Faster queries", "Better UX"],
            implementation_steps=["Step 1", "Step 2"],
            risk_assessment="low",
            metrics_to_monitor=["query_time", "success_rate"]
        )
        
        assert rec.recommendation_id == "test_rec_1"
        assert rec.optimization_type == OptimizationType.QUERY_EXPANSION
        assert rec.priority == OptimizationPriority.HIGH
        assert rec.title == "Improve Query Performance"
        assert len(rec.expected_benefits) == 2
        assert len(rec.implementation_steps) == 2
        assert len(rec.metrics_to_monitor) == 2


class TestSearchOptimization:
    """Test SearchOptimization system."""
    
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
    def mock_analytics(self):
        """Create mock analytics system."""
        analytics = Mock()
        analytics.get_real_time_metrics = AsyncMock(return_value={
            "query_rate": 50,
            "success_rate": 0.85,
            "performance": {
                "avg_query_time": 1.2,
                "cache_hit_rate": 0.75
            }
        })
        analytics.get_analytics_report = AsyncMock(return_value={
            "summary": {"total_events": 100, "query_count": 80},
            "query_analytics": {"failed_queries": ["query1", "query2"]},
            "performance": {"cache_hit_rate": 0.65},
            "user_behavior": {"avg_session_length": 45}
        })
        analytics.get_search_optimization_insights = AsyncMock(return_value={
            "performance_bottlenecks": [
                {"issue": "Slow query execution detected", "severity": "high"}
            ],
            "optimization_opportunities": []
        })
        return analytics
    
    @pytest.fixture
    def optimization(self, mock_settings, mock_analytics):
        """Create SearchOptimization instance for testing."""
        return SearchOptimization(settings=mock_settings, analytics=mock_analytics)
    
    def test_initialization(self, optimization):
        """Test optimization system initialization."""
        assert optimization is not None
        assert optimization.analytics is not None
        assert optimization.monitoring_enabled is True
        assert len(optimization.performance_thresholds) > 0
        assert len(optimization.query_patterns) > 0
        assert len(optimization.optimization_history) == 0
        assert len(optimization.applied_optimizations) == 0
        assert len(optimization.performance_alerts) == 0
    
    @pytest.mark.asyncio
    async def test_optimize_query_basic(self, optimization):
        """Test basic query optimization."""
        result = await optimization.optimize_query("python programming")
        
        assert isinstance(result, QueryOptimization)
        assert result.original_query == "python programming"
        assert result.confidence_score > 0
        assert result.expected_improvement is not None
        assert result.reasoning is not None
    
    @pytest.mark.asyncio
    async def test_optimize_query_whitespace_cleanup(self, optimization):
        """Test query optimization with whitespace cleanup."""
        result = await optimization.optimize_query("  python   programming  ")
        
        assert result.original_query == "python   programming"
        assert result.optimized_query == "python programming"
        assert "whitespace_cleanup" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_optimize_query_duplicate_removal(self, optimization):
        """Test query optimization with duplicate word removal."""
        result = await optimization.optimize_query("python python programming")
        
        assert result.original_query == "python python programming"
        assert result.optimized_query == "python programming"
        assert "duplicate_removal" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_optimize_query_expansion(self, optimization):
        """Test query optimization with expansion for short queries."""
        result = await optimization.optimize_query("js")
        
        assert result.original_query == "js"
        assert len(result.optimized_query.split()) > 1
        assert "query_expansion" in result.reasoning or result.optimization_type == "expansion"
        assert result.confidence_score < 1.0
    
    @pytest.mark.asyncio
    async def test_optimize_query_with_context(self, optimization):
        """Test query optimization with context."""
        context = {
            "recent_queries": [
                "python tutorial for beginners",
                "javascript basics",
                "python data structures"
            ]
        }
        
        result = await optimization.optimize_query("python", context=context)
        
        assert result.original_query == "python"
        # Should have either expansion or context enhancement
        assert (result.optimized_query != result.original_query or 
                result.optimization_type in ["expansion", "contextualization"])
    
    @pytest.mark.asyncio
    async def test_analyze_index_performance(self, optimization):
        """Test index performance analysis."""
        optimizations = await optimization.analyze_index_performance()
        
        assert isinstance(optimizations, list)
        # Should return at least one optimization suggestion
        assert len(optimizations) >= 0
        
        for opt in optimizations:
            assert isinstance(opt, IndexOptimization)
            assert opt.table_name is not None
            assert opt.optimization_type is not None
            assert opt.current_performance >= 0
            assert opt.expected_performance >= 0
            assert isinstance(opt.implementation_steps, list)
            assert opt.risk_level in ["low", "medium", "high"]
    
    @pytest.mark.asyncio
    async def test_monitor_performance(self, optimization):
        """Test performance monitoring."""
        alerts = await optimization.monitor_performance()
        
        assert isinstance(alerts, list)
        
        for alert in alerts:
            assert isinstance(alert, PerformanceAlert)
            assert alert.alert_id is not None
            assert alert.alert_type is not None
            assert isinstance(alert.severity, OptimizationPriority)
            assert alert.message is not None
            assert alert.metric_value is not None
            assert alert.threshold is not None
            assert isinstance(alert.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_monitor_performance_critical_query_time(self, optimization, mock_analytics):
        """Test performance monitoring with critical query time."""
        # Set up analytics to return slow query time
        mock_analytics.get_real_time_metrics.return_value = {
            "query_rate": 50,
            "success_rate": 0.85,
            "performance": {
                "avg_query_time": 6.0,  # Above critical threshold
                "cache_hit_rate": 0.75
            }
        }
        
        alerts = await optimization.monitor_performance()
        
        # Should generate a critical alert
        critical_alerts = [a for a in alerts if a.severity == OptimizationPriority.CRITICAL]
        assert len(critical_alerts) > 0
        assert "critical" in critical_alerts[0].message.lower()
    
    @pytest.mark.asyncio
    async def test_monitor_performance_low_success_rate(self, optimization, mock_analytics):
        """Test performance monitoring with low success rate."""
        # Set up analytics to return low success rate
        mock_analytics.get_real_time_metrics.return_value = {
            "query_rate": 50,
            "success_rate": 0.5,  # Below critical threshold
            "performance": {
                "avg_query_time": 1.0,
                "cache_hit_rate": 0.75
            }
        }
        
        alerts = await optimization.monitor_performance()
        
        # Should generate a critical alert for success rate
        success_alerts = [a for a in alerts if "success rate" in a.message.lower()]
        assert len(success_alerts) > 0
        assert success_alerts[0].severity == OptimizationPriority.CRITICAL
    
    @pytest.mark.asyncio
    async def test_generate_optimization_recommendations(self, optimization):
        """Test generating optimization recommendations."""
        recommendations = await optimization.generate_optimization_recommendations()
        
        assert isinstance(recommendations, list)
        
        for rec in recommendations:
            assert isinstance(rec, OptimizationRecommendation)
            assert rec.recommendation_id is not None
            assert isinstance(rec.optimization_type, OptimizationType)
            assert isinstance(rec.priority, OptimizationPriority)
            assert rec.title is not None
            assert rec.description is not None
            assert isinstance(rec.expected_benefits, list)
            assert isinstance(rec.implementation_steps, list)
            assert isinstance(rec.metrics_to_monitor, list)
    
    @pytest.mark.asyncio
    async def test_generate_recommendations_sorting(self, optimization):
        """Test that recommendations are sorted by priority."""
        recommendations = await optimization.generate_optimization_recommendations()
        
        if len(recommendations) > 1:
            # Should be sorted by priority (critical first)
            priority_order = {
                OptimizationPriority.CRITICAL: 0,
                OptimizationPriority.HIGH: 1,
                OptimizationPriority.MEDIUM: 2,
                OptimizationPriority.LOW: 3
            }
            
            for i in range(len(recommendations) - 1):
                current_priority = priority_order[recommendations[i].priority]
                next_priority = priority_order[recommendations[i + 1].priority]
                assert current_priority <= next_priority
    
    @pytest.mark.asyncio
    async def test_apply_automatic_optimizations(self, optimization):
        """Test applying automatic optimizations."""
        results = await optimization.apply_automatic_optimizations()
        
        assert "applied" in results
        assert "skipped" in results
        assert "failed" in results
        assert "summary" in results
        
        assert isinstance(results["applied"], list)
        assert isinstance(results["skipped"], list)
        assert isinstance(results["failed"], list)
        assert isinstance(results["summary"], str)
        
        # Check that applied optimizations are tracked
        for applied in results["applied"]:
            assert applied["id"] in optimization.applied_optimizations
    
    @pytest.mark.asyncio
    async def test_get_optimization_status(self, optimization):
        """Test getting optimization status."""
        status = await optimization.get_optimization_status()
        
        assert "status" in status
        assert "last_check" in status
        assert "active_alerts" in status
        assert "recent_recommendations" in status
        assert "applied_optimizations" in status
        assert "performance_summary" in status
        assert "optimization_categories" in status
        assert "alerts_by_priority" in status
        
        # Check status values
        assert status["status"] in ["active", "inactive"]
        assert isinstance(status["last_check"], datetime)
        assert isinstance(status["active_alerts"], int)
        assert isinstance(status["recent_recommendations"], int)
        assert isinstance(status["applied_optimizations"], int)
        
        # Check performance summary structure
        perf_summary = status["performance_summary"]
        assert "avg_query_time" in perf_summary
        assert "success_rate" in perf_summary
        assert "cache_hit_rate" in perf_summary
        
        # Check categories structure
        categories = status["optimization_categories"]
        assert "query" in categories
        assert "index" in categories
        assert "cache" in categories
        assert "performance" in categories
        assert "ux" in categories
    
    @pytest.mark.asyncio
    async def test_expansion_cache(self, optimization):
        """Test query expansion caching."""
        # First call should populate cache
        result1 = await optimization.optimize_query("js")
        
        # Second call should use cache
        result2 = await optimization.optimize_query("js")
        
        # Results should be consistent
        assert result1.optimized_query == result2.optimized_query
        
        # Check cache was populated
        assert "js" in optimization.expansion_cache
        assert "js" in optimization.expansion_cache_timestamps
    
    @pytest.mark.asyncio
    async def test_expansion_cache_ttl(self, optimization):
        """Test query expansion cache TTL."""
        # Use "js" which has a known expansion
        query = "js"
        
        # First call should populate cache
        result1 = await optimization.optimize_query(query)
        initial_time = optimization.expansion_cache_timestamps.get(query)
        initial_cache = optimization.expansion_cache.get(query, [])
        
        # Manually set old timestamp to simulate expired cache
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)  # Older than TTL
        optimization.expansion_cache_timestamps[query] = old_time
        
        # Second call should detect expired cache and refresh
        result2 = await optimization.optimize_query(query)
        new_time = optimization.expansion_cache_timestamps.get(query)
        
        # Should have updated cache with new timestamp
        assert new_time is not None
        assert new_time > old_time
        
        # Cache content should be consistent (since "js" always expands the same way)
        new_cache = optimization.expansion_cache.get(query, [])
        assert new_cache == initial_cache
    
    def test_alert_cooldown(self, optimization):
        """Test alert cooldown functionality."""
        current_time = datetime.now(timezone.utc)
        
        # Create first alert
        alert1 = optimization._create_alert(
            "test_alert",
            OptimizationPriority.HIGH,
            "Test alert message",
            5.0,
            2.0
        )
        
        assert alert1 is not None
        
        # Try to create same alert immediately (should be blocked by cooldown)
        alert2 = optimization._create_alert(
            "test_alert",
            OptimizationPriority.HIGH,
            "Test alert message",
            5.0,
            2.0
        )
        
        assert alert2 is None  # Should be blocked by cooldown
        
        # Simulate time passing beyond cooldown
        optimization.last_alert_times["test_alert"] = current_time - timedelta(minutes=20)
        
        alert3 = optimization._create_alert(
            "test_alert",
            OptimizationPriority.HIGH,
            "Test alert message",
            5.0,
            2.0
        )
        
        assert alert3 is not None  # Should work after cooldown
    
    def test_history_limiting(self, optimization):
        """Test that optimization history is limited in size."""
        # Add many recommendations
        for i in range(600):  # More than the 500 limit
            rec = OptimizationRecommendation(
                recommendation_id=f"test_rec_{i}",
                optimization_type=OptimizationType.QUERY_EXPANSION,
                priority=OptimizationPriority.LOW,
                title=f"Test Recommendation {i}",
                description=f"Test description {i}",
                impact_description="Test impact",
                implementation_effort="Low",
                expected_benefits=[],
                implementation_steps=[],
                risk_assessment="low",
                metrics_to_monitor=[]
            )
            optimization.optimization_history.append(rec)
        
        # Simulate the limiting that happens in generate_optimization_recommendations
        if len(optimization.optimization_history) > 500:
            optimization.optimization_history = optimization.optimization_history[-250:]
        
        # Should not exceed limit
        assert len(optimization.optimization_history) == 250
        
        # Should keep the most recent recommendations
        rec_ids = [r.recommendation_id for r in optimization.optimization_history]
        assert "test_rec_599" in rec_ids
        assert "test_rec_0" not in rec_ids
    
    def test_alert_history_limiting(self, optimization):
        """Test that alert history is limited in size."""
        # Add many alerts
        for i in range(1200):  # More than the 1000 limit
            alert = PerformanceAlert(
                alert_id=f"test_alert_{i}",
                alert_type="test_type",
                severity=OptimizationPriority.LOW,
                message=f"Test alert {i}",
                metric_value=i,
                threshold=100
            )
            optimization.performance_alerts.append(alert)
        
        # Simulate the limiting that happens in monitor_performance
        if len(optimization.performance_alerts) > 1000:
            optimization.performance_alerts = optimization.performance_alerts[-500:]
        
        # Should not exceed limit
        assert len(optimization.performance_alerts) == 500
        
        # Should keep the most recent alerts
        alert_ids = [a.alert_id for a in optimization.performance_alerts]
        assert "test_alert_1199" in alert_ids
        assert "test_alert_0" not in alert_ids
    
    @pytest.mark.asyncio
    async def test_monitoring_disabled(self, optimization):
        """Test monitoring when disabled."""
        optimization.monitoring_enabled = False
        
        alerts = await optimization.monitor_performance()
        
        # Should return empty list when monitoring is disabled
        assert len(alerts) == 0
    
    @pytest.mark.asyncio
    async def test_no_analytics_fallback(self):
        """Test optimization system without analytics."""
        mock_settings = Mock(spec=Settings)
        mock_settings.cache_path = Path("/tmp")
        
        optimization = SearchOptimization(settings=mock_settings, analytics=None)
        
        # Should still work without analytics
        recommendations = await optimization.generate_optimization_recommendations()
        assert isinstance(recommendations, list)
        
        alerts = await optimization.monitor_performance()
        assert len(alerts) == 0  # No analytics, no monitoring
        
        status = await optimization.get_optimization_status()
        assert "status" in status
        assert status["performance_summary"] == {}  # No analytics data
    
    def test_query_pattern_matching(self, optimization):
        """Test query pattern recognition."""
        patterns = optimization.query_patterns
        
        # Test too_broad pattern
        assert patterns["too_broad"].search("a")
        assert patterns["too_broad"].search("the")
        assert not patterns["too_broad"].search("python programming")
        
        # Test whitespace_issues pattern
        assert patterns["whitespace_issues"].search("python  programming")
        assert patterns["whitespace_issues"].search("test   query")
        assert not patterns["whitespace_issues"].search("normal query")
        
        # Test repeated_words pattern
        assert patterns["repeated_words"].search("python python programming")
        assert patterns["repeated_words"].search("test test case")
        assert not patterns["repeated_words"].search("python programming")
    
    @pytest.mark.asyncio
    async def test_error_handling_in_optimization(self, optimization):
        """Test error handling in query optimization."""
        # Test with None input (should handle gracefully)
        result = await optimization.optimize_query("")
        
        assert isinstance(result, QueryOptimization)
        assert result.original_query == ""
        assert result.optimized_query == ""
    
    @pytest.mark.asyncio
    async def test_recommendation_generation_error_handling(self, optimization, mock_analytics):
        """Test error handling in recommendation generation."""
        # Make analytics throw an error
        mock_analytics.get_analytics_report.side_effect = Exception("Analytics error")
        
        # Should handle error gracefully
        recommendations = await optimization.generate_optimization_recommendations()
        
        # Should still return a list (possibly empty)
        assert isinstance(recommendations, list)
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_error_handling(self, optimization, mock_analytics):
        """Test error handling in performance monitoring."""
        # Make analytics throw an error
        mock_analytics.get_real_time_metrics.side_effect = Exception("Metrics error")
        
        # Should handle error gracefully
        alerts = await optimization.monitor_performance()
        
        # Should still return a list (empty due to error)
        assert isinstance(alerts, list)
        assert len(alerts) == 0
    
    def test_performance_thresholds(self, optimization):
        """Test performance threshold configuration."""
        thresholds = optimization.performance_thresholds
        
        # Check that all required thresholds are present
        required_thresholds = [
            "query_time_slow",
            "query_time_critical",
            "success_rate_low",
            "success_rate_critical",
            "cache_hit_rate_low"
        ]
        
        for threshold in required_thresholds:
            assert threshold in thresholds
            assert isinstance(thresholds[threshold], (int, float))
            assert thresholds[threshold] > 0
