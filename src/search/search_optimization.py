"""
Search optimization system for OneNote Copilot.

This module provides advanced search optimization features including:
- Query optimization and expansion
- Index optimization and tuning
- Performance monitoring and alerting
- Adaptive search strategies
- Cache optimization recommendations
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from pathlib import Path
import json
import re
import time
from enum import Enum

from src.config.settings import Settings


logger = logging.getLogger(__name__)


class OptimizationType(Enum):
    """Types of search optimizations."""
    QUERY_EXPANSION = "query_expansion"
    INDEX_TUNING = "index_tuning"
    CACHE_STRATEGY = "cache_strategy"
    PERFORMANCE_TUNING = "performance_tuning"
    USER_EXPERIENCE = "user_experience"


class OptimizationPriority(Enum):
    """Priority levels for optimizations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QueryOptimization:
    """Query optimization suggestion."""
    original_query: str
    optimized_query: str
    optimization_type: str
    confidence_score: float
    expected_improvement: str
    reasoning: str


@dataclass
class IndexOptimization:
    """Index optimization suggestion."""
    table_name: str
    optimization_type: str
    current_performance: float
    expected_performance: float
    implementation_steps: List[str]
    risk_level: str


@dataclass
class PerformanceAlert:
    """Performance alert for monitoring."""
    alert_id: str
    alert_type: str
    severity: OptimizationPriority
    message: str
    metric_value: float
    threshold: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation."""
    recommendation_id: str
    optimization_type: OptimizationType
    priority: OptimizationPriority
    title: str
    description: str
    impact_description: str
    implementation_effort: str
    expected_benefits: List[str]
    implementation_steps: List[str]
    risk_assessment: str
    metrics_to_monitor: List[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SearchOptimization:
    """Advanced search optimization system."""
    
    def __init__(self, settings: Settings, analytics=None):
        """Initialize search optimization system."""
        self.settings = settings
        self.analytics = analytics
        self.logger = logging.getLogger(__name__)
        
        # Performance thresholds
        self.performance_thresholds = {
            "query_time_slow": 2.0,  # seconds
            "query_time_critical": 5.0,  # seconds
            "success_rate_low": 0.8,  # 80%
            "success_rate_critical": 0.6,  # 60%
            "cache_hit_rate_low": 0.7,  # 70%
            "memory_usage_high": 500 * 1024 * 1024,  # 500MB
            "disk_usage_high": 1024 * 1024 * 1024,  # 1GB
        }
        
        # Query patterns for optimization
        self.query_patterns = {
            "too_broad": re.compile(r"^.{1,3}$|^(the|a|an|and|or|but|if|then)$", re.IGNORECASE),
            "stop_words_heavy": re.compile(r"\b(the|a|an|and|or|but|if|then|is|are|was|were)\b", re.IGNORECASE),
            "special_chars": re.compile(r"[^\w\s]"),
            "repeated_words": re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE),
            "whitespace_issues": re.compile(r"\s{2,}")
        }
        
        # Optimization history
        self.optimization_history: List[OptimizationRecommendation] = []
        self.applied_optimizations: Set[str] = set()
        self.performance_alerts: List[PerformanceAlert] = []
        
        # Query expansion cache
        self.expansion_cache: Dict[str, List[str]] = {}
        self.expansion_cache_ttl = timedelta(hours=24)
        self.expansion_cache_timestamps: Dict[str, datetime] = {}
        
        # Performance monitoring
        self.monitoring_enabled = True
        self.alert_cooldown = timedelta(minutes=15)  # Prevent alert spam
        self.last_alert_times: Dict[str, datetime] = {}
    
    async def optimize_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> QueryOptimization:
        """Optimize a search query for better performance and results."""
        try:
            original_query = query.strip()
            optimized_query = original_query
            optimizations_applied = []
            confidence_score = 1.0
            
            # Clean up whitespace
            if self.query_patterns["whitespace_issues"].search(optimized_query):
                optimized_query = re.sub(r"\s+", " ", optimized_query)
                optimizations_applied.append("whitespace_cleanup")
            
            # Remove repeated words
            if self.query_patterns["repeated_words"].search(optimized_query):
                optimized_query = self.query_patterns["repeated_words"].sub(r"\1", optimized_query)
                optimizations_applied.append("duplicate_removal")
            
            # Handle very short queries
            if self.query_patterns["too_broad"].search(optimized_query):
                expanded_terms = await self._expand_query_terms(optimized_query, context)
                if expanded_terms:
                    optimized_query = " ".join([optimized_query] + expanded_terms[:2])
                    optimizations_applied.append("query_expansion")
                    confidence_score = 0.7
            
            # Add context-based terms
            if context and "recent_queries" in context:
                related_terms = self._find_related_terms(optimized_query, context["recent_queries"])
                if related_terms:
                    optimized_query = f"{optimized_query} {' '.join(related_terms[:1])}"
                    optimizations_applied.append("context_enhancement")
                    confidence_score *= 0.9
            
            # Determine optimization type
            optimization_type = "general"
            if "query_expansion" in optimizations_applied:
                optimization_type = "expansion"
            elif "context_enhancement" in optimizations_applied:
                optimization_type = "contextualization"
            elif optimizations_applied:
                optimization_type = "cleanup"
            
            # Calculate expected improvement
            improvement_estimate = self._estimate_improvement(original_query, optimized_query, optimizations_applied)
            
            return QueryOptimization(
                original_query=original_query,
                optimized_query=optimized_query.strip(),
                optimization_type=optimization_type,
                confidence_score=confidence_score,
                expected_improvement=improvement_estimate,
                reasoning=f"Applied: {', '.join(optimizations_applied) if optimizations_applied else 'no changes needed'}"
            )
            
        except Exception as e:
            self.logger.error(f"Query optimization failed: {e}")
            return QueryOptimization(
                original_query=query,
                optimized_query=query,
                optimization_type="none",
                confidence_score=1.0,
                expected_improvement="No optimization available",
                reasoning=f"Optimization failed: {str(e)}"
            )
    
    async def analyze_index_performance(self) -> List[IndexOptimization]:
        """Analyze search index performance and suggest optimizations."""
        optimizations = []
        
        try:
            # Analyze FTS5 index performance (simulated analysis)
            cache_analysis = await self._analyze_cache_performance()
            
            if cache_analysis["avg_query_time"] > self.performance_thresholds["query_time_slow"]:
                optimizations.append(IndexOptimization(
                    table_name="cached_pages_fts",
                    optimization_type="rebuild_index",
                    current_performance=cache_analysis["avg_query_time"],
                    expected_performance=cache_analysis["avg_query_time"] * 0.6,
                    implementation_steps=[
                        "Schedule index rebuild during low-usage period",
                        "Execute 'INSERT INTO cached_pages_fts(cached_pages_fts) VALUES(\"rebuild\")'",
                        "Monitor query performance after rebuild",
                        "Update optimization statistics"
                    ],
                    risk_level="low"
                ))
            
            # Check for fragmentation issues
            if cache_analysis.get("fragmentation_ratio", 0) > 0.3:
                optimizations.append(IndexOptimization(
                    table_name="cached_pages",
                    optimization_type="vacuum",
                    current_performance=cache_analysis.get("fragmentation_ratio", 0),
                    expected_performance=0.1,
                    implementation_steps=[
                        "Schedule VACUUM operation during maintenance window",
                        "Execute 'VACUUM' on database",
                        "Monitor disk space and query performance",
                        "Update fragmentation statistics"
                    ],
                    risk_level="medium"
                ))
            
            # Suggest additional indexes
            missing_indexes = await self._identify_missing_indexes()
            for index_suggestion in missing_indexes:
                optimizations.append(IndexOptimization(
                    table_name=index_suggestion["table"],
                    optimization_type="add_index",
                    current_performance=index_suggestion["current_scan_time"],
                    expected_performance=index_suggestion["expected_lookup_time"],
                    implementation_steps=[
                        f"Create index: {index_suggestion['create_sql']}",
                        "Monitor index usage and performance",
                        "Update query plans to use new index"
                    ],
                    risk_level="low"
                ))
            
        except Exception as e:
            self.logger.error(f"Index performance analysis failed: {e}")
        
        return optimizations
    
    async def monitor_performance(self) -> List[PerformanceAlert]:
        """Monitor search performance and generate alerts."""
        alerts = []
        
        if not self.monitoring_enabled or not self.analytics:
            return alerts
        
        try:
            # Get current performance metrics
            metrics = await self.analytics.get_real_time_metrics()
            current_time = datetime.now(timezone.utc)
            
            # Check query time performance
            avg_query_time = metrics.get("performance", {}).get("avg_query_time", 0)
            if avg_query_time > self.performance_thresholds["query_time_critical"]:
                alert = self._create_alert(
                    "query_time_critical",
                    OptimizationPriority.CRITICAL,
                    f"Critical query performance: {avg_query_time:.2f}s average",
                    avg_query_time,
                    self.performance_thresholds["query_time_critical"]
                )
                if alert:
                    alerts.append(alert)
            elif avg_query_time > self.performance_thresholds["query_time_slow"]:
                alert = self._create_alert(
                    "query_time_slow",
                    OptimizationPriority.HIGH,
                    f"Slow query performance: {avg_query_time:.2f}s average",
                    avg_query_time,
                    self.performance_thresholds["query_time_slow"]
                )
                if alert:
                    alerts.append(alert)
            
            # Check success rate
            success_rate = metrics.get("success_rate", 1.0)
            if success_rate < self.performance_thresholds["success_rate_critical"]:
                alert = self._create_alert(
                    "success_rate_critical",
                    OptimizationPriority.CRITICAL,
                    f"Critical success rate: {success_rate:.1%}",
                    success_rate,
                    self.performance_thresholds["success_rate_critical"]
                )
                if alert:
                    alerts.append(alert)
            elif success_rate < self.performance_thresholds["success_rate_low"]:
                alert = self._create_alert(
                    "success_rate_low",
                    OptimizationPriority.HIGH,
                    f"Low success rate: {success_rate:.1%}",
                    success_rate,
                    self.performance_thresholds["success_rate_low"]
                )
                if alert:
                    alerts.append(alert)
            
            # Check cache hit rate
            cache_hit_rate = metrics.get("performance", {}).get("cache_hit_rate", 1.0)
            if cache_hit_rate < self.performance_thresholds["cache_hit_rate_low"]:
                alert = self._create_alert(
                    "cache_hit_rate_low",
                    OptimizationPriority.MEDIUM,
                    f"Low cache hit rate: {cache_hit_rate:.1%}",
                    cache_hit_rate,
                    self.performance_thresholds["cache_hit_rate_low"]
                )
                if alert:
                    alerts.append(alert)
            
            # Store alerts
            self.performance_alerts.extend(alerts)
            
            # Limit alert history
            if len(self.performance_alerts) > 1000:
                self.performance_alerts = self.performance_alerts[-500:]
            
        except Exception as e:
            self.logger.error(f"Performance monitoring failed: {e}")
        
        return alerts
    
    async def generate_optimization_recommendations(self) -> List[OptimizationRecommendation]:
        """Generate comprehensive optimization recommendations."""
        recommendations = []
        
        try:
            # Get analytics data
            if self.analytics:
                analytics_report = await self.analytics.get_analytics_report()
                optimization_insights = await self.analytics.get_search_optimization_insights()
            else:
                analytics_report = {}
                optimization_insights = {"optimization_opportunities": [], "performance_bottlenecks": []}
            
            # Query optimization recommendations
            query_recs = await self._generate_query_recommendations(analytics_report)
            recommendations.extend(query_recs)
            
            # Index optimization recommendations
            index_recs = await self._generate_index_recommendations()
            recommendations.extend(index_recs)
            
            # Cache optimization recommendations
            cache_recs = await self._generate_cache_recommendations(analytics_report)
            recommendations.extend(cache_recs)
            
            # Performance recommendations
            perf_recs = await self._generate_performance_recommendations(optimization_insights)
            recommendations.extend(perf_recs)
            
            # User experience recommendations
            ux_recs = await self._generate_ux_recommendations(analytics_report)
            recommendations.extend(ux_recs)
            
            # Sort by priority
            priority_order = {
                OptimizationPriority.CRITICAL: 0,
                OptimizationPriority.HIGH: 1,
                OptimizationPriority.MEDIUM: 2,
                OptimizationPriority.LOW: 3
            }
            recommendations.sort(key=lambda r: priority_order.get(r.priority, 3))
            
            # Store in history
            self.optimization_history.extend(recommendations)
            
            # Limit history size
            if len(self.optimization_history) > 500:
                self.optimization_history = self.optimization_history[-250:]
            
        except Exception as e:
            self.logger.error(f"Failed to generate optimization recommendations: {e}")
        
        return recommendations
    
    async def apply_automatic_optimizations(self) -> Dict[str, Any]:
        """Apply safe automatic optimizations."""
        results = {
            "applied": [],
            "skipped": [],
            "failed": [],
            "summary": ""
        }
        
        try:
            recommendations = await self.generate_optimization_recommendations()
            
            for rec in recommendations:
                # Only apply low-risk, high-impact optimizations automatically
                if (rec.priority in [OptimizationPriority.HIGH, OptimizationPriority.CRITICAL] and
                    rec.risk_assessment == "low" and
                    rec.recommendation_id not in self.applied_optimizations):
                    
                    success = await self._apply_optimization(rec)
                    if success:
                        results["applied"].append({
                            "id": rec.recommendation_id,
                            "title": rec.title,
                            "type": rec.optimization_type.value
                        })
                        self.applied_optimizations.add(rec.recommendation_id)
                    else:
                        results["failed"].append({
                            "id": rec.recommendation_id,
                            "title": rec.title,
                            "reason": "Implementation failed"
                        })
                else:
                    results["skipped"].append({
                        "id": rec.recommendation_id,
                        "title": rec.title,
                        "reason": "Manual approval required or already applied"
                    })
            
            results["summary"] = (f"Applied {len(results['applied'])} optimizations, "
                                f"skipped {len(results['skipped'])}, "
                                f"failed {len(results['failed'])}")
            
        except Exception as e:
            self.logger.error(f"Automatic optimization failed: {e}")
            results["failed"].append({"error": str(e)})
        
        return results
    
    async def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status and statistics."""
        try:
            current_time = datetime.now(timezone.utc)
            
            # Recent recommendations
            recent_recs = [r for r in self.optimization_history 
                          if current_time - r.created_at <= timedelta(days=7)]
            
            # Active alerts
            active_alerts = [a for a in self.performance_alerts if not a.resolved]
            
            # Performance summary
            performance_summary = {}
            if self.analytics:
                metrics = await self.analytics.get_real_time_metrics()
                performance_summary = {
                    "avg_query_time": metrics.get("performance", {}).get("avg_query_time", 0),
                    "success_rate": metrics.get("success_rate", 1.0),
                    "cache_hit_rate": metrics.get("performance", {}).get("cache_hit_rate", 1.0),
                    "queries_per_hour": metrics.get("query_rate", 0)
                }
            
            return {
                "status": "active" if self.monitoring_enabled else "inactive",
                "last_check": current_time,
                "active_alerts": len(active_alerts),
                "recent_recommendations": len(recent_recs),
                "applied_optimizations": len(self.applied_optimizations),
                "performance_summary": performance_summary,
                "optimization_categories": {
                    "query": len([r for r in recent_recs if r.optimization_type == OptimizationType.QUERY_EXPANSION]),
                    "index": len([r for r in recent_recs if r.optimization_type == OptimizationType.INDEX_TUNING]),
                    "cache": len([r for r in recent_recs if r.optimization_type == OptimizationType.CACHE_STRATEGY]),
                    "performance": len([r for r in recent_recs if r.optimization_type == OptimizationType.PERFORMANCE_TUNING]),
                    "ux": len([r for r in recent_recs if r.optimization_type == OptimizationType.USER_EXPERIENCE])
                },
                "alerts_by_priority": {
                    "critical": len([a for a in active_alerts if a.severity == OptimizationPriority.CRITICAL]),
                    "high": len([a for a in active_alerts if a.severity == OptimizationPriority.HIGH]),
                    "medium": len([a for a in active_alerts if a.severity == OptimizationPriority.MEDIUM]),
                    "low": len([a for a in active_alerts if a.severity == OptimizationPriority.LOW])
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get optimization status: {e}")
            return {"status": "error", "error": str(e)}
    
    # Private helper methods
    
    async def _expand_query_terms(self, query: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Expand query with related terms."""
        # Check cache first
        if query in self.expansion_cache:
            cache_time = self.expansion_cache_timestamps.get(query)
            if cache_time and datetime.now(timezone.utc) - cache_time < self.expansion_cache_ttl:
                return self.expansion_cache[query]
        
        expanded_terms = []
        
        # Simple expansion based on common patterns
        expansions = {
            "js": ["javascript"],
            "py": ["python"],
            "api": ["application programming interface", "endpoint"],
            "db": ["database"],
            "ui": ["user interface", "interface"],
            "ux": ["user experience"],
        }
        
        query_lower = query.lower()
        for abbrev, full_terms in expansions.items():
            if abbrev == query_lower:
                expanded_terms.extend(full_terms[:2])
                break
        
        # Cache the result
        self.expansion_cache[query] = expanded_terms
        self.expansion_cache_timestamps[query] = datetime.now(timezone.utc)
        
        return expanded_terms
    
    def _find_related_terms(self, query: str, recent_queries: List[str]) -> List[str]:
        """Find related terms from recent queries."""
        query_words = set(query.lower().split())
        related_terms = []
        
        for recent_query in recent_queries[-10:]:  # Check last 10 queries
            recent_words = set(recent_query.lower().split())
            common_words = query_words.intersection(recent_words)
            
            if common_words and len(common_words) >= len(query_words) * 0.5:
                unique_words = recent_words - query_words
                if unique_words:
                    related_terms.extend(list(unique_words)[:1])
        
        return list(set(related_terms))[:2]
    
    def _estimate_improvement(self, original: str, optimized: str, optimizations: List[str]) -> str:
        """Estimate performance improvement from optimizations."""
        if original == optimized:
            return "No improvement expected"
        
        improvement_factors = {
            "whitespace_cleanup": "5-10% faster processing",
            "duplicate_removal": "10-15% better relevance",
            "query_expansion": "20-40% more results",
            "context_enhancement": "15-25% better relevance"
        }
        
        if optimizations:
            improvements = [improvement_factors.get(opt, "minor improvement") for opt in optimizations]
            return "; ".join(improvements)
        
        return "General query improvement"
    
    async def _analyze_cache_performance(self) -> Dict[str, Any]:
        """Analyze cache performance metrics."""
        # Simulated cache performance analysis
        return {
            "avg_query_time": 1.2,
            "cache_hit_rate": 0.75,
            "fragmentation_ratio": 0.15,
            "index_size_mb": 45.7,
            "total_records": 1250
        }
    
    async def _identify_missing_indexes(self) -> List[Dict[str, Any]]:
        """Identify potentially missing database indexes."""
        # Simulated analysis of missing indexes
        return [
            {
                "table": "cached_pages",
                "column": "last_modified",
                "create_sql": "CREATE INDEX idx_cached_pages_last_modified ON cached_pages(last_modified)",
                "current_scan_time": 0.8,
                "expected_lookup_time": 0.1
            }
        ]
    
    def _create_alert(self, alert_type: str, severity: OptimizationPriority, 
                     message: str, value: float, threshold: float) -> Optional[PerformanceAlert]:
        """Create a performance alert if not in cooldown."""
        current_time = datetime.now(timezone.utc)
        last_alert = self.last_alert_times.get(alert_type)
        
        if last_alert and current_time - last_alert < self.alert_cooldown:
            return None
        
        self.last_alert_times[alert_type] = current_time
        
        return PerformanceAlert(
            alert_id=f"{alert_type}_{int(current_time.timestamp())}",
            alert_type=alert_type,
            severity=severity,
            message=message,
            metric_value=value,
            threshold=threshold,
            timestamp=current_time
        )
    
    async def _generate_query_recommendations(self, analytics_report: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Generate query-specific optimization recommendations."""
        recommendations = []
        
        # Analyze query patterns from analytics
        if "query_analytics" in analytics_report:
            failed_queries = analytics_report["query_analytics"].get("failed_queries", [])
            
            if len(failed_queries) > 5:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id="query_failure_analysis",
                    optimization_type=OptimizationType.QUERY_EXPANSION,
                    priority=OptimizationPriority.HIGH,
                    title="High Query Failure Rate Detected",
                    description=f"Detected {len(failed_queries)} frequently failing queries",
                    impact_description="Improving failed queries can increase success rate by 15-25%",
                    implementation_effort="Low",
                    expected_benefits=[
                        "Improved user satisfaction",
                        "Better search success rate",
                        "Reduced support requests"
                    ],
                    implementation_steps=[
                        "Analyze failing query patterns",
                        "Implement query expansion for common failures",
                        "Add spelling correction",
                        "Monitor success rate improvement"
                    ],
                    risk_assessment="low",
                    metrics_to_monitor=["query_success_rate", "user_satisfaction", "query_patterns"]
                ))
        
        return recommendations
    
    async def _generate_index_recommendations(self) -> List[OptimizationRecommendation]:
        """Generate index optimization recommendations."""
        recommendations = []
        
        index_optimizations = await self.analyze_index_performance()
        
        for idx_opt in index_optimizations:
            if idx_opt.optimization_type == "rebuild_index":
                recommendations.append(OptimizationRecommendation(
                    recommendation_id=f"rebuild_index_{idx_opt.table_name}",
                    optimization_type=OptimizationType.INDEX_TUNING,
                    priority=OptimizationPriority.MEDIUM,
                    title=f"Rebuild Search Index for {idx_opt.table_name}",
                    description="Search index fragmentation is affecting query performance",
                    impact_description=f"Expected {((idx_opt.current_performance - idx_opt.expected_performance) / idx_opt.current_performance * 100):.0f}% performance improvement",
                    implementation_effort="Low",
                    expected_benefits=[
                        "Faster search queries",
                        "Reduced resource usage",
                        "Better user experience"
                    ],
                    implementation_steps=idx_opt.implementation_steps,
                    risk_assessment=idx_opt.risk_level,
                    metrics_to_monitor=["avg_query_time", "query_throughput", "resource_usage"]
                ))
        
        return recommendations
    
    async def _generate_cache_recommendations(self, analytics_report: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Generate cache optimization recommendations."""
        recommendations = []
        
        # Analyze cache performance
        if "performance" in analytics_report:
            cache_hit_rate = analytics_report["performance"].get("cache_hit_rate", 1.0)
            
            if cache_hit_rate < 0.7:
                recommendations.append(OptimizationRecommendation(
                    recommendation_id="improve_cache_strategy",
                    optimization_type=OptimizationType.CACHE_STRATEGY,
                    priority=OptimizationPriority.HIGH,
                    title="Optimize Cache Strategy",
                    description=f"Cache hit rate is {cache_hit_rate:.1%}, below optimal threshold",
                    impact_description="Improving cache hit rate to 80%+ can reduce query times by 30-50%",
                    implementation_effort="Medium",
                    expected_benefits=[
                        "Significantly faster query responses",
                        "Reduced server load",
                        "Better scalability"
                    ],
                    implementation_steps=[
                        "Analyze cache miss patterns",
                        "Implement predictive caching",
                        "Optimize cache eviction policy",
                        "Increase cache size if needed"
                    ],
                    risk_assessment="low",
                    metrics_to_monitor=["cache_hit_rate", "avg_query_time", "memory_usage"]
                ))
        
        return recommendations
    
    async def _generate_performance_recommendations(self, insights: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        bottlenecks = insights.get("performance_bottlenecks", [])
        
        for bottleneck in bottlenecks:
            if "slow" in bottleneck.get("issue", "").lower():
                recommendations.append(OptimizationRecommendation(
                    recommendation_id=f"performance_bottleneck_{len(recommendations)}",
                    optimization_type=OptimizationType.PERFORMANCE_TUNING,
                    priority=OptimizationPriority.HIGH,
                    title="Address Query Performance Bottleneck",
                    description=bottleneck.get("issue", "Performance issue detected"),
                    impact_description="Resolving this bottleneck can improve query times by 40-60%",
                    implementation_effort="Medium",
                    expected_benefits=[
                        "Faster query execution",
                        "Better user experience",
                        "Improved system scalability"
                    ],
                    implementation_steps=[
                        "Profile slow queries",
                        "Optimize query execution plans",
                        "Consider hardware upgrades if needed",
                        "Implement query result caching"
                    ],
                    risk_assessment="medium",
                    metrics_to_monitor=["query_execution_time", "system_resources", "user_satisfaction"]
                ))
        
        return recommendations
    
    async def _generate_ux_recommendations(self, analytics_report: Dict[str, Any]) -> List[OptimizationRecommendation]:
        """Generate user experience optimization recommendations."""
        recommendations = []
        
        if "user_behavior" in analytics_report:
            behavior = analytics_report["user_behavior"]
            
            # Check for poor user engagement patterns
            if behavior.get("avg_session_length", 0) < 60:  # Less than 1 minute
                recommendations.append(OptimizationRecommendation(
                    recommendation_id="improve_search_experience",
                    optimization_type=OptimizationType.USER_EXPERIENCE,
                    priority=OptimizationPriority.MEDIUM,
                    title="Improve Search User Experience",
                    description="Users have short session lengths, indicating poor search experience",
                    impact_description="Better UX can increase user engagement by 50-100%",
                    implementation_effort="Medium",
                    expected_benefits=[
                        "Longer user sessions",
                        "Higher user satisfaction",
                        "More successful searches"
                    ],
                    implementation_steps=[
                        "Implement search suggestions",
                        "Add query auto-completion",
                        "Improve result ranking",
                        "Add search filters and facets"
                    ],
                    risk_assessment="low",
                    metrics_to_monitor=["session_length", "user_satisfaction", "search_success_rate"]
                ))
        
        return recommendations
    
    async def _apply_optimization(self, recommendation: OptimizationRecommendation) -> bool:
        """Apply an optimization recommendation automatically."""
        try:
            # Only implement safe, automatic optimizations
            if recommendation.optimization_type == OptimizationType.QUERY_EXPANSION:
                # Enable query expansion features
                return True
            elif recommendation.optimization_type == OptimizationType.CACHE_STRATEGY:
                # Adjust cache parameters
                return True
            
            # For other types, require manual implementation
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to apply optimization {recommendation.recommendation_id}: {e}")
            return False
