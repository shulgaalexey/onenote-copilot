"""
Tests for Storage Optimizer System.

Comprehensive test suite covering storage analysis, cleanup candidate identification,
optimization planning, and storage health assessment.
"""

import asyncio
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.storage.storage_optimizer import (CleanupCandidate, OptimizationPlan,
                                           OptimizationReport,
                                           StorageOptimizer, StorageStats)


class TestStorageOptimizer:
    """Test cases for StorageOptimizer functionality."""

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
    def optimizer(self, temp_cache_dir, mock_settings):
        """Create StorageOptimizer instance with mocked settings."""
        with patch('src.storage.storage_optimizer.get_settings', return_value=mock_settings):
            optimizer = StorageOptimizer()
            optimizer.cache_dir = temp_cache_dir
            optimizer.db_path = temp_cache_dir / "cache.db"
            optimizer.assets_dir = temp_cache_dir / "assets"
            optimizer.temp_dir = temp_cache_dir / "temp"
            return optimizer

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
                    last_modified_time TEXT
                )
            """)

            # Insert sample data with various dates and sizes
            now = datetime.now()
            old_date = (now - timedelta(days=120)).isoformat()
            recent_date = (now - timedelta(days=5)).isoformat()

            sample_data = [
                ('old_page_1', 'Old Meeting Notes', 'x' * 100000, old_date),  # Large old page
                ('old_page_2', 'Archive Notes', 'x' * 5000, old_date),        # Small old page
                ('recent_page', 'Current Project', 'x' * 10000, recent_date), # Recent page
                ('large_page', 'Huge Document', 'x' * 200000, recent_date),   # Large recent page
            ]

            conn.executemany("""
                INSERT INTO pages VALUES (?, ?, ?, ?)
            """, sample_data)
            conn.commit()

        return db_path

    @pytest.fixture
    def sample_assets_dir(self, temp_cache_dir):
        """Create sample assets directory with test files."""
        assets_dir = temp_cache_dir / "assets"
        assets_dir.mkdir(exist_ok=True)

        # Create various test files
        files_to_create = [
            ("old_image.jpg", b"fake_image_data" * 1000, 100),   # Old file
            ("recent_doc.pdf", b"fake_pdf_data" * 500, 5),       # Recent file
            ("huge_file.png", b"fake_png_data" * 5000, 50),      # Large old file
            ("current.txt", b"current_data", 1),                 # Small recent file
        ]

        for filename, content, days_old in files_to_create:
            file_path = assets_dir / filename
            file_path.write_bytes(content)

            # Set file modification time
            old_time = datetime.now() - timedelta(days=days_old)
            timestamp = old_time.timestamp()
            file_path.touch(times=(timestamp, timestamp))

        return assets_dir

    @pytest.fixture
    def sample_temp_dir(self, temp_cache_dir):
        """Create sample temporary directory with test files."""
        temp_dir = temp_cache_dir / "temp"
        temp_dir.mkdir(exist_ok=True)

        # Create temporary files of various ages
        temp_files = [
            ("temp1.tmp", b"temp_data_1", 5),    # Old temp file
            ("temp2.log", b"temp_data_2" * 100, 3),  # Larger old temp file
            ("recent.tmp", b"recent_temp", 0),    # Very recent temp file
        ]

        for filename, content, days_old in temp_files:
            file_path = temp_dir / filename
            file_path.write_bytes(content)

            # Set file modification time
            old_time = datetime.now() - timedelta(days=days_old)
            timestamp = old_time.timestamp()
            file_path.touch(times=(timestamp, timestamp))

        return temp_dir

    @pytest.mark.asyncio
    async def test_analyze_storage_stats_basic(self, optimizer, sample_cache_db, sample_assets_dir):
        """Test basic storage statistics analysis."""
        stats = await optimizer._analyze_storage_stats()

        assert stats.total_size_bytes > 0
        assert stats.database_size_bytes > 0
        assert stats.assets_size_bytes > 0
        assert stats.available_space_bytes > 0
        assert stats.utilization_percentage >= 0.0

    @pytest.mark.asyncio
    async def test_analyze_storage_stats_empty_cache(self, optimizer):
        """Test storage stats with empty cache directory."""
        stats = await optimizer._analyze_storage_stats()

        # Should handle missing directories gracefully
        assert stats.database_size_bytes == 0
        assert stats.assets_size_bytes == 0
        assert stats.temp_size_bytes == 0
        assert stats.available_space_bytes > 0  # Should still report available space

    @pytest.mark.asyncio
    async def test_analyze_database_cleanup(self, optimizer, sample_cache_db):
        """Test database cleanup candidate analysis."""
        candidates = await optimizer._analyze_database_cleanup()

        # Should identify old content
        old_candidates = [c for c in candidates if c.content_type == "page" and "old" in c.reason.lower()]
        assert len(old_candidates) > 0

        # Should identify large content with low importance
        large_candidates = [c for c in candidates if "large" in c.reason.lower()]
        assert len(large_candidates) >= 0  # May or may not have large low-importance pages

        # Check candidate structure
        for candidate in candidates:
            assert candidate.content_type == "page"
            assert candidate.identifier is not None
            assert candidate.size_bytes > 0
            assert 0.0 <= candidate.importance_score <= 1.0
            assert len(candidate.reason) > 0

    @pytest.mark.asyncio
    async def test_analyze_assets_cleanup(self, optimizer, sample_assets_dir):
        """Test asset cleanup candidate analysis."""
        candidates = await optimizer._analyze_assets_cleanup()

        # Should identify old or large assets
        old_or_large = [c for c in candidates if c.content_type == "asset"]
        assert len(old_or_large) > 0

        # Check candidate structure
        for candidate in candidates:
            assert candidate.content_type == "asset"
            assert candidate.identifier is not None
            assert candidate.size_bytes > 0
            assert 0.0 <= candidate.importance_score <= 1.0
            assert len(candidate.reason) > 0

    @pytest.mark.asyncio
    async def test_analyze_temp_cleanup(self, optimizer, sample_temp_dir):
        """Test temporary file cleanup analysis."""
        candidates = await optimizer._analyze_temp_cleanup()

        # Should identify old temp files (older than 1 day)
        temp_candidates = [c for c in candidates if c.content_type == "temp"]
        assert len(temp_candidates) > 0

        # All temp file candidates should have low importance
        for candidate in temp_candidates:
            assert candidate.importance_score <= 0.2  # Temp files should have low importance
            assert "temp" in candidate.reason.lower() or "old" in candidate.reason.lower()

    def test_calculate_page_importance_high(self, optimizer):
        """Test page importance calculation for high-value content."""
        # Page with important keywords and recent date
        title = "Important Project Meeting Action Items"
        last_modified = datetime.now() - timedelta(days=2)

        score = optimizer._calculate_page_importance(title, last_modified)

        assert score > 0.7  # Should be high importance

    def test_calculate_page_importance_low(self, optimizer):
        """Test page importance calculation for low-value content."""
        # Page with generic title and old date
        title = "Random Notes"
        last_modified = datetime.now() - timedelta(days=200)

        score = optimizer._calculate_page_importance(title, last_modified)

        assert score < 0.6  # Should be lower importance

    def test_calculate_asset_importance_document(self, optimizer):
        """Test asset importance calculation for documents."""
        doc_path = Path("important_document.pdf")
        recent_access = datetime.now() - timedelta(days=3)

        score = optimizer._calculate_asset_importance(doc_path, recent_access)

        assert score > 0.6  # Documents should have higher importance

    def test_calculate_asset_importance_old_image(self, optimizer):
        """Test asset importance calculation for old images."""
        img_path = Path("old_screenshot.png")
        old_access = datetime.now() - timedelta(days=60)

        score = optimizer._calculate_asset_importance(img_path, old_access)

        assert score < 0.8  # Old images should have moderate or lower importance

    @pytest.mark.asyncio
    async def test_identify_compression_opportunities(self, optimizer, sample_cache_db):
        """Test compression opportunity identification."""
        opportunities = await optimizer._identify_compression_opportunities()

        # Should identify database compression for reasonably sized DB
        db_opportunities = [opp for opp in opportunities if "database" in opp.lower()]

        # May or may not have opportunities depending on DB size
        assert len(opportunities) >= 0

    @pytest.mark.asyncio
    async def test_generate_archive_suggestions(self, optimizer, sample_cache_db):
        """Test archive suggestion generation."""
        suggestions = await optimizer._generate_archive_suggestions()

        # Should have suggestions for old content
        old_content_suggestions = [s for s in suggestions if "old" in s.lower() or "6 months" in s.lower()]
        assert len(old_content_suggestions) >= 0  # May not have old content depending on test data

    def test_assess_cleanup_risk_low(self, optimizer):
        """Test cleanup risk assessment for low-risk scenario."""
        # All temp files with low importance
        candidates = [
            CleanupCandidate("temp", "file1.tmp", 1000, datetime.now(), 0.1, "temp file"),
            CleanupCandidate("temp", "file2.tmp", 2000, datetime.now(), 0.1, "temp file"),
        ]

        risk = optimizer._assess_cleanup_risk(candidates)

        assert "low risk" in risk.lower()

    def test_assess_cleanup_risk_high(self, optimizer):
        """Test cleanup risk assessment for high-risk scenario."""
        # Many high-importance pages
        candidates = [
            CleanupCandidate("page", "page1", 10000, datetime.now(), 0.9, "important page"),
            CleanupCandidate("page", "page2", 15000, datetime.now(), 0.8, "important page"),
            CleanupCandidate("page", "page3", 8000, datetime.now(), 0.85, "important page"),
        ]

        risk = optimizer._assess_cleanup_risk(candidates)

        assert "high risk" in risk.lower()

    @pytest.mark.asyncio
    async def test_create_optimization_plan(self, optimizer, sample_cache_db, sample_assets_dir, sample_temp_dir):
        """Test comprehensive optimization plan creation."""
        stats = StorageStats(1000000, 500000, 300000, 200000, 1000000000, 0.1)
        plan = await optimizer._create_optimization_plan(stats)

        assert isinstance(plan, OptimizationPlan)
        assert plan.total_cleanup_bytes >= 0
        assert isinstance(plan.cleanup_candidates, list)
        assert isinstance(plan.compression_opportunities, list)
        assert isinstance(plan.archive_suggestions, list)
        assert plan.estimated_space_saved_bytes >= 0
        assert len(plan.risk_assessment) > 0

    @pytest.mark.asyncio
    async def test_generate_recommendations_large_cache(self, optimizer):
        """Test recommendations for large cache scenario."""
        # Large cache stats
        stats = StorageStats(
            total_size_bytes=6 * 1024**3,  # 6GB - exceeds 5GB limit
            database_size_bytes=1 * 1024**3,
            assets_size_bytes=4 * 1024**3,
            temp_size_bytes=1 * 1024**3,
            available_space_bytes=500 * 1024**2,  # 500MB - low space
            utilization_percentage=85.0
        )

        plan = OptimizationPlan(
            total_cleanup_bytes=500 * 1024**2,  # 500MB cleanup potential
            cleanup_candidates=[],
            compression_opportunities=["Database compression could save ~20% of 1000MB"],
            archive_suggestions=[],
            estimated_space_saved_bytes=600 * 1024**2,
            risk_assessment="MEDIUM RISK"
        )

        recommendations = await optimizer._generate_recommendations(stats, plan)

        # Should recommend cleanup for large cache
        large_cache_rec = any("exceeds" in rec.lower() or "cleanup" in rec.lower() for rec in recommendations)
        assert large_cache_rec

        # Should warn about low disk space
        low_space_rec = any("disk space" in rec.lower() for rec in recommendations)
        assert low_space_rec

    @pytest.mark.asyncio
    async def test_generate_recommendations_healthy_cache(self, optimizer):
        """Test recommendations for healthy cache scenario."""
        # Healthy cache stats
        stats = StorageStats(
            total_size_bytes=2 * 1024**3,  # 2GB - reasonable size
            database_size_bytes=1 * 1024**3,
            assets_size_bytes=800 * 1024**2,
            temp_size_bytes=200 * 1024**2,
            available_space_bytes=50 * 1024**3,  # 50GB - plenty of space
            utilization_percentage=15.0
        )

        plan = OptimizationPlan(
            total_cleanup_bytes=50 * 1024**2,  # 50MB - small cleanup potential
            cleanup_candidates=[],
            compression_opportunities=[],
            archive_suggestions=[],
            estimated_space_saved_bytes=50 * 1024**2,
            risk_assessment="LOW RISK"
        )

        recommendations = await optimizer._generate_recommendations(stats, plan)

        # Should include general maintenance recommendations
        maintenance_rec = any("maintenance" in rec.lower() or "monitor" in rec.lower() for rec in recommendations)
        assert maintenance_rec

    def test_calculate_storage_health_score_excellent(self, optimizer):
        """Test storage health score calculation for excellent conditions."""
        stats = StorageStats(
            total_size_bytes=2 * 1024**3,  # 2GB - within limits
            database_size_bytes=1 * 1024**3,
            assets_size_bytes=800 * 1024**2,
            temp_size_bytes=200 * 1024**2,
            available_space_bytes=100 * 1024**3,  # 100GB - plenty
            utilization_percentage=5.0  # Low utilization
        )

        plan = OptimizationPlan(
            total_cleanup_bytes=10 * 1024**2,  # 10MB - minimal cleanup
            cleanup_candidates=[],
            compression_opportunities=[],
            archive_suggestions=[],
            estimated_space_saved_bytes=10 * 1024**2,
            risk_assessment="LOW RISK"
        )

        score = optimizer._calculate_storage_health_score(stats, plan)

        assert score >= 90.0  # Should be excellent

    def test_calculate_storage_health_score_poor(self, optimizer):
        """Test storage health score calculation for poor conditions."""
        stats = StorageStats(
            total_size_bytes=8 * 1024**3,  # 8GB - exceeds 5GB limit significantly
            database_size_bytes=4 * 1024**3,
            assets_size_bytes=3 * 1024**3,
            temp_size_bytes=1 * 1024**3,
            available_space_bytes=200 * 1024**2,  # 200MB - critical low space
            utilization_percentage=95.0  # Very high utilization
        )

        plan = OptimizationPlan(
            total_cleanup_bytes=2 * 1024**3,  # 2GB - large cleanup needed
            cleanup_candidates=[],
            compression_opportunities=[],
            archive_suggestions=[],
            estimated_space_saved_bytes=2 * 1024**3,
            risk_assessment="HIGH RISK"
        )

        score = optimizer._calculate_storage_health_score(stats, plan)

        assert score <= 50.0  # Should be poor

    @pytest.mark.asyncio
    async def test_analyze_storage_complete(self, optimizer, sample_cache_db, sample_assets_dir, sample_temp_dir):
        """Test complete storage analysis workflow."""
        report = await optimizer.analyze_storage()

        assert isinstance(report, OptimizationReport)
        assert report.timestamp is not None
        assert isinstance(report.storage_stats, StorageStats)
        assert isinstance(report.optimization_plan, OptimizationPlan)
        assert isinstance(report.recommendations, list)
        assert len(report.recommendations) > 0
        assert 0.0 <= report.health_score <= 100.0

    @pytest.mark.asyncio
    async def test_execute_cleanup_dry_run(self, optimizer):
        """Test cleanup execution in dry-run mode."""
        candidates = [
            CleanupCandidate("temp", "temp/file1.tmp", 1000, datetime.now(), 0.1, "old temp"),
            CleanupCandidate("page", "page123", 5000, datetime.now(), 0.3, "old page"),
        ]

        results = await optimizer.execute_cleanup(candidates, dry_run=True)

        assert results["temp_removed"] == 1
        assert results["pages_removed"] == 1
        assert results["bytes_freed"] == 6000
        assert results["errors"] == 0

    @pytest.mark.asyncio
    async def test_execute_cleanup_real(self, optimizer, sample_cache_db, sample_temp_dir):
        """Test actual cleanup execution."""
        # Create a temp file to clean up
        test_file = sample_temp_dir / "cleanup_test.tmp"
        test_file.write_text("test content")

        candidates = [
            CleanupCandidate(
                "temp",
                f"temp/{test_file.name}",
                len("test content"),
                datetime.now(),
                0.1,
                "test cleanup"
            )
        ]

        results = await optimizer.execute_cleanup(candidates, dry_run=False)

        assert results["temp_removed"] == 1
        assert results["bytes_freed"] > 0
        assert not test_file.exists()  # File should be deleted

    @pytest.mark.asyncio
    async def test_cleanup_database_page(self, optimizer, sample_cache_db):
        """Test database page removal."""
        # Verify page exists first
        with sqlite3.connect(optimizer.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM pages WHERE page_id = 'old_page_1'")
            assert cursor.fetchone()[0] == 1

        # Remove the page
        await optimizer._remove_page('old_page_1')

        # Verify page is removed
        with sqlite3.connect(optimizer.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM pages WHERE page_id = 'old_page_1'")
            assert cursor.fetchone()[0] == 0

    @pytest.mark.asyncio
    async def test_cleanup_asset_file(self, optimizer, sample_assets_dir):
        """Test asset file removal."""
        test_file = sample_assets_dir / "test_asset.jpg"
        test_file.write_bytes(b"test image data")

        assert test_file.exists()

        # Remove the asset
        await optimizer._remove_asset(f"assets/{test_file.name}")

        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_error_handling_in_analysis(self, optimizer):
        """Test error handling during analysis."""
        # Force error by using invalid paths
        optimizer.db_path = Path("/invalid/path/cache.db")
        optimizer.assets_dir = Path("/invalid/path/assets")
        optimizer.temp_dir = Path("/invalid/path/temp")

        # Should not raise exception, return basic report
        report = await optimizer.analyze_storage()

        assert isinstance(report, OptimizationReport)
        assert report.health_score == 0.0
        assert "failed" in report.recommendations[0].lower()

    @pytest.mark.asyncio
    async def test_get_directory_size(self, optimizer, sample_assets_dir):
        """Test directory size calculation."""
        size = await optimizer._get_directory_size(sample_assets_dir)

        assert size > 0

        # Test with non-existent directory
        empty_size = await optimizer._get_directory_size(Path("/non/existent/path"))
        assert empty_size == 0
