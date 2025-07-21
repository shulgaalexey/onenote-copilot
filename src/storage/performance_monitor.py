"""
Performance Monitoring System for OneNote Copilot.

This module provides comprehensive performance tracking, bottleneck identification,
and system health monitoring for the OneNote local cache system.
"""

import asyncio
import sqlite3
import statistics
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

from ..config.settings import get_settings


@dataclass
class PerformanceMetric:
    """Individual performance metric data point."""
    timestamp: datetime
    operation: str
    duration_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    context: Dict[str, Any]


@dataclass
class SystemMetrics:
    """Current system resource metrics."""
    cpu_usage_percent: float
    memory_usage_mb: float
    memory_available_mb: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_io_kb: float


@dataclass
class PerformanceSnapshot:
    """Performance snapshot at a point in time."""
    timestamp: datetime
    system_metrics: SystemMetrics
    active_operations: List[str]
    cache_stats: Dict[str, Any]
    recent_alerts: List[str]


@dataclass
class PerformanceTrend:
    """Performance trend analysis."""
    metric_name: str
    time_period_hours: int
    avg_value: float
    min_value: float
    max_value: float
    trend_direction: str  # 'improving', 'degrading', 'stable'
    confidence: float


@dataclass
class BottleneckAnalysis:
    """Analysis of system bottlenecks."""
    bottleneck_type: str  # 'cpu', 'memory', 'disk', 'network', 'database'
    severity: str         # 'low', 'medium', 'high', 'critical'
    description: str
    impact_operations: List[str]
    recommendations: List[str]
    detected_at: datetime


@dataclass
class PerformanceReport:
    """Comprehensive performance monitoring report."""
    timestamp: datetime
    system_health_score: float
    performance_trends: List[PerformanceTrend]
    bottlenecks: List[BottleneckAnalysis]
    alerting_summary: Dict[str, int]
    recommendations: List[str]


class PerformanceMonitor:
    """
    Real-time performance monitoring and analysis system.

    Tracks system resources, operation performance, identifies bottlenecks,
    and provides intelligent alerting and optimization recommendations.
    """

    def __init__(self):
        """Initialize the performance monitor."""
        self.settings = get_settings()
        self.cache_dir = Path(self.settings.cache_dir)
        self.metrics_db_path = self.cache_dir / "performance.db"

        # Performance tracking
        self._metrics_buffer = deque(maxlen=1000)  # Recent metrics in memory
        self._active_operations: Dict[str, float] = {}  # operation_id -> start_time
        self._operation_lock = threading.Lock()

        # Alert thresholds
        self.cpu_alert_threshold = 80.0        # CPU usage %
        self.memory_alert_threshold_mb = 1024  # Memory usage MB
        self.response_time_alert_ms = 2000     # Response time milliseconds
        self.disk_space_alert_gb = 1.0         # Available disk space GB

        # Trend analysis windows
        self.short_term_hours = 1
        self.medium_term_hours = 24
        self.long_term_hours = 168  # 1 week

        self._setup_metrics_db()
        self._last_system_metrics = None
        self._alerts_buffer = deque(maxlen=100)

    def _setup_metrics_db(self) -> None:
        """Set up performance metrics database."""
        try:
            with sqlite3.connect(self.metrics_db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        duration_ms REAL NOT NULL,
                        memory_usage_mb REAL,
                        cpu_usage_percent REAL,
                        context TEXT
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        cpu_usage REAL,
                        memory_usage_mb REAL,
                        memory_available_mb REAL,
                        disk_io_read_mb REAL,
                        disk_io_write_mb REAL,
                        network_io_kb REAL
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS performance_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        message TEXT NOT NULL,
                        resolved BOOLEAN DEFAULT FALSE
                    )
                """)

                # Create indexes for efficient querying
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON performance_metrics(timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_operation ON performance_metrics(operation)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON system_snapshots(timestamp)")

                conn.commit()
        except Exception as e:
            print(f"Warning: Failed to setup performance metrics database: {e}")

    @contextmanager
    def track_operation(self, operation: str, context: Optional[Dict[str, Any]] = None):
        """
        Context manager for tracking operation performance.

        Args:
            operation: Name of the operation being tracked
            context: Additional context information

        Usage:
            with monitor.track_operation("search_query", {"query": "test"}):
                # perform operation
                pass
        """
        operation_id = f"{operation}_{int(time.time() * 1000)}"
        start_time = time.time()

        # Record operation start
        with self._operation_lock:
            self._active_operations[operation_id] = start_time

        try:
            yield operation_id
        finally:
            # Record operation completion
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            with self._operation_lock:
                self._active_operations.pop(operation_id, None)

            # Record performance metric
            asyncio.create_task(self._record_metric(operation, duration_ms, context or {}))

    async def _record_metric(
        self,
        operation: str,
        duration_ms: float,
        context: Dict[str, Any]
    ) -> None:
        """Record a performance metric."""
        try:
            # Get current system metrics
            system_metrics = await self._get_system_metrics()

            metric = PerformanceMetric(
                timestamp=datetime.now(),
                operation=operation,
                duration_ms=duration_ms,
                memory_usage_mb=system_metrics.memory_usage_mb,
                cpu_usage_percent=system_metrics.cpu_usage_percent,
                context=context
            )

            # Add to memory buffer
            self._metrics_buffer.append(metric)

            # Store in database
            await self._store_metric_to_db(metric)

            # Check for performance alerts
            await self._check_performance_alerts(metric, system_metrics)

        except Exception as e:
            # Don't let performance tracking break the main operation
            pass

    async def _store_metric_to_db(self, metric: PerformanceMetric) -> None:
        """Store performance metric to database."""
        try:
            with sqlite3.connect(self.metrics_db_path) as conn:
                conn.execute("""
                    INSERT INTO performance_metrics
                    (timestamp, operation, duration_ms, memory_usage_mb, cpu_usage_percent, context)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    metric.timestamp.isoformat(),
                    metric.operation,
                    metric.duration_ms,
                    metric.memory_usage_mb,
                    metric.cpu_usage_percent,
                    str(metric.context)
                ))
                conn.commit()
        except Exception:
            pass

    async def _get_system_metrics(self) -> SystemMetrics:
        """Get current system resource metrics."""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=0.1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_mb = (memory.total - memory.available) / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)

            # Disk I/O (delta from last measurement)
            disk_io = psutil.disk_io_counters()
            disk_read_mb = 0.0
            disk_write_mb = 0.0

            if self._last_system_metrics:
                last_disk = self._last_system_metrics.disk_io_read_mb
                if hasattr(disk_io, 'read_bytes'):
                    disk_read_mb = max(0, (disk_io.read_bytes / (1024 * 1024)) - last_disk)
                    disk_write_mb = max(0, (disk_io.write_bytes / (1024 * 1024)) -
                                      self._last_system_metrics.disk_io_write_mb)

            # Network I/O
            network_io = psutil.net_io_counters()
            network_io_kb = 0.0
            if hasattr(network_io, 'bytes_sent'):
                network_io_kb = (network_io.bytes_sent + network_io.bytes_recv) / 1024

            metrics = SystemMetrics(
                cpu_usage_percent=cpu_usage,
                memory_usage_mb=memory_usage_mb,
                memory_available_mb=memory_available_mb,
                disk_io_read_mb=disk_read_mb,
                disk_io_write_mb=disk_write_mb,
                network_io_kb=network_io_kb
            )

            self._last_system_metrics = metrics
            return metrics

        except Exception as e:
            # Return default metrics if collection fails
            return SystemMetrics(0.0, 0.0, 1024.0, 0.0, 0.0, 0.0)

    async def _check_performance_alerts(
        self,
        metric: PerformanceMetric,
        system_metrics: SystemMetrics
    ) -> None:
        """Check for performance alerts and record them."""
        alerts = []

        # CPU usage alerts
        if system_metrics.cpu_usage_percent > self.cpu_alert_threshold:
            severity = "critical" if system_metrics.cpu_usage_percent > 95 else "high"
            alerts.append({
                "type": "high_cpu_usage",
                "severity": severity,
                "message": f"CPU usage at {system_metrics.cpu_usage_percent:.1f}%"
            })

        # Memory usage alerts
        if system_metrics.memory_usage_mb > self.memory_alert_threshold_mb:
            severity = "critical" if system_metrics.memory_available_mb < 128 else "high"
            alerts.append({
                "type": "high_memory_usage",
                "severity": severity,
                "message": f"Memory usage at {system_metrics.memory_usage_mb:.0f}MB"
            })

        # Response time alerts
        if metric.duration_ms > self.response_time_alert_ms:
            severity = "critical" if metric.duration_ms > 10000 else "medium"
            alerts.append({
                "type": "slow_operation",
                "severity": severity,
                "message": f"Operation '{metric.operation}' took {metric.duration_ms:.0f}ms"
            })

        # Disk space alerts
        try:
            available_gb = psutil.disk_usage(self.cache_dir).free / (1024**3)
            if available_gb < self.disk_space_alert_gb:
                severity = "critical" if available_gb < 0.1 else "high"
                alerts.append({
                    "type": "low_disk_space",
                    "severity": severity,
                    "message": f"Available disk space: {available_gb:.1f}GB"
                })
        except Exception:
            pass

        # Record alerts in database
        for alert in alerts:
            await self._record_alert(alert)
            self._alerts_buffer.append(f"{alert['severity'].upper()}: {alert['message']}")

    async def _record_alert(self, alert: Dict[str, str]) -> None:
        """Record a performance alert."""
        try:
            with sqlite3.connect(self.metrics_db_path) as conn:
                conn.execute("""
                    INSERT INTO performance_alerts (timestamp, alert_type, severity, message)
                    VALUES (?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    alert["type"],
                    alert["severity"],
                    alert["message"]
                ))
                conn.commit()
        except Exception:
            pass

    async def get_current_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot."""
        try:
            system_metrics = await self._get_system_metrics()

            # Get active operations
            with self._operation_lock:
                active_ops = list(self._active_operations.keys())

            # Get cache stats (basic)
            cache_stats = await self._get_cache_stats()

            # Get recent alerts
            recent_alerts = list(self._alerts_buffer)[-10:]  # Last 10 alerts

            return PerformanceSnapshot(
                timestamp=datetime.now(),
                system_metrics=system_metrics,
                active_operations=active_ops,
                cache_stats=cache_stats,
                recent_alerts=recent_alerts
            )
        except Exception as e:
            return PerformanceSnapshot(
                datetime.now(),
                SystemMetrics(0.0, 0.0, 1024.0, 0.0, 0.0, 0.0),
                [],
                {},
                [f"Snapshot error: {str(e)}"]
            )

    async def _get_cache_stats(self) -> Dict[str, Any]:
        """Get basic cache statistics."""
        stats = {}
        try:
            cache_db_path = self.cache_dir / "cache.db"
            if cache_db_path.exists():
                with sqlite3.connect(cache_db_path) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM pages")
                    stats["total_pages"] = cursor.fetchone()[0]

                    cursor = conn.execute("SELECT COUNT(DISTINCT notebook_id) FROM pages")
                    stats["total_notebooks"] = cursor.fetchone()[0]

                    stats["db_size_mb"] = cache_db_path.stat().st_size / (1024 * 1024)
        except Exception:
            pass

        return stats

    async def analyze_performance_trends(self, hours: int = 24) -> List[PerformanceTrend]:
        """Analyze performance trends over specified time period."""
        if not self.metrics_db_path.exists():
            return []

        trends = []
        start_time = (datetime.now() - timedelta(hours=hours)).isoformat()

        try:
            with sqlite3.connect(self.metrics_db_path) as conn:
                # Analyze response time trends by operation
                cursor = conn.execute("""
                    SELECT operation, AVG(duration_ms), MIN(duration_ms), MAX(duration_ms)
                    FROM performance_metrics
                    WHERE timestamp > ?
                    GROUP BY operation
                    HAVING COUNT(*) >= 5
                """, (start_time,))

                for operation, avg_duration, min_duration, max_duration in cursor.fetchall():
                    # Determine trend direction (simplified)
                    trend_direction = "stable"
                    if max_duration > avg_duration * 2:
                        trend_direction = "degrading"
                    elif min_duration < avg_duration * 0.5:
                        trend_direction = "improving"

                    trends.append(PerformanceTrend(
                        metric_name=f"{operation}_response_time",
                        time_period_hours=hours,
                        avg_value=avg_duration,
                        min_value=min_duration,
                        max_value=max_duration,
                        trend_direction=trend_direction,
                        confidence=0.8  # Simplified confidence
                    ))

                # Analyze system resource trends
                cursor = conn.execute("""
                    SELECT AVG(cpu_usage), MIN(cpu_usage), MAX(cpu_usage),
                           AVG(memory_usage_mb), MIN(memory_usage_mb), MAX(memory_usage_mb)
                    FROM system_snapshots
                    WHERE timestamp > ?
                """, (start_time,))

                result = cursor.fetchone()
                if result and result[0] is not None:
                    avg_cpu, min_cpu, max_cpu, avg_mem, min_mem, max_mem = result

                    trends.extend([
                        PerformanceTrend(
                            metric_name="cpu_usage",
                            time_period_hours=hours,
                            avg_value=avg_cpu,
                            min_value=min_cpu,
                            max_value=max_cpu,
                            trend_direction="stable",
                            confidence=0.9
                        ),
                        PerformanceTrend(
                            metric_name="memory_usage",
                            time_period_hours=hours,
                            avg_value=avg_mem,
                            min_value=min_mem,
                            max_value=max_mem,
                            trend_direction="stable",
                            confidence=0.9
                        )
                    ])

        except Exception as e:
            pass

        return trends

    async def identify_bottlenecks(self) -> List[BottleneckAnalysis]:
        """Identify system bottlenecks based on performance data."""
        bottlenecks = []

        try:
            # Analyze recent performance data
            recent_snapshot = await self.get_current_snapshot()
            trends = await self.analyze_performance_trends(hours=1)

            # CPU bottleneck detection
            if recent_snapshot.system_metrics.cpu_usage_percent > 85:
                cpu_trend = next((t for t in trends if t.metric_name == "cpu_usage"), None)
                severity = "critical" if recent_snapshot.system_metrics.cpu_usage_percent > 95 else "high"

                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_type="cpu",
                    severity=severity,
                    description=f"High CPU usage: {recent_snapshot.system_metrics.cpu_usage_percent:.1f}%",
                    impact_operations=["search", "indexing", "content_processing"],
                    recommendations=[
                        "Reduce concurrent operations",
                        "Implement operation queuing",
                        "Consider background processing for heavy tasks"
                    ],
                    detected_at=datetime.now()
                ))

            # Memory bottleneck detection
            if recent_snapshot.system_metrics.memory_available_mb < 256:  # Less than 256MB available
                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_type="memory",
                    severity="high",
                    description=f"Low available memory: {recent_snapshot.system_metrics.memory_available_mb:.0f}MB",
                    impact_operations=["large_file_processing", "bulk_operations"],
                    recommendations=[
                        "Implement memory cleanup procedures",
                        "Process content in smaller batches",
                        "Add memory usage monitoring to operations"
                    ],
                    detected_at=datetime.now()
                ))

            # Disk I/O bottleneck detection
            if recent_snapshot.system_metrics.disk_io_read_mb > 50:  # High disk activity
                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_type="disk",
                    severity="medium",
                    description=f"High disk I/O: {recent_snapshot.system_metrics.disk_io_read_mb:.1f}MB/s read",
                    impact_operations=["database_operations", "asset_loading"],
                    recommendations=[
                        "Optimize database queries",
                        "Implement better caching strategies",
                        "Consider SSD storage for cache directory"
                    ],
                    detected_at=datetime.now()
                ))

            # Database performance bottleneck
            slow_operations = [t for t in trends if "response_time" in t.metric_name and t.avg_value > 1000]
            if slow_operations:
                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_type="database",
                    severity="medium",
                    description=f"Slow database operations detected: {len(slow_operations)} operations averaging >1s",
                    impact_operations=[t.metric_name.replace("_response_time", "") for t in slow_operations],
                    recommendations=[
                        "Rebuild database indexes",
                        "Analyze and optimize slow queries",
                        "Consider database maintenance operations"
                    ],
                    detected_at=datetime.now()
                ))

        except Exception as e:
            bottlenecks.append(BottleneckAnalysis(
                bottleneck_type="monitoring",
                severity="low",
                description=f"Performance monitoring error: {str(e)}",
                impact_operations=["monitoring"],
                recommendations=["Check performance monitoring configuration"],
                detected_at=datetime.now()
            ))

        return bottlenecks

    async def generate_performance_report(self) -> PerformanceReport:
        """Generate comprehensive performance report."""
        try:
            # Get current snapshot for health assessment
            snapshot = await self.get_current_snapshot()

            # Analyze trends
            trends = await self.analyze_performance_trends(hours=24)

            # Identify bottlenecks
            bottlenecks = await self.identify_bottlenecks()

            # Get alerting summary
            alerting_summary = await self._get_alerting_summary()

            # Calculate health score
            health_score = await self._calculate_system_health_score(snapshot, trends, bottlenecks)

            # Generate recommendations
            recommendations = await self._generate_performance_recommendations(
                snapshot, trends, bottlenecks
            )

            return PerformanceReport(
                timestamp=datetime.now(),
                system_health_score=health_score,
                performance_trends=trends,
                bottlenecks=bottlenecks,
                alerting_summary=alerting_summary,
                recommendations=recommendations
            )
        except Exception as e:
            return PerformanceReport(
                datetime.now(), 0.0, [], [],
                {"errors": 1}, [f"Performance report generation failed: {str(e)}"]
            )

    async def _get_alerting_summary(self) -> Dict[str, int]:
        """Get summary of recent alerts."""
        summary = defaultdict(int)

        try:
            with sqlite3.connect(self.metrics_db_path) as conn:
                last_24h = (datetime.now() - timedelta(hours=24)).isoformat()
                cursor = conn.execute("""
                    SELECT alert_type, severity, COUNT(*)
                    FROM performance_alerts
                    WHERE timestamp > ?
                    GROUP BY alert_type, severity
                """, (last_24h,))

                for alert_type, severity, count in cursor.fetchall():
                    summary[f"{severity}_{alert_type}"] = count
                    summary["total_alerts"] += count
        except Exception:
            pass

        return dict(summary)

    async def _calculate_system_health_score(
        self,
        snapshot: PerformanceSnapshot,
        trends: List[PerformanceTrend],
        bottlenecks: List[BottleneckAnalysis]
    ) -> float:
        """Calculate overall system health score (0-100)."""
        score = 100.0

        # Resource utilization penalties
        if snapshot.system_metrics.cpu_usage_percent > 80:
            score -= min(30, (snapshot.system_metrics.cpu_usage_percent - 80) * 2)

        if snapshot.system_metrics.memory_available_mb < 512:
            score -= min(25, (512 - snapshot.system_metrics.memory_available_mb) / 20)

        # Bottleneck penalties
        for bottleneck in bottlenecks:
            if bottleneck.severity == "critical":
                score -= 20
            elif bottleneck.severity == "high":
                score -= 10
            elif bottleneck.severity == "medium":
                score -= 5

        # Performance trend penalties
        degrading_trends = [t for t in trends if t.trend_direction == "degrading"]
        score -= len(degrading_trends) * 5

        # Alert frequency penalty
        if len(snapshot.recent_alerts) > 5:
            score -= (len(snapshot.recent_alerts) - 5) * 2

        return max(0.0, min(100.0, score))

    async def _generate_performance_recommendations(
        self,
        snapshot: PerformanceSnapshot,
        trends: List[PerformanceTrend],
        bottlenecks: List[BottleneckAnalysis]
    ) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []

        # Resource-based recommendations
        if snapshot.system_metrics.cpu_usage_percent > 70:
            recommendations.append(
                f"CPU usage is high ({snapshot.system_metrics.cpu_usage_percent:.1f}%). "
                "Consider reducing concurrent operations or implementing queuing."
            )

        if snapshot.system_metrics.memory_available_mb < 512:
            recommendations.append(
                f"Available memory is low ({snapshot.system_metrics.memory_available_mb:.0f}MB). "
                "Implement memory cleanup procedures."
            )

        # Bottleneck-based recommendations
        for bottleneck in bottlenecks:
            if bottleneck.severity in ["critical", "high"]:
                recommendations.extend(bottleneck.recommendations)

        # Trend-based recommendations
        slow_trends = [t for t in trends if "response_time" in t.metric_name and t.avg_value > 500]
        if slow_trends:
            recommendations.append(
                f"Several operations are running slowly (>500ms average). "
                "Consider database optimization and index rebuilding."
            )

        # General maintenance recommendations
        recommendations.extend([
            "Monitor system resources regularly for capacity planning",
            "Implement automated performance alerting",
            "Schedule regular database maintenance operations"
        ])

        return recommendations

    async def cleanup_old_metrics(self, days_to_keep: int = 30) -> int:
        """Clean up old performance metrics to manage database size."""
        if not self.metrics_db_path.exists():
            return 0

        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()

            with sqlite3.connect(self.metrics_db_path) as conn:
                # Count records to be deleted
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM performance_metrics WHERE timestamp < ?
                """, (cutoff_date,))
                count = cursor.fetchone()[0]

                # Delete old metrics
                conn.execute("DELETE FROM performance_metrics WHERE timestamp < ?", (cutoff_date,))
                conn.execute("DELETE FROM system_snapshots WHERE timestamp < ?", (cutoff_date,))
                conn.execute("DELETE FROM performance_alerts WHERE timestamp < ? AND resolved = 1", (cutoff_date,))

                conn.commit()

                # Optimize database
                conn.execute("VACUUM")

                return count
        except Exception as e:
            return 0
