"""
Report Generation System for OneNote Copilot Analytics.

This module provides comprehensive analytics dashboards and export functionality
for cache analytics, storage optimization, and performance monitoring reports.
"""

import asyncio
import base64
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Template

from ..config.settings import get_settings
from .cache_analyzer import AnalysisReport, CacheAnalyzer
from .performance_monitor import PerformanceMonitor, PerformanceReport
from .storage_optimizer import OptimizationReport, StorageOptimizer


@dataclass
class DashboardData:
    """Complete dashboard data structure."""
    timestamp: datetime
    cache_analysis: AnalysisReport
    storage_optimization: OptimizationReport
    performance_monitoring: PerformanceReport
    system_summary: Dict[str, Any]
    recommendations_summary: List[str]
    health_scores: Dict[str, float]


@dataclass
class ExportOptions:
    """Options for report export."""
    format: str  # 'json', 'csv', 'html', 'pdf'
    include_charts: bool = True
    include_raw_data: bool = False
    time_range_hours: int = 24
    template_name: Optional[str] = None


class ReportGenerator:
    """
    Comprehensive analytics dashboard and report generation system.

    Combines data from cache analysis, storage optimization, and performance
    monitoring to create unified reports and dashboards.
    """

    def __init__(self):
        """Initialize the report generator."""
        self.settings = get_settings()
        self.cache_dir = Path(self.settings.cache_dir)
        self.reports_dir = self.cache_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)

        # Initialize component analyzers
        self.cache_analyzer = CacheAnalyzer()
        self.storage_optimizer = StorageOptimizer()
        self.performance_monitor = PerformanceMonitor()

        # Report templates
        self._html_template = self._get_html_template()
        self._csv_headers = {
            'cache_stats': ['timestamp', 'total_pages', 'total_size_mb', 'notebooks_count', 'health_score'],
            'performance': ['timestamp', 'operation', 'avg_response_ms', 'cpu_usage', 'memory_mb'],
            'storage': ['timestamp', 'total_size_gb', 'cleanup_potential_mb', 'health_score']
        }

    async def generate_dashboard(self) -> DashboardData:
        """
        Generate comprehensive analytics dashboard data.

        Returns:
            DashboardData: Complete dashboard information
        """
        try:
            # Run all analyses in parallel
            cache_analysis_task = self.cache_analyzer.analyze_cache()
            storage_analysis_task = self.storage_optimizer.analyze_storage()
            performance_analysis_task = self.performance_monitor.generate_performance_report()

            # Wait for all analyses to complete
            cache_analysis, storage_analysis, performance_analysis = await asyncio.gather(
                cache_analysis_task,
                storage_analysis_task,
                performance_analysis_task,
                return_exceptions=True
            )

            # Handle any exceptions in analysis
            if isinstance(cache_analysis, Exception):
                cache_analysis = self._get_empty_cache_analysis(str(cache_analysis))
            if isinstance(storage_analysis, Exception):
                storage_analysis = self._get_empty_storage_analysis(str(storage_analysis))
            if isinstance(performance_analysis, Exception):
                performance_analysis = self._get_empty_performance_analysis(str(performance_analysis))

            # Generate system summary
            system_summary = await self._generate_system_summary(
                cache_analysis, storage_analysis, performance_analysis
            )

            # Combine recommendations
            recommendations_summary = await self._combine_recommendations(
                cache_analysis, storage_analysis, performance_analysis
            )

            # Calculate health scores
            health_scores = {
                'cache_health': cache_analysis.health_score,
                'storage_health': storage_analysis.health_score,
                'performance_health': performance_analysis.system_health_score,
                'overall_health': (
                    cache_analysis.health_score +
                    storage_analysis.health_score +
                    performance_analysis.system_health_score
                ) / 3
            }

            return DashboardData(
                timestamp=datetime.now(),
                cache_analysis=cache_analysis,
                storage_optimization=storage_analysis,
                performance_monitoring=performance_analysis,
                system_summary=system_summary,
                recommendations_summary=recommendations_summary,
                health_scores=health_scores
            )

        except Exception as e:
            # Return minimal dashboard if generation fails
            return self._get_empty_dashboard(str(e))

    async def _generate_system_summary(
        self,
        cache_analysis: AnalysisReport,
        storage_analysis: OptimizationReport,
        performance_analysis: PerformanceReport
    ) -> Dict[str, Any]:
        """Generate high-level system summary."""
        return {
            'total_pages': cache_analysis.cache_stats.total_pages,
            'cache_size_mb': cache_analysis.cache_stats.total_size_bytes / (1024 * 1024),
            'storage_utilization_mb': storage_analysis.storage_stats.total_size_bytes / (1024 * 1024),
            'cleanup_potential_mb': storage_analysis.optimization_plan.total_cleanup_bytes / (1024 * 1024),
            'avg_search_time_ms': cache_analysis.performance_metrics.avg_search_time_ms,
            'system_cpu_usage': performance_analysis.system_health_score,  # Simplified
            'active_alerts': len(performance_analysis.bottlenecks),
            'last_sync': cache_analysis.cache_stats.last_sync.isoformat() if cache_analysis.cache_stats.last_sync else None,
            'notebooks_count': cache_analysis.cache_stats.notebooks_count,
            'sections_count': cache_analysis.cache_stats.sections_count
        }

    async def _combine_recommendations(
        self,
        cache_analysis: AnalysisReport,
        storage_analysis: OptimizationReport,
        performance_analysis: PerformanceReport
    ) -> List[str]:
        """Combine and prioritize recommendations from all analyses."""
        all_recommendations = []

        # Add prioritized cache recommendations
        cache_recs = cache_analysis.recommendations[:3]  # Top 3
        all_recommendations.extend([f"Cache: {rec}" for rec in cache_recs])

        # Add prioritized storage recommendations
        storage_recs = storage_analysis.recommendations[:3]  # Top 3
        all_recommendations.extend([f"Storage: {rec}" for rec in storage_recs])

        # Add prioritized performance recommendations
        perf_recs = performance_analysis.recommendations[:3]  # Top 3
        all_recommendations.extend([f"Performance: {rec}" for rec in perf_recs])

        # Add critical bottleneck recommendations
        critical_bottlenecks = [b for b in performance_analysis.bottlenecks if b.severity == "critical"]
        for bottleneck in critical_bottlenecks[:2]:  # Top 2 critical
            all_recommendations.append(f"CRITICAL: {bottleneck.description}")

        return all_recommendations[:10]  # Limit to top 10 overall

    async def export_report(
        self,
        dashboard_data: DashboardData,
        options: ExportOptions,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Export analytics report in specified format.

        Args:
            dashboard_data: Dashboard data to export
            options: Export configuration options
            output_path: Custom output path (optional)

        Returns:
            Path: Location of exported report file
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.reports_dir / f"analytics_report_{timestamp}.{options.format}"

        try:
            if options.format == 'json':
                await self._export_json(dashboard_data, output_path, options)
            elif options.format == 'csv':
                await self._export_csv(dashboard_data, output_path, options)
            elif options.format == 'html':
                await self._export_html(dashboard_data, output_path, options)
            else:
                raise ValueError(f"Unsupported export format: {options.format}")

            return output_path

        except Exception as e:
            # Create error report
            error_path = output_path.with_suffix('.error.txt')
            with open(error_path, 'w', encoding='utf-8') as f:
                f.write(f"Report export failed: {str(e)}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            return error_path

    async def _export_json(
        self,
        dashboard_data: DashboardData,
        output_path: Path,
        options: ExportOptions
    ) -> None:
        """Export dashboard data as JSON."""
        # Convert dataclasses to dictionary
        export_data = {
            'timestamp': dashboard_data.timestamp.isoformat(),
            'system_summary': dashboard_data.system_summary,
            'recommendations_summary': dashboard_data.recommendations_summary,
            'health_scores': dashboard_data.health_scores,
        }

        if options.include_raw_data:
            export_data.update({
                'cache_analysis': self._dataclass_to_dict(dashboard_data.cache_analysis),
                'storage_optimization': self._dataclass_to_dict(dashboard_data.storage_optimization),
                'performance_monitoring': self._dataclass_to_dict(dashboard_data.performance_monitoring)
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)

    async def _export_csv(
        self,
        dashboard_data: DashboardData,
        output_path: Path,
        options: ExportOptions
    ) -> None:
        """Export dashboard data as CSV (summary format)."""
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write summary section
            writer.writerow(['OneNote Copilot Analytics Summary'])
            writer.writerow(['Generated', dashboard_data.timestamp.isoformat()])
            writer.writerow([])

            # Health scores
            writer.writerow(['Health Scores'])
            writer.writerow(['Component', 'Score'])
            for component, score in dashboard_data.health_scores.items():
                writer.writerow([component.replace('_', ' ').title(), f"{score:.1f}"])
            writer.writerow([])

            # System summary
            writer.writerow(['System Summary'])
            writer.writerow(['Metric', 'Value'])
            for metric, value in dashboard_data.system_summary.items():
                if isinstance(value, float):
                    value = f"{value:.2f}"
                writer.writerow([metric.replace('_', ' ').title(), value])
            writer.writerow([])

            # Top recommendations
            writer.writerow(['Top Recommendations'])
            writer.writerow(['Priority', 'Recommendation'])
            for i, rec in enumerate(dashboard_data.recommendations_summary, 1):
                writer.writerow([i, rec])

    async def _export_html(
        self,
        dashboard_data: DashboardData,
        output_path: Path,
        options: ExportOptions
    ) -> None:
        """Export dashboard data as HTML report."""
        # Prepare template data
        template_data = {
            'timestamp': dashboard_data.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'dashboard': dashboard_data,
            'health_scores': dashboard_data.health_scores,
            'system_summary': dashboard_data.system_summary,
            'recommendations': dashboard_data.recommendations_summary,
            'include_charts': options.include_charts
        }

        # Generate charts data if requested
        if options.include_charts:
            template_data['charts_data'] = await self._generate_charts_data(dashboard_data)

        # Render template
        html_content = self._html_template.render(**template_data)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _dataclass_to_dict(self, obj: Any) -> Dict[str, Any]:
        """Convert dataclass to dictionary, handling nested structures."""
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for field, value in asdict(obj).items():
                if isinstance(value, datetime):
                    result[field] = value.isoformat()
                elif isinstance(value, list):
                    result[field] = [self._dataclass_to_dict(item) if hasattr(item, '__dataclass_fields__') else item for item in value]
                elif hasattr(value, '__dataclass_fields__'):
                    result[field] = self._dataclass_to_dict(value)
                else:
                    result[field] = value
            return result
        else:
            return obj

    async def _generate_charts_data(self, dashboard_data: DashboardData) -> Dict[str, Any]:
        """Generate data for charts and visualizations."""
        charts = {}

        # Health scores pie chart
        charts['health_scores'] = {
            'labels': list(dashboard_data.health_scores.keys()),
            'data': list(dashboard_data.health_scores.values()),
            'type': 'pie'
        }

        # System summary bar chart
        numeric_summary = {
            k: v for k, v in dashboard_data.system_summary.items()
            if isinstance(v, (int, float)) and k != 'last_sync'
        }
        charts['system_metrics'] = {
            'labels': list(numeric_summary.keys()),
            'data': list(numeric_summary.values()),
            'type': 'bar'
        }

        # Usage patterns (if available)
        if dashboard_data.cache_analysis.usage_patterns.most_searched_terms:
            terms_data = dashboard_data.cache_analysis.usage_patterns.most_searched_terms[:10]
            charts['search_terms'] = {
                'labels': [term for term, _ in terms_data],
                'data': [count for _, count in terms_data],
                'type': 'horizontal_bar'
            }

        return charts

    def _get_html_template(self) -> Template:
        """Get HTML template for report generation."""
        template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OneNote Copilot Analytics Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; color: #333; }
        .header { text-align: center; border-bottom: 2px solid #0078d4; padding-bottom: 20px; margin-bottom: 30px; }
        .health-scores { display: flex; justify-content: space-around; margin: 30px 0; }
        .health-card { text-align: center; padding: 20px; border-radius: 8px; min-width: 120px; }
        .health-excellent { background: #d4edda; color: #155724; }
        .health-good { background: #fff3cd; color: #856404; }
        .health-warning { background: #f8d7da; color: #721c24; }
        .section { margin: 30px 0; padding: 20px; border-left: 4px solid #0078d4; background: #f8f9fa; }
        .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .metric-item { background: white; padding: 15px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .recommendations { list-style: none; padding: 0; }
        .recommendations li { padding: 10px; margin: 5px 0; border-left: 3px solid #0078d4; background: white; }
        .footer { text-align: center; margin-top: 50px; color: #666; font-size: 0.9em; }
        h1, h2 { color: #0078d4; }
        .critical { color: #dc3545; font-weight: bold; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 OneNote Copilot Analytics Report</h1>
        <p>Generated: {{ timestamp }}</p>
    </div>

    <div class="health-scores">
        {% for name, score in health_scores.items() %}
        <div class="health-card {{ 'health-excellent' if score >= 80 else 'health-good' if score >= 60 else 'health-warning' }}">
            <h3>{{ name.replace('_', ' ').title() }}</h3>
            <div style="font-size: 2em; font-weight: bold;">{{ "%.0f"|format(score) }}%</div>
        </div>
        {% endfor %}
    </div>

    <div class="section">
        <h2>🎯 System Summary</h2>
        <div class="metric-grid">
            {% for metric, value in system_summary.items() %}
            <div class="metric-item">
                <strong>{{ metric.replace('_', ' ').title() }}:</strong>
                {% if value is number %}
                    {{ "%.2f"|format(value) }}
                {% else %}
                    {{ value or 'N/A' }}
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="section">
        <h2>💡 Top Recommendations</h2>
        <ul class="recommendations">
            {% for recommendation in recommendations %}
            <li class="{{ 'critical' if 'CRITICAL' in recommendation }}">
                {{ recommendation }}
            </li>
            {% endfor %}
        </ul>
    </div>

    <div class="section">
        <h2>📈 Cache Performance</h2>
        <div class="metric-grid">
            <div class="metric-item">
                <strong>Total Pages:</strong> {{ dashboard.cache_analysis.cache_stats.total_pages }}
            </div>
            <div class="metric-item">
                <strong>Avg Search Time:</strong> {{ "%.0f"|format(dashboard.cache_analysis.performance_metrics.avg_search_time_ms) }}ms
            </div>
            <div class="metric-item">
                <strong>Cache Hit Rate:</strong> {{ "%.1f"|format(dashboard.cache_analysis.performance_metrics.cache_hit_rate) }}%
            </div>
            <div class="metric-item">
                <strong>Storage Efficiency:</strong> {{ "%.1f"|format(dashboard.cache_analysis.performance_metrics.storage_efficiency) }}%
            </div>
        </div>
    </div>

    <div class="section">
        <h2>💾 Storage Analysis</h2>
        <div class="metric-grid">
            <div class="metric-item">
                <strong>Total Size:</strong> {{ "%.1f"|format(dashboard.storage_optimization.storage_stats.total_size_bytes / 1048576) }} MB
            </div>
            <div class="metric-item">
                <strong>Cleanup Potential:</strong> {{ "%.1f"|format(dashboard.storage_optimization.optimization_plan.total_cleanup_bytes / 1048576) }} MB
            </div>
            <div class="metric-item">
                <strong>Available Space:</strong> {{ "%.1f"|format(dashboard.storage_optimization.storage_stats.available_space_bytes / 1073741824) }} GB
            </div>
            <div class="metric-item">
                <strong>Risk Assessment:</strong> {{ dashboard.storage_optimization.optimization_plan.risk_assessment }}
            </div>
        </div>
    </div>

    {% if dashboard.performance_monitoring.bottlenecks %}
    <div class="section">
        <h2>⚠️ Performance Bottlenecks</h2>
        {% for bottleneck in dashboard.performance_monitoring.bottlenecks %}
        <div class="metric-item {{ 'critical' if bottleneck.severity == 'critical' }}">
            <strong>{{ bottleneck.bottleneck_type.title() }} ({{ bottleneck.severity.title() }}):</strong>
            {{ bottleneck.description }}
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <div class="footer">
        <p>OneNote Copilot Analytics • Generated automatically •
        System Health: {{ "%.0f"|format(health_scores.overall_health) }}%</p>
    </div>
</body>
</html>
        """
        return Template(template_str)

    def _get_empty_cache_analysis(self, error: str) -> AnalysisReport:
        """Create empty cache analysis for error cases."""
        from .cache_analyzer import (CacheStats, PerformanceMetrics,
                                     UsagePattern)
        return AnalysisReport(
            timestamp=datetime.now(),
            cache_stats=CacheStats(0, 0, 0.0, 0, 0, None, None, None),
            usage_patterns=UsagePattern([], [], {}, {}, 0.0, []),
            performance_metrics=PerformanceMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            recommendations=[f"Cache analysis failed: {error}"],
            health_score=0.0
        )

    def _get_empty_storage_analysis(self, error: str) -> OptimizationReport:
        """Create empty storage analysis for error cases."""
        from .storage_optimizer import OptimizationPlan, StorageStats
        return OptimizationReport(
            timestamp=datetime.now(),
            storage_stats=StorageStats(0, 0, 0, 0, 0, 0.0),
            optimization_plan=OptimizationPlan(0, [], [], [], 0, "Analysis failed"),
            recommendations=[f"Storage analysis failed: {error}"],
            health_score=0.0
        )

    def _get_empty_performance_analysis(self, error: str) -> PerformanceReport:
        """Create empty performance analysis for error cases."""
        return PerformanceReport(
            timestamp=datetime.now(),
            system_health_score=0.0,
            performance_trends=[],
            bottlenecks=[],
            alerting_summary={},
            recommendations=[f"Performance analysis failed: {error}"]
        )

    def _get_empty_dashboard(self, error: str) -> DashboardData:
        """Create empty dashboard for error cases."""
        return DashboardData(
            timestamp=datetime.now(),
            cache_analysis=self._get_empty_cache_analysis(error),
            storage_optimization=self._get_empty_storage_analysis(error),
            performance_monitoring=self._get_empty_performance_analysis(error),
            system_summary={'error': error},
            recommendations_summary=[f"Dashboard generation failed: {error}"],
            health_scores={'overall_health': 0.0}
        )

    async def schedule_periodic_reports(
        self,
        frequency_hours: int = 24,
        export_formats: List[str] = None
    ) -> None:
        """
        Schedule periodic report generation.

        Args:
            frequency_hours: How often to generate reports
            export_formats: List of formats to generate ['json', 'html']
        """
        if export_formats is None:
            export_formats = ['json', 'html']

        while True:
            try:
                # Generate dashboard
                dashboard_data = await self.generate_dashboard()

                # Export in requested formats
                for format_type in export_formats:
                    options = ExportOptions(
                        format=format_type,
                        include_charts=True,
                        include_raw_data=(format_type == 'json'),
                        time_range_hours=frequency_hours
                    )

                    await self.export_report(dashboard_data, options)

                # Wait for next interval
                await asyncio.sleep(frequency_hours * 3600)

            except Exception as e:
                # Log error but continue scheduling
                print(f"Periodic report generation failed: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour
