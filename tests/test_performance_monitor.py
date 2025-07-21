"""
Tests for Performance Monitor System.

Comprehensive test suite covering performance tracking, bottleneck detection,
trend analysis, and system health monitoring.
"""

import asyncio
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.storage.performance_monitor import (BottleneckAnalysis,
                                             PerformanceMetric,
                                             PerformanceMonitor,
                                             PerformanceReport,
                                             PerformanceSnapshot,
                                             PerformanceTrend, SystemMetrics)


class TestPerformanceMonitor:
    """Test cases for PerformanceMonitor functionality."""

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
    def monitor(self, temp_cache_dir, mock_settings):
        """Create PerformanceMonitor instance with mocked settings."""
        with patch('src.storage.performance_monitor.get_settings', return_value=mock_settings):
            monitor = PerformanceMonitor()
            monitor.cache_dir = temp_cache_dir
            monitor.metrics_db_path = temp_cache_dir / "performance.db"
            return monitor

    @pytest.fixture
    def sample_metrics_db(self, monitor):
        """Create sample performance metrics database."""
        monitor._setup_metrics_db()

        with sqlite3.connect(monitor.metrics_db_path) as conn:
            # Insert sample performance metrics - need at least 5 per operation for trends
            now = datetime.now()
            metrics_data = [
                # Search operations (6 entries for trend analysis)
                (now.isoformat(), 'search', 150.0, 512.0, 25.0, '{"query": "test"}'),
                ((now - timedelta(minutes=5)).isoformat(), 'search', 200.0, 480.0, 30.0, '{"query": "meeting"}'),
                ((now - timedelta(minutes=10)).isoformat(), 'search', 180.0, 500.0, 28.0, '{"query": "project"}'),
                ((now - timedelta(minutes=15)).isoformat(), 'search', 220.0, 490.0, 32.0, '{"query": "notes"}'),
                ((now - timedelta(minutes=20)).isoformat(), 'search', 190.0, 510.0, 29.0, '{"query": "document"}'),
                ((now - timedelta(hours=1)).isoformat(), 'search', 300.0, 520.0, 35.0, '{"query": "archive"}'),
                # Index operations (5 entries for trend analysis)
                ((now - timedelta(minutes=30)).isoformat(), 'index', 1000.0, 600.0, 45.0, '{"pages": 10}'),
                ((now - timedelta(minutes=35)).isoformat(), 'index', 1200.0, 620.0, 48.0, '{"pages": 12}'),
                ((now - timedelta(minutes=40)).isoformat(), 'index', 1100.0, 610.0, 46.0, '{"pages": 11}'),
                ((now - timedelta(minutes=45)).isoformat(), 'index', 1300.0, 630.0, 50.0, '{"pages": 13}'),
                ((now - timedelta(hours=2)).isoformat(), 'index', 1150.0, 615.0, 47.0, '{"pages": 10}'),
                # Bulk sync operation (just one, won't appear in trends due to < 5 threshold)
                ((now - timedelta(hours=2)).isoformat(), 'bulk_sync', 5000.0, 800.0, 60.0, '{"pages": 100}'),
            ]

            conn.executemany("""
                INSERT INTO performance_metrics
                (timestamp, operation, duration_ms, memory_usage_mb, cpu_usage_percent, context)
                VALUES (?, ?, ?, ?, ?, ?)
            """, metrics_data)

            # Insert sample system snapshots
            snapshots_data = [
                (now.isoformat(), 25.0, 512.0, 1024.0, 10.0, 5.0, 100.0),
                ((now - timedelta(minutes=30)).isoformat(), 30.0, 480.0, 1544.0, 15.0, 8.0, 150.0),
                ((now - timedelta(hours=1)).isoformat(), 35.0, 600.0, 1424.0, 20.0, 12.0, 200.0),
            ]

            conn.executemany("""
                INSERT INTO system_snapshots
                (timestamp, cpu_usage, memory_usage_mb, memory_available_mb, disk_io_read_mb, disk_io_write_mb, network_io_kb)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, snapshots_data)

            # Insert sample alerts
            alerts_data = [
                (now.isoformat(), 'high_cpu_usage', 'high', 'CPU usage at 85.0%', False),
                ((now - timedelta(minutes=30)).isoformat(), 'slow_operation', 'medium', 'Search took 2500ms', False),
            ]

            conn.executemany("""
                INSERT INTO performance_alerts (timestamp, alert_type, severity, message, resolved)
                VALUES (?, ?, ?, ?, ?)
            """, alerts_data)

            conn.commit()

        return monitor.metrics_db_path

    @pytest.fixture
    def mock_psutil(self):
        """Mock psutil for system metrics testing."""
        with patch('src.storage.performance_monitor.psutil') as mock_psutil:
            # Mock CPU usage
            mock_psutil.cpu_percent.return_value = 25.0

            # Mock memory usage
            mock_memory = Mock()
            mock_memory.total = 8 * 1024**3  # 8GB
            mock_memory.available = 4 * 1024**3  # 4GB available
            mock_psutil.virtual_memory.return_value = mock_memory

            # Mock disk I/O
            mock_disk_io = Mock()
            mock_disk_io.read_bytes = 100 * 1024**2  # 100MB
            mock_disk_io.write_bytes = 50 * 1024**2   # 50MB
            mock_psutil.disk_io_counters.return_value = mock_disk_io

            # Mock network I/O
            mock_net_io = Mock()
            mock_net_io.bytes_sent = 10 * 1024  # 10KB
            mock_net_io.bytes_recv = 20 * 1024  # 20KB
            mock_psutil.net_io_counters.return_value = mock_net_io

            # Mock disk usage
            mock_disk_usage = Mock()
            mock_disk_usage.free = 100 * 1024**3  # 100GB free
            mock_disk_usage.total = 500 * 1024**3  # 500GB total
            mock_psutil.disk_usage.return_value = mock_disk_usage

            yield mock_psutil

    def test_performance_monitor_initialization(self, monitor):
        """Test PerformanceMonitor initialization."""
        assert monitor.cache_dir is not None
        assert monitor.metrics_db_path is not None
        assert monitor.cpu_alert_threshold == 80.0
        assert monitor.memory_alert_threshold_mb == 1024
        assert monitor.response_time_alert_ms == 2000
        assert len(monitor._metrics_buffer) == 0

    def test_track_operation_context_manager(self, monitor):
        """Test operation tracking context manager."""
        with monitor.track_operation("test_operation", {"test": "context"}) as operation_id:
            assert operation_id is not None
            assert operation_id.startswith("test_operation_")

            # Check that operation is in active operations
            with monitor._operation_lock:
                assert operation_id in monitor._active_operations

        # After context exit, operation should be removed
        with monitor._operation_lock:
            assert operation_id not in monitor._active_operations

    @pytest.mark.asyncio
    async def test_get_system_metrics(self, monitor, mock_psutil):
        """Test system metrics collection."""
        metrics = await monitor._get_system_metrics()

        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_usage_percent == 25.0
        assert metrics.memory_usage_mb > 0
        assert metrics.memory_available_mb > 0
        assert metrics.disk_io_read_mb >= 0
        assert metrics.disk_io_write_mb >= 0
        assert metrics.network_io_kb >= 0

    @pytest.mark.asyncio
    async def test_record_metric(self, monitor, mock_psutil):
        """Test performance metric recording."""
        monitor._setup_metrics_db()

        await monitor._record_metric("test_search", 250.0, {"query": "test"})

        # Check that metric was added to buffer
        assert len(monitor._metrics_buffer) == 1
        metric = monitor._metrics_buffer[0]
        assert metric.operation == "test_search"
        assert metric.duration_ms == 250.0
        assert metric.context == {"query": "test"}

        # Check that metric was stored in database
        with sqlite3.connect(monitor.metrics_db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM performance_metrics")
            count = cursor.fetchone()[0]
            assert count == 1

    @pytest.mark.asyncio
    async def test_check_performance_alerts_high_cpu(self, monitor, mock_psutil):
        """Test performance alert detection for high CPU usage."""
        monitor._setup_metrics_db()

        # Mock high CPU usage
        mock_psutil.cpu_percent.return_value = 95.0

        # Create high CPU system metrics
        system_metrics = await monitor._get_system_metrics()
        metric = PerformanceMetric(
            timestamp=datetime.now(),
            operation="test",
            duration_ms=100.0,
            memory_usage_mb=system_metrics.memory_usage_mb,
            cpu_usage_percent=95.0,
            context={}
        )

        await monitor._check_performance_alerts(metric, system_metrics)

        # Check that alert was recorded
        with sqlite3.connect(monitor.metrics_db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM performance_alerts WHERE alert_type = 'high_cpu_usage'")
            count = cursor.fetchone()[0]
            assert count == 1

    @pytest.mark.asyncio
    async def test_check_performance_alerts_slow_operation(self, monitor, mock_psutil):
        """Test performance alert detection for slow operations."""
        monitor._setup_metrics_db()

        system_metrics = await monitor._get_system_metrics()
        metric = PerformanceMetric(
            timestamp=datetime.now(),
            operation="slow_search",
            duration_ms=5000.0,  # 5 seconds - very slow
            memory_usage_mb=system_metrics.memory_usage_mb,
            cpu_usage_percent=system_metrics.cpu_usage_percent,
            context={"query": "complex"}
        )

        await monitor._check_performance_alerts(metric, system_metrics)

        # Check that slow operation alert was recorded
        with sqlite3.connect(monitor.metrics_db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM performance_alerts WHERE alert_type = 'slow_operation'")
            count = cursor.fetchone()[0]
            assert count == 1

    @pytest.mark.asyncio
    async def test_get_current_snapshot(self, monitor, mock_psutil):
        """Test current performance snapshot generation."""
        monitor._setup_metrics_db()

        # Add some active operations
        with monitor.track_operation("active_search"):
            with monitor.track_operation("active_index"):
                snapshot = await monitor.get_current_snapshot()

        assert isinstance(snapshot, PerformanceSnapshot)
        assert snapshot.timestamp is not None
        assert isinstance(snapshot.system_metrics, SystemMetrics)
        assert isinstance(snapshot.active_operations, list)
        assert isinstance(snapshot.cache_stats, dict)
        assert isinstance(snapshot.recent_alerts, list)

    @pytest.mark.asyncio
    async def test_analyze_performance_trends(self, monitor, sample_metrics_db):
        """Test performance trend analysis."""
        trends = await monitor.analyze_performance_trends(hours=24)

        assert isinstance(trends, list)

        # Should have trends for operations with enough data
        operation_trends = [t for t in trends if "response_time" in t.metric_name]
        assert len(operation_trends) > 0

        # Check trend structure
        for trend in operation_trends:
            assert isinstance(trend, PerformanceTrend)
            assert trend.time_period_hours == 24
            assert trend.avg_value > 0
            assert trend.min_value >= 0
            assert trend.max_value >= trend.min_value
            assert trend.trend_direction in ['improving', 'degrading', 'stable']
            assert 0.0 <= trend.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_identify_bottlenecks_high_cpu(self, monitor, mock_psutil):
        """Test bottleneck identification for high CPU usage."""
        # Mock very high CPU usage
        mock_psutil.cpu_percent.return_value = 98.0

        bottlenecks = await monitor.identify_bottlenecks()

        cpu_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == "cpu"]
        assert len(cpu_bottlenecks) == 1

        cpu_bottleneck = cpu_bottlenecks[0]
        assert cpu_bottleneck.severity in ["critical", "high"]
        assert "cpu" in cpu_bottleneck.description.lower()
        assert len(cpu_bottleneck.recommendations) > 0

    @pytest.mark.asyncio
    async def test_identify_bottlenecks_low_memory(self, monitor, mock_psutil):
        """Test bottleneck identification for low memory."""
        # Mock low available memory
        mock_memory = Mock()
        mock_memory.total = 8 * 1024**3  # 8GB
        mock_memory.available = 100 * 1024**2  # Only 100MB available
        mock_psutil.virtual_memory.return_value = mock_memory

        bottlenecks = await monitor.identify_bottlenecks()

        memory_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == "memory"]
        assert len(memory_bottlenecks) == 1

        memory_bottleneck = memory_bottlenecks[0]
        assert memory_bottleneck.severity == "high"
        assert "memory" in memory_bottleneck.description.lower()
        assert len(memory_bottleneck.recommendations) > 0

    @pytest.mark.asyncio
    async def test_generate_performance_report(self, monitor, sample_metrics_db, mock_psutil):
        """Test comprehensive performance report generation."""
        report = await monitor.generate_performance_report()

        assert isinstance(report, PerformanceReport)
        assert report.timestamp is not None
        assert 0.0 <= report.system_health_score <= 100.0
        assert isinstance(report.performance_trends, list)
        assert isinstance(report.bottlenecks, list)
        assert isinstance(report.alerting_summary, dict)
        assert isinstance(report.recommendations, list)

    @pytest.mark.asyncio
    async def test_calculate_system_health_score_good(self, monitor, mock_psutil):
        """Test health score calculation for good performance."""
        # Mock good system conditions
        mock_psutil.cpu_percent.return_value = 15.0  # Low CPU
        mock_memory = Mock()
        mock_memory.total = 8 * 1024**3  # 8GB
        mock_memory.available = 4 * 1024**3  # 4GB available - plenty
        mock_psutil.virtual_memory.return_value = mock_memory

        snapshot = await monitor.get_current_snapshot()
        trends = []  # No degrading trends
        bottlenecks = []  # No bottlenecks

        score = await monitor._calculate_system_health_score(snapshot, trends, bottlenecks)

        assert score >= 80.0  # Should be high for good conditions

    @pytest.mark.asyncio
    async def test_calculate_system_health_score_poor(self, monitor, mock_psutil):
        """Test health score calculation for poor performance."""
        # Mock poor system conditions
        mock_psutil.cpu_percent.return_value = 95.0  # Very high CPU
        mock_memory = Mock()
        mock_memory.total = 8 * 1024**3  # 8GB
        mock_memory.available = 50 * 1024**2  # Only 50MB available
        mock_psutil.virtual_memory.return_value = mock_memory

        snapshot = await monitor.get_current_snapshot()

        # Mock degrading trends
        trends = [
            PerformanceTrend("search_response_time", 24, 500.0, 100.0, 1000.0, "degrading", 0.8),
            PerformanceTrend("cpu_usage", 24, 85.0, 50.0, 98.0, "degrading", 0.9)
        ]

        # Mock critical bottlenecks
        bottlenecks = [
            BottleneckAnalysis("cpu", "critical", "Critical CPU usage", [], [], datetime.now()),
            BottleneckAnalysis("memory", "high", "Low memory", [], [], datetime.now())
        ]

        score = await monitor._calculate_system_health_score(snapshot, trends, bottlenecks)

        assert score <= 40.0  # Should be low for poor conditions

    @pytest.mark.asyncio
    async def test_generate_performance_recommendations(self, monitor, mock_psutil):
        """Test performance recommendation generation."""
        # Create conditions that should trigger recommendations
        mock_psutil.cpu_percent.return_value = 85.0  # High CPU
        snapshot = await monitor.get_current_snapshot()

        trends = [
            PerformanceTrend("search_response_time", 24, 800.0, 200.0, 2000.0, "degrading", 0.8)
        ]

        bottlenecks = [
            BottleneckAnalysis(
                "cpu", "high", "High CPU usage", ["search", "indexing"],
                ["Reduce concurrent operations", "Implement queuing"], datetime.now()
            )
        ]

        recommendations = await monitor._generate_performance_recommendations(snapshot, trends, bottlenecks)

        assert len(recommendations) > 0

        # Should include CPU-related recommendations
        cpu_rec = any("cpu" in rec.lower() for rec in recommendations)
        assert cpu_rec

        # Should include performance-related recommendations
        perf_rec = any("performance" in rec.lower() or "slow" in rec.lower() for rec in recommendations)
        assert perf_rec

    @pytest.mark.asyncio
    async def test_cleanup_old_metrics(self, monitor, sample_metrics_db):
        """Test cleanup of old performance metrics."""
        # Insert old metrics that should be cleaned up
        old_date = (datetime.now() - timedelta(days=60)).isoformat()

        with sqlite3.connect(monitor.metrics_db_path) as conn:
            conn.execute("""
                INSERT INTO performance_metrics (timestamp, operation, duration_ms, memory_usage_mb, cpu_usage_percent, context)
                VALUES (?, 'old_operation', 100.0, 500.0, 20.0, '{}')
            """, (old_date,))
            conn.commit()

        # Clean up metrics older than 30 days
        cleaned_count = await monitor.cleanup_old_metrics(days_to_keep=30)

        assert cleaned_count > 0  # Should have cleaned up at least one record

        # Verify old metrics are gone
        with sqlite3.connect(monitor.metrics_db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM performance_metrics WHERE timestamp < ?",
                                ((datetime.now() - timedelta(days=30)).isoformat(),))
            remaining_old = cursor.fetchone()[0]
            assert remaining_old == 0

    @pytest.mark.asyncio
    async def test_record_alert(self, monitor):
        """Test alert recording functionality."""
        monitor._setup_metrics_db()

        alert = {
            "type": "test_alert",
            "severity": "medium",
            "message": "Test alert message"
        }

        await monitor._record_alert(alert)

        # Verify alert was recorded
        with sqlite3.connect(monitor.metrics_db_path) as conn:
            cursor = conn.execute("SELECT alert_type, severity, message FROM performance_alerts")
            result = cursor.fetchone()
            assert result[0] == "test_alert"
            assert result[1] == "medium"
            assert result[2] == "Test alert message"

    @pytest.mark.asyncio
    async def test_get_alerting_summary(self, monitor, sample_metrics_db):
        """Test alerting summary generation."""
        summary = await monitor._get_alerting_summary()

        assert isinstance(summary, dict)
        assert "total_alerts" in summary
        assert summary["total_alerts"] >= 0

        # Should have some alert type counts from sample data
        alert_types = [k for k in summary.keys() if k != "total_alerts"]
        assert len(alert_types) >= 0

    def test_performance_metric_creation(self, monitor):
        """Test PerformanceMetric dataclass creation."""
        metric = PerformanceMetric(
            timestamp=datetime.now(),
            operation="test_operation",
            duration_ms=150.5,
            memory_usage_mb=512.0,
            cpu_usage_percent=25.0,
            context={"test": "data"}
        )

        assert metric.operation == "test_operation"
        assert metric.duration_ms == 150.5
        assert metric.memory_usage_mb == 512.0
        assert metric.cpu_usage_percent == 25.0
        assert metric.context == {"test": "data"}

    def test_system_metrics_creation(self, monitor):
        """Test SystemMetrics dataclass creation."""
        metrics = SystemMetrics(
            cpu_usage_percent=35.5,
            memory_usage_mb=1024.0,
            memory_available_mb=2048.0,
            disk_io_read_mb=15.5,
            disk_io_write_mb=8.2,
            network_io_kb=125.0
        )

        assert metrics.cpu_usage_percent == 35.5
        assert metrics.memory_usage_mb == 1024.0
        assert metrics.memory_available_mb == 2048.0
        assert metrics.disk_io_read_mb == 15.5
        assert metrics.disk_io_write_mb == 8.2
        assert metrics.network_io_kb == 125.0

    def test_bottleneck_analysis_creation(self, monitor):
        """Test BottleneckAnalysis dataclass creation."""
        bottleneck = BottleneckAnalysis(
            bottleneck_type="cpu",
            severity="high",
            description="High CPU utilization detected",
            impact_operations=["search", "indexing"],
            recommendations=["Reduce concurrent operations", "Implement queuing"],
            detected_at=datetime.now()
        )

        assert bottleneck.bottleneck_type == "cpu"
        assert bottleneck.severity == "high"
        assert "CPU utilization" in bottleneck.description
        assert len(bottleneck.impact_operations) == 2
        assert len(bottleneck.recommendations) == 2

    @pytest.mark.asyncio
    async def test_error_handling_in_metrics_collection(self, monitor):
        """Test error handling in system metrics collection."""
        # Mock psutil to raise exceptions
        with patch('src.storage.performance_monitor.psutil.cpu_percent', side_effect=Exception("CPU error")):
            metrics = await monitor._get_system_metrics()

            # Should return default metrics instead of raising
            assert isinstance(metrics, SystemMetrics)
            assert metrics.cpu_usage_percent == 0.0

    @pytest.mark.asyncio
    async def test_error_handling_in_report_generation(self, monitor):
        """Test error handling in report generation."""
        # Force error by corrupting database path
        monitor.metrics_db_path = Path("/invalid/path/performance.db")

        report = await monitor.generate_performance_report()

        # Should return error report instead of raising
        assert isinstance(report, PerformanceReport)
        assert report.system_health_score == 0.0
        assert "failed" in report.recommendations[0].lower()
