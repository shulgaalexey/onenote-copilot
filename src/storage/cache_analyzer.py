"""
Cache Analytics System for OneNote Copilot.

This module provides comprehensive cache analysis, usage pattern detection,
and performance insights for the OneNote local cache system.
"""

import asyncio
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config.settings import get_settings


@dataclass
class CacheStats:
    """Cache statistics and metrics."""
    total_pages: int
    total_size_bytes: int
    avg_page_size_bytes: float
    notebooks_count: int
    sections_count: int
    oldest_content: Optional[datetime]
    newest_content: Optional[datetime]
    last_sync: Optional[datetime]


@dataclass
class UsagePattern:
    """User usage pattern analysis."""
    most_searched_terms: List[Tuple[str, int]]
    popular_pages: List[Tuple[str, int]]
    search_frequency_by_hour: Dict[int, int]
    notebook_access_frequency: Dict[str, int]
    avg_searches_per_day: float
    peak_usage_hours: List[int]


@dataclass
class PerformanceMetrics:
    """Performance analysis metrics."""
    avg_search_time_ms: float
    fastest_search_ms: float
    slowest_search_ms: float
    cache_hit_rate: float
    index_health_score: float
    storage_efficiency: float


@dataclass
class AnalysisReport:
    """Comprehensive cache analysis report."""
    timestamp: datetime
    cache_stats: CacheStats
    usage_patterns: UsagePattern
    performance_metrics: PerformanceMetrics
    recommendations: List[str]
    health_score: float


class CacheAnalyzer:
    """
    Comprehensive cache analysis and insights system.

    Provides detailed analytics on cache usage, performance metrics,
    user behavior patterns, and optimization recommendations.
    """

    def __init__(self):
        """Initialize the cache analyzer."""
        self.settings = get_settings()
        self.cache_dir = Path(self.settings.cache_dir)
        self.db_path = self.cache_dir / "cache.db"
        self.analytics_db_path = self.cache_dir / "analytics.db"
        self._setup_analytics_db()

    def _setup_analytics_db(self) -> None:
        """Set up analytics database for tracking metrics."""
        try:
            with sqlite3.connect(self.analytics_db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS search_analytics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        query TEXT NOT NULL,
                        results_count INTEGER,
                        search_time_ms REAL,
                        cache_hit BOOLEAN DEFAULT TRUE
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS page_access (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        page_id TEXT NOT NULL,
                        page_title TEXT,
                        access_type TEXT DEFAULT 'search'
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sync_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        pages_updated INTEGER DEFAULT 0,
                        pages_added INTEGER DEFAULT 0,
                        pages_deleted INTEGER DEFAULT 0,
                        sync_duration_ms REAL,
                        success BOOLEAN DEFAULT TRUE
                    )
                """)

                conn.commit()
        except Exception as e:
            # Analytics DB failure shouldn't break the system
            print(f"Warning: Failed to setup analytics database: {e}")

    async def analyze_cache(self) -> AnalysisReport:
        """
        Perform comprehensive cache analysis.

        Returns:
            AnalysisReport: Complete analysis results with recommendations
        """
        try:
            # Gather all analysis components
            cache_stats = await self._analyze_cache_stats()
            usage_patterns = await self._analyze_usage_patterns()
            performance_metrics = await self._analyze_performance()

            # Generate recommendations based on analysis
            recommendations = await self._generate_recommendations(
                cache_stats, usage_patterns, performance_metrics
            )

            # Calculate overall health score
            health_score = self._calculate_health_score(
                cache_stats, usage_patterns, performance_metrics
            )

            return AnalysisReport(
                timestamp=datetime.now(),
                cache_stats=cache_stats,
                usage_patterns=usage_patterns,
                performance_metrics=performance_metrics,
                recommendations=recommendations,
                health_score=health_score
            )
        except Exception as e:
            # Return basic analysis if full analysis fails
            return AnalysisReport(
                timestamp=datetime.now(),
                cache_stats=CacheStats(0, 0, 0.0, 0, 0, None, None, None),
                usage_patterns=UsagePattern([], [], {}, {}, 0.0, []),
                performance_metrics=PerformanceMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
                recommendations=[f"Analysis failed: {str(e)}"],
                health_score=0.0
            )

    async def _analyze_cache_stats(self) -> CacheStats:
        """Analyze cache statistics and content metrics."""
        if not self.db_path.exists():
            return CacheStats(0, 0, 0.0, 0, 0, None, None, None)

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total pages and basic stats
                cursor = conn.execute("SELECT COUNT(*) FROM pages")
                total_pages = cursor.fetchone()[0] or 0

                # Calculate total size (estimate based on content length)
                cursor = conn.execute("SELECT SUM(LENGTH(content)) FROM pages WHERE content IS NOT NULL")
                total_size_bytes = cursor.fetchone()[0] or 0

                avg_page_size = total_size_bytes / total_pages if total_pages > 0 else 0.0

                # Notebook and section counts
                cursor = conn.execute("SELECT COUNT(DISTINCT notebook_id) FROM pages")
                notebooks_count = cursor.fetchone()[0] or 0

                cursor = conn.execute("SELECT COUNT(DISTINCT section_id) FROM pages")
                sections_count = cursor.fetchone()[0] or 0

                # Content age analysis
                cursor = conn.execute("SELECT MIN(created_time), MAX(last_modified_time) FROM pages")
                result = cursor.fetchone()
                oldest_content = datetime.fromisoformat(result[0]) if result[0] else None
                newest_content = datetime.fromisoformat(result[1]) if result[1] else None

                # Last sync time (from metadata if available)
                cursor = conn.execute("SELECT MAX(last_modified_time) FROM pages")
                result = cursor.fetchone()
                last_sync = datetime.fromisoformat(result[0]) if result[0] else None

                return CacheStats(
                    total_pages=total_pages,
                    total_size_bytes=total_size_bytes,
                    avg_page_size_bytes=avg_page_size,
                    notebooks_count=notebooks_count,
                    sections_count=sections_count,
                    oldest_content=oldest_content,
                    newest_content=newest_content,
                    last_sync=last_sync
                )
        except Exception as e:
            return CacheStats(0, 0, 0.0, 0, 0, None, None, None)

    async def _analyze_usage_patterns(self) -> UsagePattern:
        """Analyze user behavior and usage patterns."""
        if not self.analytics_db_path.exists():
            return UsagePattern([], [], {}, {}, 0.0, [])

        try:
            with sqlite3.connect(self.analytics_db_path) as conn:
                # Most searched terms (last 30 days)
                thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
                cursor = conn.execute("""
                    SELECT query, COUNT(*) as count
                    FROM search_analytics
                    WHERE timestamp > ?
                    GROUP BY LOWER(query)
                    ORDER BY count DESC
                    LIMIT 10
                """, (thirty_days_ago,))
                most_searched_terms = cursor.fetchall()

                # Popular pages (most accessed)
                cursor = conn.execute("""
                    SELECT page_title, COUNT(*) as count
                    FROM page_access
                    WHERE timestamp > ? AND page_title IS NOT NULL
                    GROUP BY page_id
                    ORDER BY count DESC
                    LIMIT 10
                """, (thirty_days_ago,))
                popular_pages = cursor.fetchall()

                # Search frequency by hour
                cursor = conn.execute("""
                    SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
                    FROM search_analytics
                    WHERE timestamp > ?
                    GROUP BY hour
                """, (thirty_days_ago,))
                search_by_hour = dict(cursor.fetchall())
                search_frequency_by_hour = {int(h): c for h, c in search_by_hour.items()}

                # Average searches per day
                cursor = conn.execute("""
                    SELECT COUNT(*) as total_searches,
                           COUNT(DISTINCT DATE(timestamp)) as active_days
                    FROM search_analytics
                    WHERE timestamp > ?
                """, (thirty_days_ago,))
                result = cursor.fetchone()
                total_searches, active_days = result
                avg_searches_per_day = total_searches / max(active_days, 1)

                # Peak usage hours (top 3 hours by search volume)
                peak_hours = sorted(search_frequency_by_hour.items(),
                                  key=lambda x: x[1], reverse=True)[:3]
                peak_usage_hours = [hour for hour, _ in peak_hours]

                # Notebook access frequency (placeholder - would need notebook tracking)
                notebook_access_frequency = {}

                return UsagePattern(
                    most_searched_terms=most_searched_terms,
                    popular_pages=popular_pages,
                    search_frequency_by_hour=search_frequency_by_hour,
                    notebook_access_frequency=notebook_access_frequency,
                    avg_searches_per_day=avg_searches_per_day,
                    peak_usage_hours=peak_usage_hours
                )
        except Exception as e:
            return UsagePattern([], [], {}, {}, 0.0, [])

    async def _analyze_performance(self) -> PerformanceMetrics:
        """Analyze system performance metrics."""
        if not self.analytics_db_path.exists():
            return PerformanceMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        try:
            with sqlite3.connect(self.analytics_db_path) as conn:
                # Search performance metrics (last 30 days)
                thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
                cursor = conn.execute("""
                    SELECT AVG(search_time_ms), MIN(search_time_ms), MAX(search_time_ms)
                    FROM search_analytics
                    WHERE timestamp > ? AND search_time_ms IS NOT NULL
                """, (thirty_days_ago,))
                result = cursor.fetchone()
                avg_search_ms = result[0] or 0.0
                fastest_ms = result[1] or 0.0
                slowest_ms = result[2] or 0.0

                # Cache hit rate
                cursor = conn.execute("""
                    SELECT
                        SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as hit_rate
                    FROM search_analytics
                    WHERE timestamp > ?
                """, (thirty_days_ago,))
                result = cursor.fetchone()
                cache_hit_rate = result[0] or 100.0  # Assume 100% for local cache

                # Index health score (based on search performance)
                if avg_search_ms > 0:
                    # Score based on target of 500ms - lower is better
                    index_health = max(0, 100 - (avg_search_ms / 5))  # 5ms = 1 point penalty
                else:
                    index_health = 100.0

                # Storage efficiency (placeholder calculation)
                storage_efficiency = 85.0  # Would calculate based on compression ratio

                return PerformanceMetrics(
                    avg_search_time_ms=avg_search_ms,
                    fastest_search_ms=fastest_ms,
                    slowest_search_ms=slowest_ms,
                    cache_hit_rate=cache_hit_rate,
                    index_health_score=index_health,
                    storage_efficiency=storage_efficiency
                )
        except Exception as e:
            return PerformanceMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    async def _generate_recommendations(
        self,
        cache_stats: CacheStats,
        usage_patterns: UsagePattern,
        performance_metrics: PerformanceMetrics
    ) -> List[str]:
        """Generate optimization recommendations based on analysis."""
        recommendations = []

        # Cache size recommendations
        size_mb = cache_stats.total_size_bytes / (1024 * 1024)
        if size_mb > 1000:  # > 1GB
            recommendations.append(
                f"Cache size is large ({size_mb:.1f}MB). Consider cleanup of old content."
            )
        elif size_mb < 10:  # < 10MB
            recommendations.append(
                "Cache appears small. Consider syncing more content for better search coverage."
            )

        # Performance recommendations
        if performance_metrics.avg_search_time_ms > 500:
            recommendations.append(
                f"Average search time ({performance_metrics.avg_search_time_ms:.1f}ms) exceeds target. "
                "Consider rebuilding search index."
            )

        if performance_metrics.index_health_score < 70:
            recommendations.append(
                "Search index health is poor. Recommend index optimization or rebuild."
            )

        # Usage pattern recommendations
        if usage_patterns.avg_searches_per_day > 50:
            recommendations.append(
                "High search usage detected. Consider enabling search result caching for better performance."
            )

        # Content freshness recommendations
        if cache_stats.last_sync:
            days_since_sync = (datetime.now() - cache_stats.last_sync).days
            if days_since_sync > 7:
                recommendations.append(
                    f"Content hasn't been synced in {days_since_sync} days. "
                    "Consider running a sync to get latest changes."
                )

        # Default recommendations if no specific issues
        if not recommendations:
            recommendations.extend([
                "Cache is performing well! No immediate optimizations needed.",
                "Consider regular sync operations to keep content fresh.",
                "Monitor search performance for any degradation over time."
            ])

        return recommendations

    def _calculate_health_score(
        self,
        cache_stats: CacheStats,
        usage_patterns: UsagePattern,
        performance_metrics: PerformanceMetrics
    ) -> float:
        """Calculate overall cache health score (0-100)."""
        score = 0.0

        # Performance component (40% weight)
        perf_score = min(100, performance_metrics.index_health_score)
        if performance_metrics.avg_search_time_ms < 500:
            perf_score = min(100, perf_score + 20)  # Bonus for fast searches

        score += perf_score * 0.4

        # Content freshness (30% weight)
        freshness_score = 50.0  # Base score
        if cache_stats.last_sync:
            days_since_sync = (datetime.now() - cache_stats.last_sync).days
            if days_since_sync < 1:
                freshness_score = 100.0
            elif days_since_sync < 7:
                freshness_score = 80.0
            elif days_since_sync < 30:
                freshness_score = 60.0
            else:
                freshness_score = 30.0

        score += freshness_score * 0.3

        # Content coverage (20% weight)
        coverage_score = 70.0  # Base score
        if cache_stats.total_pages > 100:
            coverage_score = 90.0
        elif cache_stats.total_pages > 50:
            coverage_score = 80.0
        elif cache_stats.total_pages < 10:
            coverage_score = 40.0

        score += coverage_score * 0.2

        # Usage activity (10% weight)
        activity_score = min(100, usage_patterns.avg_searches_per_day * 10)
        score += activity_score * 0.1

        return min(100.0, max(0.0, score))

    async def track_search(
        self,
        query: str,
        results_count: int,
        search_time_ms: float,
        cache_hit: bool = True
    ) -> None:
        """Track search analytics for pattern analysis."""
        try:
            with sqlite3.connect(self.analytics_db_path) as conn:
                conn.execute("""
                    INSERT INTO search_analytics
                    (timestamp, query, results_count, search_time_ms, cache_hit)
                    VALUES (?, ?, ?, ?, ?)
                """, (datetime.now().isoformat(), query, results_count, search_time_ms, cache_hit))
                conn.commit()
        except Exception:
            # Analytics failures shouldn't break search
            pass

    async def track_page_access(
        self,
        page_id: str,
        page_title: Optional[str] = None,
        access_type: str = "search"
    ) -> None:
        """Track page access for usage pattern analysis."""
        try:
            with sqlite3.connect(self.analytics_db_path) as conn:
                conn.execute("""
                    INSERT INTO page_access
                    (timestamp, page_id, page_title, access_type)
                    VALUES (?, ?, ?, ?)
                """, (datetime.now().isoformat(), page_id, page_title, access_type))
                conn.commit()
        except Exception:
            # Analytics failures shouldn't break functionality
            pass

    async def export_report(self, report: AnalysisReport, output_path: Path) -> None:
        """Export analysis report to JSON file."""
        try:
            # Convert dataclasses to dict for JSON serialization
            report_dict = {
                "timestamp": report.timestamp.isoformat(),
                "cache_stats": asdict(report.cache_stats),
                "usage_patterns": asdict(report.usage_patterns),
                "performance_metrics": asdict(report.performance_metrics),
                "recommendations": report.recommendations,
                "health_score": report.health_score
            }

            # Convert datetime objects in nested structures
            def convert_datetimes(obj):
                if isinstance(obj, dict):
                    return {k: convert_datetimes(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_datetimes(item) for item in obj]
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                else:
                    return obj

            report_dict = convert_datetimes(report_dict)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report_dict, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise RuntimeError(f"Failed to export report: {e}")
