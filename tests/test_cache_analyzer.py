"""
Tests for Cache Analytics System (CacheAnalyzer).

Comprehensive test suite covering cache analysis, usage pattern detection,
performance metrics, and recommendation generation.
"""

import pytest
import asyncio
import tempfile
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.storage.cache_analyzer import (
    CacheAnalyzer,
    CacheStats,
    UsagePattern,
    PerformanceMetrics,
    AnalysisReport
)
from src.config.settings import get_settings


class TestCacheAnalyzer:
    """Test cases for CacheAnalyzer functionality."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_settings(self, temp_cache_dir):
        """Mock settings with temporary cache directory."""
        settings = Mock()
        settings.cache_dir = str(temp_cache_dir)
        return settings
    
    @pytest.fixture
    def analyzer(self, temp_cache_dir, mock_settings):
        """Create CacheAnalyzer instance with mocked settings."""
        with patch('src.storage.cache_analyzer.get_settings', return_value=mock_settings):
            analyzer = CacheAnalyzer()
            analyzer.cache_dir = temp_cache_dir
            analyzer.db_path = temp_cache_dir / "cache.db"
            analyzer.analytics_db_path = temp_cache_dir / "analytics.db"
            return analyzer
    
    @pytest.fixture
    def sample_cache_db(self, temp_cache_dir):
        """Create sample cache database for testing."""
        db_path = temp_cache_dir / "cache.db"
        
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE pages (
                    page_id TEXT PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    notebook_id TEXT,
                    notebook_name TEXT,
                    section_id TEXT,
                    created_time TEXT,
                    last_modified_time TEXT
                )
            """)
            
            # Insert sample data
            sample_data = [
                ('page1', 'Meeting Notes', 'Content for meeting notes' * 100, 'nb1', 'Work Notebook', 'sec1', 
                 '2025-01-01T10:00:00', '2025-01-15T10:00:00'),
                ('page2', 'Project Plan', 'Project planning content' * 150, 'nb1', 'Work Notebook', 'sec1',
                 '2025-01-10T14:00:00', '2025-01-20T14:00:00'),
                ('page3', 'Old Notes', 'Old content' * 50, 'nb2', 'Archive', 'sec2',
                 '2024-06-01T10:00:00', '2024-06-01T10:00:00'),
            ]
            
            conn.executemany("""
                INSERT INTO pages VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, sample_data)
            conn.commit()
        
        return db_path
    
    @pytest.fixture
    def sample_analytics_db(self, analyzer):
        """Create sample analytics database for testing."""
        analyzer._setup_analytics_db()
        
        with sqlite3.connect(analyzer.analytics_db_path) as conn:
            # Insert sample search analytics
            search_data = [
                ('2025-01-20T10:00:00', 'meeting notes', 5, 150.0, True),
                ('2025-01-20T10:30:00', 'project plan', 3, 120.0, True),
                ('2025-01-20T11:00:00', 'important tasks', 8, 200.0, True),
                ('2025-01-20T14:00:00', 'meeting notes', 5, 100.0, True),
            ]
            
            conn.executemany("""
                INSERT INTO search_analytics (timestamp, query, results_count, search_time_ms, cache_hit)
                VALUES (?, ?, ?, ?, ?)
            """, search_data)
            
            # Insert sample page access data
            access_data = [
                ('2025-01-20T10:00:00', 'page1', 'Meeting Notes', 'search'),
                ('2025-01-20T10:30:00', 'page2', 'Project Plan', 'search'),
                ('2025-01-20T14:00:00', 'page1', 'Meeting Notes', 'search'),
            ]
            
            conn.executemany("""
                INSERT INTO page_access (timestamp, page_id, page_title, access_type)
                VALUES (?, ?, ?, ?)
            """, access_data)
            
            conn.commit()
        
        return analyzer.analytics_db_path
    
    @pytest.mark.asyncio
    async def test_analyze_cache_stats_basic(self, analyzer, sample_cache_db):
        """Test basic cache statistics analysis."""
        stats = await analyzer._analyze_cache_stats()
        
        assert stats.total_pages == 3
        assert stats.notebooks_count == 2
        assert stats.sections_count == 2
        assert stats.total_size_bytes > 0
        assert stats.avg_page_size_bytes > 0
        assert stats.oldest_content is not None
        assert stats.newest_content is not None
    
    @pytest.mark.asyncio
    async def test_analyze_cache_stats_empty_db(self, analyzer):
        """Test cache stats with no database."""
        stats = await analyzer._analyze_cache_stats()
        
        assert stats.total_pages == 0
        assert stats.notebooks_count == 0
        assert stats.sections_count == 0
        assert stats.total_size_bytes == 0
        assert stats.avg_page_size_bytes == 0.0
    
    @pytest.mark.asyncio
    async def test_analyze_usage_patterns(self, analyzer, sample_analytics_db):
        """Test usage pattern analysis."""
        patterns = await analyzer._analyze_usage_patterns()
        
        assert len(patterns.most_searched_terms) > 0
        assert patterns.most_searched_terms[0][0] == 'meeting notes'  # Most frequent
        assert patterns.most_searched_terms[0][1] == 2  # Appeared twice
        assert len(patterns.popular_pages) > 0
        assert patterns.avg_searches_per_day > 0
    
    @pytest.mark.asyncio
    async def test_analyze_usage_patterns_empty(self, analyzer):
        """Test usage patterns with no analytics data."""
        patterns = await analyzer._analyze_usage_patterns()
        
        assert patterns.most_searched_terms == []
        assert patterns.popular_pages == []
        assert patterns.avg_searches_per_day == 0.0
        assert patterns.peak_usage_hours == []
    
    @pytest.mark.asyncio
    async def test_analyze_performance_metrics(self, analyzer, sample_analytics_db):
        """Test performance metrics analysis."""
        metrics = await analyzer._analyze_performance()
        
        assert metrics.avg_search_time_ms > 0
        assert metrics.fastest_search_ms > 0
        assert metrics.slowest_search_ms > 0
        assert metrics.cache_hit_rate == 100.0  # All cache hits in sample data
        assert metrics.index_health_score > 0
    
    @pytest.mark.asyncio
    async def test_full_cache_analysis(self, analyzer, sample_cache_db, sample_analytics_db):
        """Test complete cache analysis workflow."""
        report = await analyzer.analyze_cache()
        
        assert isinstance(report, AnalysisReport)
        assert report.timestamp is not None
        assert isinstance(report.cache_stats, CacheStats)
        assert isinstance(report.usage_patterns, UsagePattern)
        assert isinstance(report.performance_metrics, PerformanceMetrics)
        assert isinstance(report.recommendations, list)
        assert len(report.recommendations) > 0
        assert 0.0 <= report.health_score <= 100.0
    
    @pytest.mark.asyncio
    async def test_generate_recommendations_large_cache(self, analyzer):
        """Test recommendations for large cache scenario."""
        # Mock large cache stats
        cache_stats = CacheStats(
            total_pages=1000,
            total_size_bytes=2 * 1024 * 1024 * 1024,  # 2GB
            avg_page_size_bytes=2048000,
            notebooks_count=20,
            sections_count=50,
            oldest_content=datetime.now() - timedelta(days=200),
            newest_content=datetime.now() - timedelta(days=1),
            last_sync=datetime.now() - timedelta(days=10)
        )
        
        usage_patterns = UsagePattern([], [], {}, {}, 10.0, [])
        performance_metrics = PerformanceMetrics(800.0, 100.0, 2000.0, 95.0, 60.0, 85.0)
        
        recommendations = await analyzer._generate_recommendations(
            cache_stats, usage_patterns, performance_metrics
        )
        
        # Should recommend cleanup for large cache
        assert any('large' in rec.lower() or 'cleanup' in rec.lower() for rec in recommendations)
        # Should recommend performance improvements for slow searches
        assert any('performance' in rec.lower() or 'index' in rec.lower() for rec in recommendations)
    
    @pytest.mark.asyncio
    async def test_generate_recommendations_outdated_sync(self, analyzer):
        """Test recommendations for outdated sync scenario."""
        cache_stats = CacheStats(
            total_pages=100,
            total_size_bytes=50 * 1024 * 1024,  # 50MB
            avg_page_size_bytes=500000,
            notebooks_count=5,
            sections_count=10,
            oldest_content=datetime.now() - timedelta(days=90),
            newest_content=datetime.now() - timedelta(days=30),
            last_sync=datetime.now() - timedelta(days=15)  # 15 days old
        )
        
        usage_patterns = UsagePattern([], [], {}, {}, 5.0, [])
        performance_metrics = PerformanceMetrics(300.0, 50.0, 800.0, 98.0, 85.0, 90.0)
        
        recommendations = await analyzer._generate_recommendations(
            cache_stats, usage_patterns, performance_metrics
        )
        
        # Should recommend sync for old content
        assert any('sync' in rec.lower() for rec in recommendations)
    
    def test_calculate_health_score_excellent(self, analyzer):
        """Test health score calculation for excellent performance."""
        cache_stats = CacheStats(
            total_pages=200,
            total_size_bytes=100 * 1024 * 1024,  # 100MB
            avg_page_size_bytes=500000,
            notebooks_count=10,
            sections_count=20,
            oldest_content=datetime.now() - timedelta(days=30),
            newest_content=datetime.now() - timedelta(days=1),
            last_sync=datetime.now() - timedelta(hours=2)  # Very recent
        )
        
        usage_patterns = UsagePattern([], [], {}, {}, 20.0, [])
        performance_metrics = PerformanceMetrics(200.0, 50.0, 400.0, 99.0, 95.0, 92.0)
        
        score = analyzer._calculate_health_score(cache_stats, usage_patterns, performance_metrics)
        
        assert score >= 90.0  # Should be excellent
    
    def test_calculate_health_score_poor(self, analyzer):
        """Test health score calculation for poor performance."""
        cache_stats = CacheStats(
            total_pages=5,
            total_size_bytes=1024 * 1024,  # 1MB - very small
            avg_page_size_bytes=200000,
            notebooks_count=1,
            sections_count=1,
            oldest_content=datetime.now() - timedelta(days=180),
            newest_content=datetime.now() - timedelta(days=60),
            last_sync=datetime.now() - timedelta(days=45)  # Very old
        )
        
        usage_patterns = UsagePattern([], [], {}, {}, 1.0, [])  # Low usage
        performance_metrics = PerformanceMetrics(2000.0, 500.0, 5000.0, 80.0, 40.0, 60.0)
        
        score = analyzer._calculate_health_score(cache_stats, usage_patterns, performance_metrics)
        
        assert score <= 50.0  # Should be poor
    
    @pytest.mark.asyncio
    async def test_track_search_analytics(self, analyzer):
        """Test search analytics tracking."""
        analyzer._setup_analytics_db()
        
        await analyzer.track_search("test query", 5, 150.0, True)
        
        # Verify data was recorded
        with sqlite3.connect(analyzer.analytics_db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM search_analytics")
            count = cursor.fetchone()[0]
            assert count == 1
            
            cursor = conn.execute("SELECT query, results_count, search_time_ms FROM search_analytics")
            result = cursor.fetchone()
            assert result[0] == "test query"
            assert result[1] == 5
            assert result[2] == 150.0
    
    @pytest.mark.asyncio
    async def test_track_page_access(self, analyzer):
        """Test page access tracking."""
        analyzer._setup_analytics_db()
        
        await analyzer.track_page_access("page123", "Test Page", "search")
        
        # Verify data was recorded
        with sqlite3.connect(analyzer.analytics_db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM page_access")
            count = cursor.fetchone()[0]
            assert count == 1
            
            cursor = conn.execute("SELECT page_id, page_title, access_type FROM page_access")
            result = cursor.fetchone()
            assert result[0] == "page123"
            assert result[1] == "Test Page"
            assert result[2] == "search"
    
    @pytest.mark.asyncio
    async def test_export_report(self, analyzer, temp_cache_dir):
        """Test report export functionality."""
        # Create a basic report
        cache_stats = CacheStats(100, 50000000, 500000, 5, 10, None, None, datetime.now())
        usage_patterns = UsagePattern([], [], {}, {}, 5.0, [])
        performance_metrics = PerformanceMetrics(300.0, 100.0, 800.0, 95.0, 85.0, 90.0)
        
        report = AnalysisReport(
            timestamp=datetime.now(),
            cache_stats=cache_stats,
            usage_patterns=usage_patterns,
            performance_metrics=performance_metrics,
            recommendations=["Test recommendation"],
            health_score=85.0
        )
        
        # Export to JSON
        output_path = temp_cache_dir / "test_report.json"
        await analyzer.export_report(report, output_path)
        
        assert output_path.exists()
        
        # Verify content is valid JSON
        import json
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert 'timestamp' in data
            assert 'health_score' in data
            assert data['health_score'] == 85.0
    
    @pytest.mark.asyncio
    async def test_analyze_cache_error_handling(self, analyzer):
        """Test error handling in cache analysis."""
        # Force error by using invalid database path
        analyzer.db_path = Path("/invalid/path/cache.db")
        analyzer.analytics_db_path = Path("/invalid/path/analytics.db")
        
        report = await analyzer.analyze_cache()
        
        # Should return basic empty report instead of raising exception
        assert isinstance(report, AnalysisReport)
        assert report.health_score == 0.0
        assert report.cache_stats.total_pages == 0
    
    @pytest.mark.asyncio
    async def test_analytics_db_setup_failure(self, analyzer):
        """Test graceful handling of analytics DB setup failure."""
        # Mock database connection failure
        with patch('sqlite3.connect', side_effect=Exception("DB connection failed")):
            # Should not raise exception
            analyzer._setup_analytics_db()
            
            # Analytics tracking should also handle failures gracefully
            await analyzer.track_search("test", 1, 100.0)
            await analyzer.track_page_access("page1", "Title")
    
    def test_empty_cache_stats_creation(self, analyzer):
        """Test creation of empty cache stats."""
        stats = CacheStats(0, 0, 0.0, 0, 0, None, None, None)
        
        assert stats.total_pages == 0
        assert stats.total_size_bytes == 0
        assert stats.avg_page_size_bytes == 0.0
        assert stats.notebooks_count == 0
        assert stats.sections_count == 0
        assert stats.oldest_content is None
        assert stats.newest_content is None
        assert stats.last_sync is None
    
    def test_usage_pattern_creation(self, analyzer):
        """Test creation of usage pattern objects."""
        patterns = UsagePattern(
            most_searched_terms=[("test", 5), ("query", 3)],
            popular_pages=[("page1", 10), ("page2", 7)],
            search_frequency_by_hour={9: 5, 10: 8, 14: 12},
            notebook_access_frequency={"notebook1": 20, "notebook2": 15},
            avg_searches_per_day=15.5,
            peak_usage_hours=[10, 14, 15]
        )
        
        assert len(patterns.most_searched_terms) == 2
        assert patterns.most_searched_terms[0][0] == "test"
        assert patterns.avg_searches_per_day == 15.5
        assert 14 in patterns.peak_usage_hours
    
    def test_performance_metrics_creation(self, analyzer):
        """Test creation of performance metrics objects."""
        metrics = PerformanceMetrics(
            avg_search_time_ms=250.5,
            fastest_search_ms=50.0,
            slowest_search_ms=1000.0,
            cache_hit_rate=98.5,
            index_health_score=92.0,
            storage_efficiency=87.5
        )
        
        assert metrics.avg_search_time_ms == 250.5
        assert metrics.cache_hit_rate == 98.5
        assert metrics.index_health_score == 92.0
        assert metrics.storage_efficiency == 87.5
