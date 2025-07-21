"""
Search analytics system for OneNote cache.

Provides comprehensive usage tracking, performance metrics, user behavior analysis,
and search optimization insights for the OneNote local cache search system.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union, NamedTuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, Counter
import statistics
import uuid

from ..models.cache import CachedPage
from ..config.settings import Settings

logger = logging.getLogger(__name__)


class SearchEventType(str, Enum):
    """Types of search events to track."""
    QUERY_EXECUTED = "query_executed"
    RESULT_CLICKED = "result_clicked"
    FILTER_APPLIED = "filter_applied"
    SUGGESTION_SELECTED = "suggestion_selected"
    SUGGESTION_GENERATED = "suggestion_generated"
    RANKING_APPLIED = "ranking_applied"
    SEARCH_COMPLETED = "search_completed"
    SEARCH_FAILED = "search_failed"


class PerformanceMetric(str, Enum):
    """Performance metrics to track."""
    QUERY_EXECUTION_TIME = "query_execution_time"
    RESULT_RANKING_TIME = "result_ranking_time"
    FILTER_APPLICATION_TIME = "filter_application_time"
    SUGGESTION_GENERATION_TIME = "suggestion_generation_time"
    TOTAL_SEARCH_TIME = "total_search_time"
    CACHE_HIT_RATE = "cache_hit_rate"
    RESULT_ACCURACY = "result_accuracy"


@dataclass
class SearchEvent:
    """A search-related event with metadata."""
    
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: SearchEventType = SearchEventType.QUERY_EXECUTED
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = ""
    user_id: Optional[str] = None
    
    # Search context
    query: Optional[str] = None
    result_count: int = 0
    filters_applied: List[str] = field(default_factory=list)
    ranking_method: Optional[str] = None
    
    # Performance data
    execution_time: float = 0.0
    cache_hit: bool = False
    success: bool = True
    
    # User interaction
    clicked_result_position: Optional[int] = None
    clicked_result_id: Optional[str] = None
    interaction_type: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceSnapshot:
    """Performance metrics snapshot."""
    
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Query performance
    avg_query_time: float = 0.0
    avg_ranking_time: float = 0.0
    avg_total_time: float = 0.0
    
    # Hit rates
    cache_hit_rate: float = 0.0
    suggestion_usage_rate: float = 0.0
    
    # Quality metrics
    avg_results_per_query: float = 0.0
    successful_query_rate: float = 0.0
    user_satisfaction_score: float = 0.0
    
    # Volume metrics
    queries_per_hour: float = 0.0
    unique_users: int = 0
    total_events: int = 0


@dataclass
class SearchPattern:
    """Identified search pattern."""
    
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_type: str = ""  # "common_query", "user_journey", "temporal"
    
    # Pattern data
    queries: List[str] = field(default_factory=list)
    frequency: int = 0
    success_rate: float = 0.0
    
    # Temporal data
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    peak_hours: List[int] = field(default_factory=list)
    
    # User data
    unique_users: Set[str] = field(default_factory=set)
    common_filters: List[str] = field(default_factory=list)
    
    # Performance
    avg_execution_time: float = 0.0
    typical_result_count: float = 0.0


class SearchAnalytics:
    """
    Comprehensive search analytics and performance monitoring system.
    
    Tracks user behavior, search performance, and system optimization metrics
    to provide insights for improving the search experience.
    """

    def __init__(self, 
                 settings: Optional[Settings] = None,
                 max_events: int = 50000,
                 retention_days: int = 90):
        """
        Initialize search analytics system.

        Args:
            settings: Configuration settings
            max_events: Maximum number of events to keep in memory
            retention_days: Days to retain analytics data
        """
        self.settings = settings or Settings()
        self.max_events = max_events
        self.retention_days = retention_days
        
        # Storage
        self.analytics_dir = Path(self.settings.cache_path) / "analytics"
        self.analytics_dir.mkdir(parents=True, exist_ok=True)
        
        self.events_file = self.analytics_dir / "search_events.json"
        self.patterns_file = self.analytics_dir / "search_patterns.json"
        self.performance_file = self.analytics_dir / "performance_snapshots.json"
        
        # In-memory data
        self.events: List[SearchEvent] = []
        self.patterns: Dict[str, SearchPattern] = {}
        self.performance_snapshots: List[PerformanceSnapshot] = []
        
        # Analytics state
        self.current_session_id = str(uuid.uuid4())
        self.analytics_enabled = True
        
        # Performance tracking
        self.performance_buffer: Dict[str, List[float]] = defaultdict(list)
        self.query_cache: Dict[str, Any] = {}
        
        # User behavior tracking
        self.user_sessions: Dict[str, List[SearchEvent]] = defaultdict(list)
        self.query_sequences: Dict[str, List[str]] = defaultdict(list)
        
        # Load existing data
        self._load_analytics_data()
        
        logger.info("Initialized search analytics system")

    async def track_event(self, 
                         event_type: SearchEventType,
                         session_id: Optional[str] = None,
                         user_id: Optional[str] = None,
                         **kwargs) -> str:
        """
        Track a search-related event.

        Args:
            event_type: Type of event to track
            session_id: Session identifier
            user_id: User identifier
            **kwargs: Additional event data

        Returns:
            Event ID for correlation
        """
        if not self.analytics_enabled:
            return ""
        
        try:
            # Create event
            event = SearchEvent(
                event_type=event_type,
                session_id=session_id or self.current_session_id,
                user_id=user_id,
                **kwargs
            )
            
            # Add to events
            self.events.append(event)
            
            # Add to user session
            if event.session_id:
                self.user_sessions[event.session_id].append(event)
            
            # Track query sequences for pattern analysis
            if event.query and event.session_id:
                self.query_sequences[event.session_id].append(event.query)
            
            # Maintain event count limit
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events:]
            
            # Update patterns asynchronously
            asyncio.create_task(self._update_patterns(event))
            
            logger.debug(f"Tracked event: {event_type} - {event.event_id}")
            return event.event_id
            
        except Exception as e:
            logger.error(f"Failed to track event: {e}")
            return ""

    async def record_performance(self, 
                               metric: PerformanceMetric,
                               value: float,
                               context: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a performance metric.

        Args:
            metric: Performance metric type
            value: Metric value
            context: Additional context data
        """
        if not self.analytics_enabled:
            return
        
        try:
            # Add to performance buffer
            self.performance_buffer[metric.value].append(value)
            
            # Keep buffer size reasonable
            if len(self.performance_buffer[metric.value]) > 1000:
                self.performance_buffer[metric.value] = self.performance_buffer[metric.value][-1000:]
            
            logger.debug(f"Recorded performance metric: {metric} = {value}")
            
        except Exception as e:
            logger.error(f"Failed to record performance: {e}")

    async def get_analytics_report(self, 
                                 time_range: Optional[Tuple[datetime, datetime]] = None,
                                 include_patterns: bool = True,
                                 include_performance: bool = True) -> Dict[str, Any]:
        """
        Generate comprehensive analytics report.

        Args:
            time_range: Optional time range filter
            include_patterns: Include pattern analysis
            include_performance: Include performance metrics

        Returns:
            Analytics report
        """
        try:
            # Filter events by time range
            filtered_events = self.events
            if time_range:
                start_time, end_time = time_range
                filtered_events = [
                    e for e in self.events 
                    if start_time <= e.timestamp <= end_time
                ]
            
            report = {
                "report_generated": datetime.now(timezone.utc).isoformat(),
                "time_range": {
                    "start": time_range[0].isoformat() if time_range else None,
                    "end": time_range[1].isoformat() if time_range else None
                },
                "summary": await self._generate_summary_stats(filtered_events)
            }
            
            # Query analytics
            report["query_analytics"] = await self._analyze_queries(filtered_events)
            
            # User behavior
            report["user_behavior"] = await self._analyze_user_behavior(filtered_events)
            
            # Performance metrics
            if include_performance:
                report["performance"] = await self._analyze_performance()
            
            # Pattern analysis
            if include_patterns:
                report["patterns"] = await self._analyze_patterns()
            
            # Recommendations
            report["recommendations"] = await self._generate_recommendations(filtered_events)
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate analytics report: {e}")
            return {"error": str(e)}

    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time performance and usage metrics."""
        try:
            now = datetime.now(timezone.utc)
            last_hour = now - timedelta(hours=1)
            
            # Recent events
            recent_events = [e for e in self.events if e.timestamp >= last_hour]
            
            # Current performance
            current_perf = {}
            for metric, values in self.performance_buffer.items():
                if values:
                    recent_values = values[-100:]  # Last 100 measurements
                    current_perf[metric] = {
                        "current": values[-1] if values else 0,
                        "average": sum(recent_values) / len(recent_values),
                        "min": min(recent_values),
                        "max": max(recent_values)
                    }
            
            return {
                "timestamp": now.isoformat(),
                "events_last_hour": len(recent_events),
                "active_sessions": len(set(e.session_id for e in recent_events if e.session_id)),
                "query_rate": len([e for e in recent_events if e.event_type == SearchEventType.QUERY_EXECUTED]),
                "success_rate": sum(1 for e in recent_events if e.success) / len(recent_events) if recent_events else 0,
                "performance": current_perf,
                "cache_utilization": len(self.query_cache),
                "patterns_identified": len(self.patterns)
            }
            
        except Exception as e:
            logger.error(f"Failed to get real-time metrics: {e}")
            return {}

    async def get_search_optimization_insights(self) -> Dict[str, Any]:
        """Generate insights for search optimization."""
        try:
            insights = {
                "generated": datetime.now(timezone.utc).isoformat(),
                "optimization_opportunities": [],
                "performance_bottlenecks": [],
                "user_experience_issues": [],
                "recommendations": []
            }
            
            # Analyze query performance
            query_times = self.performance_buffer.get(PerformanceMetric.TOTAL_SEARCH_TIME.value, [])
            if query_times:
                avg_time = sum(query_times) / len(query_times)
                p95_time = sorted(query_times)[int(len(query_times) * 0.95)] if query_times else 0
                
                if avg_time > 1.0:  # Slow queries
                    insights["performance_bottlenecks"].append({
                        "issue": "Slow average query time",
                        "metric": f"{avg_time:.3f}s average",
                        "recommendation": "Consider query optimization or index improvements"
                    })
                
                if p95_time > 3.0:  # Very slow p95
                    insights["performance_bottlenecks"].append({
                        "issue": "Slow 95th percentile query time",
                        "metric": f"{p95_time:.3f}s P95",
                        "recommendation": "Investigate and optimize slowest queries"
                    })
            
            # Analyze cache efficiency
            cache_hits = sum(1 for e in self.events[-1000:] if e.cache_hit)
            cache_requests = len([e for e in self.events[-1000:] if e.event_type == SearchEventType.QUERY_EXECUTED])
            
            if cache_requests > 0:
                cache_hit_rate = cache_hits / cache_requests
                if cache_hit_rate < 0.5:
                    insights["optimization_opportunities"].append({
                        "opportunity": "Low cache hit rate",
                        "metric": f"{cache_hit_rate:.1%}",
                        "potential_improvement": "Improve caching strategy for better performance"
                    })
            
            # Analyze user behavior
            failed_searches = len([e for e in self.events[-1000:] if not e.success])
            total_searches = len([e for e in self.events[-1000:] if e.event_type == SearchEventType.QUERY_EXECUTED])
            
            if total_searches > 0:
                failure_rate = failed_searches / total_searches
                if failure_rate > 0.1:
                    insights["user_experience_issues"].append({
                        "issue": "High search failure rate",
                        "metric": f"{failure_rate:.1%}",
                        "impact": "Poor user experience"
                    })
            
            # Pattern-based insights
            for pattern in self.patterns.values():
                if pattern.success_rate < 0.7 and pattern.frequency > 10:
                    insights["optimization_opportunities"].append({
                        "opportunity": "Frequently failing query pattern",
                        "pattern": pattern.queries[0] if pattern.queries else "Unknown",
                        "frequency": pattern.frequency,
                        "success_rate": f"{pattern.success_rate:.1%}"
                    })
            
            return insights
            
        except Exception as e:
            logger.error(f"Failed to generate optimization insights: {e}")
            return {"error": str(e)}

    def create_performance_snapshot(self) -> PerformanceSnapshot:
        """Create a performance snapshot for trending analysis."""
        try:
            recent_events = self.events[-1000:]  # Last 1000 events
            
            # Calculate metrics
            query_events = [e for e in recent_events if e.event_type == SearchEventType.QUERY_EXECUTED]
            
            snapshot = PerformanceSnapshot()
            
            if query_events:
                # Query performance
                query_times = [e.execution_time for e in query_events if e.execution_time > 0]
                if query_times:
                    snapshot.avg_query_time = sum(query_times) / len(query_times)
                
                # Success rate
                successful = sum(1 for e in query_events if e.success)
                snapshot.successful_query_rate = successful / len(query_events)
                
                # Results per query
                result_counts = [e.result_count for e in query_events]
                if result_counts:
                    snapshot.avg_results_per_query = sum(result_counts) / len(result_counts)
                
                # Cache hit rate
                cache_hits = sum(1 for e in query_events if e.cache_hit)
                snapshot.cache_hit_rate = cache_hits / len(query_events)
                
                # Volume metrics
                snapshot.unique_users = len(set(e.user_id for e in query_events if e.user_id))
                
                # Calculate queries per hour
                if query_events:
                    time_span = (query_events[-1].timestamp - query_events[0].timestamp).total_seconds() / 3600
                    if time_span > 0:
                        snapshot.queries_per_hour = len(query_events) / time_span
            
            snapshot.total_events = len(recent_events)
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to create performance snapshot: {e}")
            return PerformanceSnapshot()

    def clear_analytics_data(self, older_than: Optional[timedelta] = None) -> int:
        """
        Clear analytics data.

        Args:
            older_than: Clear data older than this threshold

        Returns:
            Number of events removed
        """
        try:
            if older_than is None:
                # Clear all data
                removed_count = len(self.events)
                self.events.clear()
                self.patterns.clear()
                self.performance_snapshots.clear()
                self.performance_buffer.clear()
                self.user_sessions.clear()
                self.query_sequences.clear()
                self.query_cache.clear()
            else:
                # Clear old data
                cutoff_time = datetime.now(timezone.utc) - older_than
                old_count = len(self.events)
                
                self.events = [e for e in self.events if e.timestamp >= cutoff_time]
                removed_count = old_count - len(self.events)
                
                # Clear old patterns
                old_patterns = {
                    k: p for k, p in self.patterns.items() 
                    if p.last_seen < cutoff_time
                }
                for pattern_id in old_patterns:
                    del self.patterns[pattern_id]
                
                # Clear old snapshots
                self.performance_snapshots = [
                    s for s in self.performance_snapshots 
                    if s.timestamp >= cutoff_time
                ]
            
            logger.info(f"Cleared {removed_count} analytics events")
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to clear analytics data: {e}")
            return 0

    def save_analytics_data(self) -> None:
        """Save analytics data to disk."""
        try:
            # Create snapshot before saving
            current_snapshot = self.create_performance_snapshot()
            self.performance_snapshots.append(current_snapshot)
            
            # Limit snapshots
            if len(self.performance_snapshots) > 1000:
                self.performance_snapshots = self.performance_snapshots[-1000:]
            
            # Save events
            events_data = [asdict(event) for event in self.events[-10000:]]  # Keep last 10k
            with open(self.events_file, 'w', encoding='utf-8') as f:
                json.dump(events_data, f, indent=2, default=str)
            
            # Save patterns
            patterns_data = {k: asdict(p) for k, p in self.patterns.items()}
            # Convert sets to lists for JSON serialization
            for pattern_data in patterns_data.values():
                if 'unique_users' in pattern_data and isinstance(pattern_data['unique_users'], set):
                    pattern_data['unique_users'] = list(pattern_data['unique_users'])
            
            with open(self.patterns_file, 'w', encoding='utf-8') as f:
                json.dump(patterns_data, f, indent=2, default=str)
            
            # Save performance snapshots
            snapshots_data = [asdict(snapshot) for snapshot in self.performance_snapshots]
            with open(self.performance_file, 'w', encoding='utf-8') as f:
                json.dump(snapshots_data, f, indent=2, default=str)
            
            logger.debug("Analytics data saved to disk")
            
        except Exception as e:
            logger.error(f"Failed to save analytics data: {e}")

    # Private helper methods

    def _load_analytics_data(self) -> None:
        """Load analytics data from disk."""
        try:
            # Load events
            if self.events_file.exists():
                with open(self.events_file, 'r', encoding='utf-8') as f:
                    events_data = json.load(f)
                    
                for event_data in events_data:
                    # Convert timestamp back to datetime
                    event_data['timestamp'] = datetime.fromisoformat(event_data['timestamp'])
                    event = SearchEvent(**event_data)
                    self.events.append(event)
            
            # Load patterns
            if self.patterns_file.exists():
                with open(self.patterns_file, 'r', encoding='utf-8') as f:
                    patterns_data = json.load(f)
                    
                for pattern_id, pattern_data in patterns_data.items():
                    # Convert datetime strings back
                    pattern_data['first_seen'] = datetime.fromisoformat(pattern_data['first_seen'])
                    pattern_data['last_seen'] = datetime.fromisoformat(pattern_data['last_seen'])
                    # Convert lists back to sets
                    if 'unique_users' in pattern_data:
                        pattern_data['unique_users'] = set(pattern_data['unique_users'])
                    
                    pattern = SearchPattern(**pattern_data)
                    self.patterns[pattern_id] = pattern
            
            # Load performance snapshots
            if self.performance_file.exists():
                with open(self.performance_file, 'r', encoding='utf-8') as f:
                    snapshots_data = json.load(f)
                    
                for snapshot_data in snapshots_data:
                    snapshot_data['timestamp'] = datetime.fromisoformat(snapshot_data['timestamp'])
                    snapshot = PerformanceSnapshot(**snapshot_data)
                    self.performance_snapshots.append(snapshot)
            
            logger.debug(f"Loaded {len(self.events)} events, {len(self.patterns)} patterns, "
                        f"{len(self.performance_snapshots)} snapshots")
            
        except Exception as e:
            logger.warning(f"Failed to load analytics data: {e}")

    async def _update_patterns(self, event: SearchEvent) -> None:
        """Update search patterns based on new event."""
        try:
            if not event.query:
                return
            
            # Simple pattern: normalize query for pattern matching
            normalized_query = event.query.lower().strip()
            
            # Find or create pattern
            pattern_id = f"query_{hash(normalized_query) % 10000}"
            
            if pattern_id not in self.patterns:
                self.patterns[pattern_id] = SearchPattern(
                    pattern_id=pattern_id,
                    pattern_type="common_query",
                    queries=[event.query],
                    first_seen=event.timestamp
                )
            
            pattern = self.patterns[pattern_id]
            
            # Update pattern
            if event.query not in pattern.queries:
                pattern.queries.append(event.query)
            
            pattern.frequency += 1
            pattern.last_seen = event.timestamp
            
            if event.user_id:
                pattern.unique_users.add(event.user_id)
            
            if event.filters_applied:
                pattern.common_filters.extend(event.filters_applied)
            
            # Update performance metrics
            if event.execution_time > 0:
                # Simple running average
                current_avg = pattern.avg_execution_time
                pattern.avg_execution_time = (current_avg * (pattern.frequency - 1) + event.execution_time) / pattern.frequency
            
            if event.result_count >= 0:
                current_avg = pattern.typical_result_count
                pattern.typical_result_count = (current_avg * (pattern.frequency - 1) + event.result_count) / pattern.frequency
            
            # Update success rate
            success_count = pattern.success_rate * (pattern.frequency - 1) + (1 if event.success else 0)
            pattern.success_rate = success_count / pattern.frequency
            
        except Exception as e:
            logger.error(f"Failed to update patterns: {e}")

    async def _generate_summary_stats(self, events: List[SearchEvent]) -> Dict[str, Any]:
        """Generate summary statistics from events."""
        if not events:
            return {}
        
        return {
            "total_events": len(events),
            "unique_sessions": len(set(e.session_id for e in events if e.session_id)),
            "unique_users": len(set(e.user_id for e in events if e.user_id)),
            "query_count": len([e for e in events if e.event_type == SearchEventType.QUERY_EXECUTED]),
            "success_rate": sum(1 for e in events if e.success) / len(events),
            "avg_result_count": sum(e.result_count for e in events) / len(events) if events else 0,
            "time_span_hours": (events[-1].timestamp - events[0].timestamp).total_seconds() / 3600 if len(events) > 1 else 0
        }

    async def _analyze_queries(self, events: List[SearchEvent]) -> Dict[str, Any]:
        """Analyze query patterns and characteristics."""
        query_events = [e for e in events if e.event_type == SearchEventType.QUERY_EXECUTED and e.query]
        
        if not query_events:
            return {}
        
        # Query frequency analysis
        query_counts = Counter(e.query.lower() for e in query_events)
        
        # Performance analysis
        query_times = [e.execution_time for e in query_events if e.execution_time > 0]
        
        return {
            "total_queries": len(query_events),
            "unique_queries": len(query_counts),
            "most_common_queries": query_counts.most_common(10),
            "avg_execution_time": sum(query_times) / len(query_times) if query_times else 0,
            "slowest_queries": sorted(
                [(e.query, e.execution_time) for e in query_events if e.execution_time > 0],
                key=lambda x: x[1], reverse=True
            )[:10]
        }

    async def _analyze_user_behavior(self, events: List[SearchEvent]) -> Dict[str, Any]:
        """Analyze user behavior patterns."""
        # Session analysis
        sessions = defaultdict(list)
        for event in events:
            if event.session_id:
                sessions[event.session_id].append(event)
        
        if not sessions:
            return {}
        
        # Calculate session metrics
        session_lengths = [len(events) for events in sessions.values()]
        session_durations = []
        
        for session_events in sessions.values():
            if len(session_events) > 1:
                duration = (session_events[-1].timestamp - session_events[0].timestamp).total_seconds()
                session_durations.append(duration)
        
        return {
            "total_sessions": len(sessions),
            "avg_events_per_session": sum(session_lengths) / len(session_lengths) if session_lengths else 0,
            "avg_session_duration_minutes": sum(session_durations) / len(session_durations) / 60 if session_durations else 0,
            "click_through_rate": len([e for e in events if e.clicked_result_position is not None]) / 
                                len([e for e in events if e.event_type == SearchEventType.QUERY_EXECUTED]) if events else 0
        }

    async def _analyze_performance(self) -> Dict[str, Any]:
        """Analyze system performance metrics."""
        performance_data = {}
        
        for metric, values in self.performance_buffer.items():
            if values:
                performance_data[metric] = {
                    "count": len(values),
                    "average": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "median": statistics.median(values),
                    "p95": sorted(values)[int(len(values) * 0.95)] if values else 0
                }
        
        return performance_data

    async def _analyze_patterns(self) -> Dict[str, Any]:
        """Analyze identified search patterns."""
        if not self.patterns:
            return {}
        
        # Sort patterns by frequency
        frequent_patterns = sorted(
            self.patterns.values(),
            key=lambda p: p.frequency,
            reverse=True
        )[:10]
        
        return {
            "total_patterns": len(self.patterns),
            "most_frequent_patterns": [
                {
                    "queries": p.queries[:5],  # First 5 query variations
                    "frequency": p.frequency,
                    "success_rate": p.success_rate,
                    "unique_users": len(p.unique_users),
                    "avg_execution_time": p.avg_execution_time
                }
                for p in frequent_patterns
            ]
        }

    async def _generate_recommendations(self, events: List[SearchEvent]) -> List[Dict[str, str]]:
        """Generate optimization recommendations based on analytics."""
        recommendations = []
        
        # Analyze for common issues
        query_events = [e for e in events if e.event_type == SearchEventType.QUERY_EXECUTED]
        
        if query_events:
            # Check for slow queries
            slow_queries = [e for e in query_events if e.execution_time > 2.0]
            if len(slow_queries) / len(query_events) > 0.1:
                recommendations.append({
                    "type": "performance",
                    "issue": "High percentage of slow queries detected",
                    "recommendation": "Consider optimizing search algorithms or adding more aggressive caching",
                    "priority": "high"
                })
            
            # Check for low success rate
            success_rate = sum(1 for e in query_events if e.success) / len(query_events)
            if success_rate < 0.8:
                recommendations.append({
                    "type": "quality",
                    "issue": f"Search success rate is {success_rate:.1%}",
                    "recommendation": "Review search logic and error handling to improve success rate",
                    "priority": "medium"
                })
            
            # Check for low cache utilization
            cache_hits = sum(1 for e in query_events if e.cache_hit)
            if cache_hits / len(query_events) < 0.3:
                recommendations.append({
                    "type": "efficiency",
                    "issue": "Low cache hit rate",
                    "recommendation": "Improve caching strategy to reduce query execution time",
                    "priority": "medium"
                })
        
        return recommendations
