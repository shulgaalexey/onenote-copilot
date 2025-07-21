"""
Tests for Report Generator System.

Comprehensive test suite covering dashboard generation, report export,
and analytics integration functionality.
"""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.storage.cache_analyzer import (AnalysisReport, CacheStats,
                                        PerformanceMetrics, UsagePattern)
from src.storage.performance_monitor import PerformanceReport
from src.storage.report_generator import (DashboardData, ExportOptions,
                                          ReportGenerator)
from src.storage.storage_optimizer import (OptimizationPlan,
                                           OptimizationReport, StorageStats)


class TestReportGenerator:
    """Test cases for ReportGenerator functionality."""

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
    def generator(self, temp_cache_dir, mock_settings):
        """Create ReportGenerator instance with mocked settings."""
        with patch('src.storage.report_generator.get_settings', return_value=mock_settings):
            generator = ReportGenerator()
            generator.cache_dir = temp_cache_dir
            generator.reports_dir = temp_cache_dir / "reports"
            generator.reports_dir.mkdir(exist_ok=True)
            return generator

    @pytest.fixture
    def sample_cache_analysis(self):
        """Create sample cache analysis report."""
        cache_stats = CacheStats(
            total_pages=150,
            total_size_bytes=75 * 1024 * 1024,  # 75MB
            avg_page_size_bytes=500000,  # 500KB
            notebooks_count=8,
            sections_count=20,
            oldest_content=datetime.now() - timedelta(days=180),
            newest_content=datetime.now() - timedelta(days=1),
            last_sync=datetime.now() - timedelta(hours=6)
        )

        usage_patterns = UsagePattern(
            most_searched_terms=[("meeting notes", 15), ("project plan", 12), ("tasks", 8)],
            popular_pages=[("Daily Standup", 25), ("Sprint Planning", 18), ("Retrospective", 12)],
            search_frequency_by_hour={9: 5, 10: 12, 11: 8, 14: 15, 15: 10},
            notebook_access_frequency={"Work": 45, "Personal": 20, "Archive": 5},
            avg_searches_per_day=25.5,
            peak_usage_hours=[10, 14, 15]
        )

        performance_metrics = PerformanceMetrics(
            avg_search_time_ms=180.5,
            fastest_search_ms=45.0,
            slowest_search_ms=850.0,
            cache_hit_rate=97.8,
            index_health_score=88.5,
            storage_efficiency=92.0
        )

        return AnalysisReport(
            timestamp=datetime.now(),
            cache_stats=cache_stats,
            usage_patterns=usage_patterns,
            performance_metrics=performance_metrics,
            recommendations=[
                "Cache performance is excellent",
                "Consider archiving content older than 6 months",
                "Peak usage hours are well distributed"
            ],
            health_score=87.5
        )

    @pytest.fixture
    def sample_storage_analysis(self):
        """Create sample storage optimization report."""
        storage_stats = StorageStats(
            total_size_bytes=120 * 1024 * 1024,  # 120MB
            database_size_bytes=75 * 1024 * 1024,  # 75MB
            assets_size_bytes=40 * 1024 * 1024,  # 40MB
            temp_size_bytes=5 * 1024 * 1024,  # 5MB
            available_space_bytes=50 * 1024**3,  # 50GB
            utilization_percentage=0.24
        )

        optimization_plan = OptimizationPlan(
            total_cleanup_bytes=15 * 1024 * 1024,  # 15MB
            cleanup_candidates=[],
            compression_opportunities=["Database compression could save ~20% of 75MB"],
            archive_suggestions=["Archive content older than 6 months (25MB)"],
            estimated_space_saved_bytes=25 * 1024 * 1024,  # 25MB
            risk_assessment="LOW RISK - Only temporary files and old content targeted"
        )

        return OptimizationReport(
            timestamp=datetime.now(),
            storage_stats=storage_stats,
            optimization_plan=optimization_plan,
            recommendations=[
                "Storage utilization is healthy",
                "Consider cleanup of temporary files (5MB)",
                "Database compression could save ~15MB"
            ],
            health_score=91.2
        )

    @pytest.fixture
    def sample_performance_analysis(self):
        """Create sample performance monitoring report."""
        return PerformanceReport(
            timestamp=datetime.now(),
            system_health_score=85.5,
            performance_trends=[],
            bottlenecks=[],
            alerting_summary={"total_alerts": 2, "medium_slow_operation": 1, "low_disk_space": 1},
            recommendations=[
                "System performance is good",
                "Monitor disk space usage",
                "Consider optimizing slow operations"
            ]
        )

    @pytest.fixture
    def sample_dashboard_data(self, sample_cache_analysis, sample_storage_analysis, sample_performance_analysis):
        """Create complete sample dashboard data."""
        return DashboardData(
            timestamp=datetime.now(),
            cache_analysis=sample_cache_analysis,
            storage_optimization=sample_storage_analysis,
            performance_monitoring=sample_performance_analysis,
            system_summary={
                'total_pages': 150,
                'cache_size_mb': 75.0,
                'storage_utilization_mb': 120.0,
                'cleanup_potential_mb': 15.0,
                'avg_search_time_ms': 180.5,
                'system_cpu_usage': 85.5,
                'active_alerts': 0,
                'last_sync': datetime.now().isoformat(),
                'notebooks_count': 8,
                'sections_count': 20
            },
            recommendations_summary=[
                "Cache: Cache performance is excellent",
                "Storage: Storage utilization is healthy",
                "Performance: System performance is good"
            ],
            health_scores={
                'cache_health': 87.5,
                'storage_health': 91.2,
                'performance_health': 85.5,
                'overall_health': 88.1
            }
        )

    def test_report_generator_initialization(self, generator):
        """Test ReportGenerator initialization."""
        assert generator.cache_dir is not None
        assert generator.reports_dir.exists()
        assert generator.cache_analyzer is not None
        assert generator.storage_optimizer is not None
        assert generator.performance_monitor is not None
        assert generator._html_template is not None
        assert isinstance(generator._csv_headers, dict)

    @pytest.mark.asyncio
    async def test_generate_system_summary(self, generator, sample_cache_analysis, sample_storage_analysis, sample_performance_analysis):
        """Test system summary generation."""
        summary = await generator._generate_system_summary(
            sample_cache_analysis, sample_storage_analysis, sample_performance_analysis
        )

        assert isinstance(summary, dict)
        assert summary['total_pages'] == 150
        assert summary['cache_size_mb'] == 75.0
        assert summary['avg_search_time_ms'] == 180.5
        assert summary['notebooks_count'] == 8
        assert summary['sections_count'] == 20
        assert 'last_sync' in summary

    @pytest.mark.asyncio
    async def test_combine_recommendations(self, generator, sample_cache_analysis, sample_storage_analysis, sample_performance_analysis):
        """Test recommendation combination and prioritization."""
        recommendations = await generator._combine_recommendations(
            sample_cache_analysis, sample_storage_analysis, sample_performance_analysis
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) <= 10  # Should limit to top 10

        # Should include recommendations from all components
        cache_recs = [r for r in recommendations if r.startswith("Cache:")]
        storage_recs = [r for r in recommendations if r.startswith("Storage:")]
        perf_recs = [r for r in recommendations if r.startswith("Performance:")]

        assert len(cache_recs) > 0
        assert len(storage_recs) > 0
        assert len(perf_recs) > 0

    @pytest.mark.asyncio
    async def test_generate_dashboard_success(self, generator):
        """Test successful dashboard generation."""
        # Mock the component analyzers
        generator.cache_analyzer.analyze_cache = AsyncMock(return_value=Mock(
            health_score=85.0,
            recommendations=["Test cache recommendation"],
            cache_stats=Mock(),
            usage_patterns=Mock(),
            performance_metrics=Mock()
        ))

        generator.storage_optimizer.analyze_storage = AsyncMock(return_value=Mock(
            health_score=90.0,
            recommendations=["Test storage recommendation"],
            storage_stats=Mock(),
            optimization_plan=Mock()
        ))

        generator.performance_monitor.generate_performance_report = AsyncMock(return_value=Mock(
            system_health_score=88.0,
            recommendations=["Test performance recommendation"],
            performance_trends=[],
            bottlenecks=[],
            alerting_summary={}
        ))

        dashboard = await generator.generate_dashboard()

        assert isinstance(dashboard, DashboardData)
        assert dashboard.timestamp is not None
        assert len(dashboard.health_scores) == 4  # cache, storage, performance, overall
        assert 'overall_health' in dashboard.health_scores
        assert len(dashboard.recommendations_summary) > 0

    @pytest.mark.asyncio
    async def test_generate_dashboard_with_errors(self, generator):
        """Test dashboard generation with component errors."""
        # Mock analyzers to raise exceptions
        generator.cache_analyzer.analyze_cache = AsyncMock(side_effect=Exception("Cache error"))
        generator.storage_optimizer.analyze_storage = AsyncMock(side_effect=Exception("Storage error"))
        generator.performance_monitor.generate_performance_report = AsyncMock(side_effect=Exception("Performance error"))

        dashboard = await generator.generate_dashboard()

        # Should return error dashboard instead of raising
        assert isinstance(dashboard, DashboardData)
        assert dashboard.health_scores['overall_health'] == 0.0
        assert any("failed" in rec.lower() for rec in dashboard.recommendations_summary)

    @pytest.mark.asyncio
    async def test_export_json_format(self, generator, sample_dashboard_data):
        """Test JSON export functionality."""
        output_path = generator.reports_dir / "test_report.json"
        options = ExportOptions(format='json', include_raw_data=True)

        result_path = await generator.export_report(sample_dashboard_data, options, output_path)

        assert result_path == output_path
        assert output_path.exists()

        # Verify JSON content
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert 'timestamp' in data
            assert 'system_summary' in data
            assert 'health_scores' in data
            assert 'cache_analysis' in data  # Should include raw data

    @pytest.mark.asyncio
    async def test_export_json_format_minimal(self, generator, sample_dashboard_data):
        """Test minimal JSON export without raw data."""
        output_path = generator.reports_dir / "test_minimal.json"
        options = ExportOptions(format='json', include_raw_data=False)

        result_path = await generator.export_report(sample_dashboard_data, options, output_path)

        assert output_path.exists()

        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert 'system_summary' in data
            assert 'health_scores' in data
            assert 'cache_analysis' not in data  # Should not include raw data

    @pytest.mark.asyncio
    async def test_export_csv_format(self, generator, sample_dashboard_data):
        """Test CSV export functionality."""
        output_path = generator.reports_dir / "test_report.csv"
        options = ExportOptions(format='csv')

        result_path = await generator.export_report(sample_dashboard_data, options, output_path)

        assert output_path.exists()

        # Verify CSV content structure
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "OneNote Copilot Analytics Summary" in content
            assert "Health Scores" in content
            assert "System Summary" in content
            assert "Top Recommendations" in content

    @pytest.mark.asyncio
    async def test_export_html_format(self, generator, sample_dashboard_data):
        """Test HTML export functionality."""
        output_path = generator.reports_dir / "test_report.html"
        options = ExportOptions(format='html', include_charts=True)

        result_path = await generator.export_report(sample_dashboard_data, options, output_path)

        assert output_path.exists()

        # Verify HTML content structure
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "<!DOCTYPE html>" in content
            assert "OneNote Copilot Analytics Report" in content
            assert "System Summary" in content
            assert "health-card" in content  # CSS class for health cards

    @pytest.mark.asyncio
    async def test_export_unsupported_format(self, generator, sample_dashboard_data):
        """Test export with unsupported format."""
        output_path = generator.reports_dir / "test_report.xyz"
        options = ExportOptions(format='xyz')  # Unsupported format

        result_path = await generator.export_report(sample_dashboard_data, options, output_path)

        # Should create error file instead
        assert result_path.suffix == '.error.txt'
        assert result_path.exists()

        with open(result_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "export failed" in content.lower()

    @pytest.mark.asyncio
    async def test_generate_charts_data(self, generator, sample_dashboard_data):
        """Test chart data generation for visualizations."""
        charts_data = await generator._generate_charts_data(sample_dashboard_data)

        assert isinstance(charts_data, dict)
        assert 'health_scores' in charts_data
        assert 'system_metrics' in charts_data

        # Check health scores chart
        health_chart = charts_data['health_scores']
        assert health_chart['type'] == 'pie'
        assert len(health_chart['labels']) == len(health_chart['data'])

        # Check system metrics chart
        metrics_chart = charts_data['system_metrics']
        assert metrics_chart['type'] == 'bar'
        assert len(metrics_chart['labels']) == len(metrics_chart['data'])

        # Should include search terms chart if data available
        if 'search_terms' in charts_data:
            search_chart = charts_data['search_terms']
            assert search_chart['type'] == 'horizontal_bar'
            assert len(search_chart['labels']) <= 10  # Limited to top 10

    def test_dataclass_to_dict_conversion(self, generator):
        """Test dataclass to dictionary conversion."""
        # Create a simple dataclass for testing
        from dataclasses import dataclass

        @dataclass
        class TestData:
            name: str
            value: int
            timestamp: datetime

        test_obj = TestData("test", 42, datetime.now())
        result = generator._dataclass_to_dict(test_obj)

        assert isinstance(result, dict)
        assert result['name'] == "test"
        assert result['value'] == 42
        assert isinstance(result['timestamp'], str)  # Should be converted to ISO format

    def test_html_template_rendering(self, generator, sample_dashboard_data):
        """Test HTML template rendering."""
        template_data = {
            'timestamp': sample_dashboard_data.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'dashboard': sample_dashboard_data,
            'health_scores': sample_dashboard_data.health_scores,
            'system_summary': sample_dashboard_data.system_summary,
            'recommendations': sample_dashboard_data.recommendations_summary,
            'include_charts': False
        }

        html_content = generator._html_template.render(**template_data)

        assert "OneNote Copilot Analytics Report" in html_content
        assert str(sample_dashboard_data.health_scores['overall_health']) in html_content
        assert "System Summary" in html_content
        assert "Top Recommendations" in html_content

    def test_export_options_creation(self, generator):
        """Test ExportOptions dataclass creation."""
        options = ExportOptions(
            format='html',
            include_charts=True,
            include_raw_data=False,
            time_range_hours=48,
            template_name='custom'
        )

        assert options.format == 'html'
        assert options.include_charts is True
        assert options.include_raw_data is False
        assert options.time_range_hours == 48
        assert options.template_name == 'custom'

    def test_dashboard_data_creation(self, sample_cache_analysis, sample_storage_analysis, sample_performance_analysis):
        """Test DashboardData dataclass creation."""
        timestamp = datetime.now()
        system_summary = {'test_metric': 100}
        recommendations = ['Test recommendation']
        health_scores = {'overall_health': 85.0}

        dashboard = DashboardData(
            timestamp=timestamp,
            cache_analysis=sample_cache_analysis,
            storage_optimization=sample_storage_analysis,
            performance_monitoring=sample_performance_analysis,
            system_summary=system_summary,
            recommendations_summary=recommendations,
            health_scores=health_scores
        )

        assert dashboard.timestamp == timestamp
        assert dashboard.system_summary == system_summary
        assert dashboard.recommendations_summary == recommendations
        assert dashboard.health_scores == health_scores

    def test_empty_dashboard_creation(self, generator):
        """Test creation of empty dashboard for error cases."""
        error_msg = "Test error"
        empty_dashboard = generator._get_empty_dashboard(error_msg)

        assert isinstance(empty_dashboard, DashboardData)
        assert empty_dashboard.health_scores['overall_health'] == 0.0
        assert error_msg in empty_dashboard.recommendations_summary[0]
        assert error_msg in empty_dashboard.system_summary['error']

    @pytest.mark.asyncio
    async def test_default_output_path_generation(self, generator, sample_dashboard_data):
        """Test automatic output path generation when none provided."""
        options = ExportOptions(format='json')

        result_path = await generator.export_report(sample_dashboard_data, options)

        # Should create file in reports directory with timestamp
        assert result_path.parent == generator.reports_dir
        assert result_path.suffix == '.json'
        assert 'analytics_report_' in result_path.name
        assert result_path.exists()

    @pytest.mark.asyncio
    async def test_schedule_periodic_reports_single_iteration(self, generator):
        """Test periodic report scheduling (single iteration for testing)."""
        # Mock the generator methods to avoid actual report generation
        generator.generate_dashboard = AsyncMock(return_value=Mock())
        generator.export_report = AsyncMock(return_value=Path("test_report.json"))

        # Test a single iteration with very short frequency
        import asyncio

        # Create a task that we can cancel after a short time
        task = asyncio.create_task(generator.schedule_periodic_reports(
            frequency_hours=0.001,  # Very short for testing
            export_formats=['json']
        ))

        # Let it run briefly then cancel
        await asyncio.sleep(0.1)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify it attempted to generate reports
        assert generator.generate_dashboard.called
        assert generator.export_report.called

    def test_csv_headers_configuration(self, generator):
        """Test CSV headers configuration."""
        assert 'cache_stats' in generator._csv_headers
        assert 'performance' in generator._csv_headers
        assert 'storage' in generator._csv_headers

        # Check that headers contain expected fields
        cache_headers = generator._csv_headers['cache_stats']
        assert 'timestamp' in cache_headers
        assert 'total_pages' in cache_headers
        assert 'health_score' in cache_headers
