"""
Storage Optimization System for OneNote Copilot.

This module provides intelligent cache size management, cleanup recommendations,
and storage optimization strategies for the OneNote local cache system.
"""

import asyncio
import os
import shutil
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..config.settings import get_settings


@dataclass
class StorageStats:
    """Storage utilization statistics."""
    total_size_bytes: int
    database_size_bytes: int
    assets_size_bytes: int
    temp_size_bytes: int
    available_space_bytes: int
    utilization_percentage: float


@dataclass
class CleanupCandidate:
    """Candidate content for cleanup."""
    content_type: str  # 'page', 'asset', 'temp'
    identifier: str
    size_bytes: int
    last_accessed: Optional[datetime]
    importance_score: float
    reason: str


@dataclass
class OptimizationPlan:
    """Storage optimization plan."""
    total_cleanup_bytes: int
    cleanup_candidates: List[CleanupCandidate]
    compression_opportunities: List[str]
    archive_suggestions: List[str]
    estimated_space_saved_bytes: int
    risk_assessment: str


@dataclass
class OptimizationReport:
    """Storage optimization results."""
    timestamp: datetime
    storage_stats: StorageStats
    optimization_plan: OptimizationPlan
    recommendations: List[str]
    health_score: float


class StorageOptimizer:
    """
    Intelligent storage optimization and cache management system.

    Provides automated cleanup suggestions, storage analysis,
    and optimization recommendations for efficient cache management.
    """

    def __init__(self):
        """Initialize the storage optimizer."""
        self.settings = get_settings()
        self.cache_dir = Path(self.settings.cache_dir)
        self.db_path = self.cache_dir / "cache.db"
        self.assets_dir = self.cache_dir / "assets"
        self.temp_dir = self.cache_dir / "temp"

        # Optimization thresholds
        self.max_cache_size_gb = 5.0  # Maximum recommended cache size
        self.old_content_days = 90    # Content older than this considered for cleanup
        self.unused_content_days = 30 # Content unused for this long considered for cleanup

    async def analyze_storage(self) -> OptimizationReport:
        """
        Perform comprehensive storage analysis and optimization planning.

        Returns:
            OptimizationReport: Complete storage analysis with optimization plan
        """
        try:
            # Gather storage statistics
            storage_stats = await self._analyze_storage_stats()

            # Create optimization plan
            optimization_plan = await self._create_optimization_plan(storage_stats)

            # Generate recommendations
            recommendations = await self._generate_recommendations(
                storage_stats, optimization_plan
            )

            # Calculate health score
            health_score = self._calculate_storage_health_score(
                storage_stats, optimization_plan
            )

            return OptimizationReport(
                timestamp=datetime.now(),
                storage_stats=storage_stats,
                optimization_plan=optimization_plan,
                recommendations=recommendations,
                health_score=health_score
            )
        except Exception as e:
            # Return basic report if analysis fails
            return OptimizationReport(
                timestamp=datetime.now(),
                storage_stats=StorageStats(0, 0, 0, 0, 0, 0.0),
                optimization_plan=OptimizationPlan(0, [], [], [], 0, "Analysis failed"),
                recommendations=[f"Storage analysis failed: {str(e)}"],
                health_score=0.0
            )

    async def _analyze_storage_stats(self) -> StorageStats:
        """Analyze current storage utilization."""
        try:
            # Calculate directory sizes
            total_size = await self._get_directory_size(self.cache_dir)
            database_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            assets_size = await self._get_directory_size(self.assets_dir) if self.assets_dir.exists() else 0
            temp_size = await self._get_directory_size(self.temp_dir) if self.temp_dir.exists() else 0

            # Get available disk space
            available_space = shutil.disk_usage(self.cache_dir).free

            # Calculate utilization percentage
            disk_total = shutil.disk_usage(self.cache_dir).total
            utilization = (total_size / disk_total) * 100 if disk_total > 0 else 0.0

            return StorageStats(
                total_size_bytes=total_size,
                database_size_bytes=database_size,
                assets_size_bytes=assets_size,
                temp_size_bytes=temp_size,
                available_space_bytes=available_space,
                utilization_percentage=utilization
            )
        except Exception as e:
            return StorageStats(0, 0, 0, 0, 0, 0.0)

    async def _get_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory contents."""
        if not directory.exists():
            return 0

        total_size = 0
        try:
            for item in directory.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
        except Exception:
            pass

        return total_size

    async def _create_optimization_plan(self, storage_stats: StorageStats) -> OptimizationPlan:
        """Create comprehensive optimization plan."""
        cleanup_candidates = []
        compression_opportunities = []
        archive_suggestions = []

        # Analyze database content for cleanup candidates
        if self.db_path.exists():
            cleanup_candidates.extend(await self._analyze_database_cleanup())

        # Analyze asset files for cleanup
        if self.assets_dir.exists():
            cleanup_candidates.extend(await self._analyze_assets_cleanup())

        # Analyze temporary files
        if self.temp_dir.exists():
            cleanup_candidates.extend(await self._analyze_temp_cleanup())

        # Identify compression opportunities
        compression_opportunities = await self._identify_compression_opportunities()

        # Generate archive suggestions
        archive_suggestions = await self._generate_archive_suggestions()

        # Calculate total cleanup potential
        total_cleanup = sum(candidate.size_bytes for candidate in cleanup_candidates)

        # Estimate space savings (including compression)
        estimated_savings = total_cleanup + (storage_stats.total_size_bytes * 0.1)  # 10% compression estimate

        # Risk assessment
        risk_assessment = self._assess_cleanup_risk(cleanup_candidates)

        return OptimizationPlan(
            total_cleanup_bytes=total_cleanup,
            cleanup_candidates=cleanup_candidates,
            compression_opportunities=compression_opportunities,
            archive_suggestions=archive_suggestions,
            estimated_space_saved_bytes=int(estimated_savings),
            risk_assessment=risk_assessment
        )

    async def _analyze_database_cleanup(self) -> List[CleanupCandidate]:
        """Analyze database content for cleanup opportunities."""
        candidates = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Old content that hasn't been accessed recently
                old_date = (datetime.now() - timedelta(days=self.old_content_days)).isoformat()
                cursor = conn.execute("""
                    SELECT page_id, title, LENGTH(content) as size, last_modified_time
                    FROM pages
                    WHERE last_modified_time < ?
                    ORDER BY last_modified_time ASC
                    LIMIT 50
                """, (old_date,))

                for page_id, title, size, last_modified in cursor.fetchall():
                    last_mod = datetime.fromisoformat(last_modified) if last_modified else None

                    candidates.append(CleanupCandidate(
                        content_type="page",
                        identifier=page_id,
                        size_bytes=size or 0,
                        last_accessed=last_mod,
                        importance_score=self._calculate_page_importance(title, last_mod),
                        reason=f"Old content (last modified: {last_mod.strftime('%Y-%m-%d') if last_mod else 'unknown'})"
                    ))

                # Large pages with minimal content value
                cursor = conn.execute("""
                    SELECT page_id, title, LENGTH(content) as size, last_modified_time
                    FROM pages
                    WHERE LENGTH(content) > 50000
                    ORDER BY LENGTH(content) DESC
                    LIMIT 20
                """)

                for page_id, title, size, last_modified in cursor.fetchall():
                    last_mod = datetime.fromisoformat(last_modified) if last_modified else None

                    # Only suggest if importance is low
                    importance = self._calculate_page_importance(title, last_mod)
                    if importance < 0.5:
                        candidates.append(CleanupCandidate(
                            content_type="page",
                            identifier=page_id,
                            size_bytes=size or 0,
                            last_accessed=last_mod,
                            importance_score=importance,
                            reason=f"Large page with low importance ({size // 1024}KB)"
                        ))

        except Exception as e:
            pass

        return candidates

    async def _analyze_assets_cleanup(self) -> List[CleanupCandidate]:
        """Analyze asset files for cleanup opportunities."""
        candidates = []

        if not self.assets_dir.exists():
            return candidates

        try:
            for asset_file in self.assets_dir.rglob('*'):
                if not asset_file.is_file():
                    continue

                # Get file stats
                stat = asset_file.stat()
                size = stat.st_size
                last_accessed = datetime.fromtimestamp(stat.st_atime)

                # Check if file is old or large
                days_since_access = (datetime.now() - last_accessed).days

                if days_since_access > self.unused_content_days or size > 10 * 1024 * 1024:  # 10MB+
                    reason = []
                    if days_since_access > self.unused_content_days:
                        reason.append(f"unused for {days_since_access} days")
                    if size > 10 * 1024 * 1024:
                        reason.append(f"large file ({size // (1024*1024)}MB)")

                    candidates.append(CleanupCandidate(
                        content_type="asset",
                        identifier=str(asset_file.relative_to(self.cache_dir)),
                        size_bytes=size,
                        last_accessed=last_accessed,
                        importance_score=self._calculate_asset_importance(asset_file, last_accessed),
                        reason=", ".join(reason)
                    ))

        except Exception as e:
            pass

        return candidates

    async def _analyze_temp_cleanup(self) -> List[CleanupCandidate]:
        """Analyze temporary files for cleanup."""
        candidates = []

        if not self.temp_dir.exists():
            return candidates

        try:
            for temp_file in self.temp_dir.rglob('*'):
                if not temp_file.is_file():
                    continue

                stat = temp_file.stat()
                size = stat.st_size
                last_modified = datetime.fromtimestamp(stat.st_mtime)

                # All temp files older than 1 day are candidates
                days_old = (datetime.now() - last_modified).days
                if days_old > 1:
                    candidates.append(CleanupCandidate(
                        content_type="temp",
                        identifier=str(temp_file.relative_to(self.cache_dir)),
                        size_bytes=size,
                        last_accessed=last_modified,
                        importance_score=0.1,  # Temp files have low importance
                        reason=f"temporary file ({days_old} days old)"
                    ))

        except Exception as e:
            pass

        return candidates

    def _calculate_page_importance(self, title: Optional[str], last_modified: Optional[datetime]) -> float:
        """Calculate importance score for a page (0.0 - 1.0)."""
        score = 0.5  # Base score

        # Title-based scoring
        if title:
            # Important keywords increase score
            important_keywords = [
                "meeting", "project", "task", "todo", "important",
                "action", "decision", "plan", "goal", "deadline"
            ]
            for keyword in important_keywords:
                if keyword.lower() in title.lower():
                    score += 0.1

            # Recent in title increases score
            if any(word in title.lower() for word in ["2024", "2025", "current", "new"]):
                score += 0.1

        # Recency scoring
        if last_modified:
            days_old = (datetime.now() - last_modified).days
            if days_old < 7:
                score += 0.3
            elif days_old < 30:
                score += 0.2
            elif days_old < 90:
                score += 0.1

        return min(1.0, max(0.0, score))

    def _calculate_asset_importance(self, asset_path: Path, last_accessed: datetime) -> float:
        """Calculate importance score for an asset file."""
        score = 0.3  # Base score for assets

        # File type scoring
        if asset_path.suffix.lower() in ['.jpg', '.png', '.gif']:
            score += 0.2  # Images are moderately important
        elif asset_path.suffix.lower() in ['.pdf', '.doc', '.docx']:
            score += 0.4  # Documents are more important

        # Recent access increases importance
        days_since_access = (datetime.now() - last_accessed).days
        if days_since_access < 7:
            score += 0.3
        elif days_since_access < 30:
            score += 0.2

        return min(1.0, max(0.0, score))

    async def _identify_compression_opportunities(self) -> List[str]:
        """Identify opportunities for data compression."""
        opportunities = []

        # Database compression
        if self.db_path.exists():
            db_size_mb = self.db_path.stat().st_size / (1024 * 1024)
            if db_size_mb > 100:  # Large database
                opportunities.append(f"Database compression could save ~20% of {db_size_mb:.1f}MB")

        # Asset compression
        if self.assets_dir.exists():
            try:
                large_images = []
                for asset in self.assets_dir.rglob('*'):
                    if asset.is_file() and asset.suffix.lower() in ['.jpg', '.png', '.bmp']:
                        size_mb = asset.stat().st_size / (1024 * 1024)
                        if size_mb > 5:  # Large image files
                            large_images.append((asset, size_mb))

                if large_images:
                    total_size = sum(size for _, size in large_images)
                    opportunities.append(
                        f"Image compression could save ~30% of {total_size:.1f}MB "
                        f"across {len(large_images)} large images"
                    )
            except Exception:
                pass

        return opportunities

    async def _generate_archive_suggestions(self) -> List[str]:
        """Generate suggestions for archiving old content."""
        suggestions = []

        try:
            if self.db_path.exists():
                with sqlite3.connect(self.db_path) as conn:
                    # Count old content
                    six_months_ago = (datetime.now() - timedelta(days=180)).isoformat()
                    cursor = conn.execute("""
                        SELECT COUNT(*), SUM(LENGTH(content))
                        FROM pages
                        WHERE last_modified_time < ?
                    """, (six_months_ago,))

                    result = cursor.fetchone()
                    if result and result[0] > 0:
                        old_count = result[0]
                        old_size_mb = (result[1] or 0) / (1024 * 1024)

                        suggestions.append(
                            f"Archive {old_count} pages older than 6 months "
                            f"({old_size_mb:.1f}MB) to external storage"
                        )

                    # Suggest archiving by notebook for unused notebooks
                    cursor = conn.execute("""
                        SELECT notebook_name, COUNT(*) as page_count,
                               SUM(LENGTH(content)) as total_size,
                               MAX(last_modified_time) as latest_activity
                        FROM pages
                        GROUP BY notebook_id, notebook_name
                        HAVING latest_activity < ?
                        ORDER BY total_size DESC
                        LIMIT 5
                    """, (six_months_ago,))

                    for notebook_name, page_count, total_size, latest in cursor.fetchall():
                        size_mb = (total_size or 0) / (1024 * 1024)
                        if size_mb > 10:  # Only suggest for significant size
                            suggestions.append(
                                f"Archive notebook '{notebook_name}' ({page_count} pages, "
                                f"{size_mb:.1f}MB) - inactive since {latest[:10] if latest else 'unknown'}"
                            )

        except Exception:
            pass

        return suggestions

    def _assess_cleanup_risk(self, candidates: List[CleanupCandidate]) -> str:
        """Assess the risk level of proposed cleanup operations."""
        if not candidates:
            return "No cleanup needed"

        # Calculate risk based on importance scores and content types
        high_importance_count = sum(1 for c in candidates if c.importance_score > 0.7)
        temp_count = sum(1 for c in candidates if c.content_type == "temp")
        page_count = sum(1 for c in candidates if c.content_type == "page")

        if high_importance_count > len(candidates) * 0.3:  # 30%+ high importance
            return "HIGH RISK - Many important items selected for cleanup"
        elif page_count > temp_count and page_count > 10:
            return "MEDIUM RISK - Significant page content cleanup proposed"
        elif temp_count == len(candidates):
            return "LOW RISK - Only temporary files targeted"
        else:
            return "MEDIUM RISK - Mixed content cleanup"

    async def _generate_recommendations(
        self,
        storage_stats: StorageStats,
        optimization_plan: OptimizationPlan
    ) -> List[str]:
        """Generate storage optimization recommendations."""
        # Check for error conditions (invalid paths detected)
        if (storage_stats.total_size_bytes == 0 and
            storage_stats.database_size_bytes == 0 and
            storage_stats.assets_size_bytes == 0 and
            storage_stats.temp_size_bytes == 0 and
            storage_stats.utilization_percentage == 0.0 and
            not self.db_path.exists()):
            return ["Storage analysis failed: Invalid paths detected"]

        recommendations = []

        # Size-based recommendations
        total_gb = storage_stats.total_size_bytes / (1024 ** 3)
        if total_gb > self.max_cache_size_gb:
            recommendations.append(
                f"Cache size ({total_gb:.1f}GB) exceeds recommended maximum "
                f"({self.max_cache_size_gb}GB). Consider cleanup or archival."
            )

        # Available space warnings
        available_gb = storage_stats.available_space_bytes / (1024 ** 3)
        if available_gb < 1:
            recommendations.append(
                f"Low disk space warning: Only {available_gb:.1f}GB available. "
                "Immediate cleanup recommended."
            )
        elif available_gb < 5:
            recommendations.append(
                f"Moderate disk space: {available_gb:.1f}GB available. "
                "Consider cleanup to prevent future issues."
            )

        # Cleanup recommendations
        if optimization_plan.total_cleanup_bytes > 100 * 1024 * 1024:  # > 100MB
            cleanup_mb = optimization_plan.total_cleanup_bytes / (1024 * 1024)
            recommendations.append(
                f"Significant cleanup opportunity: {cleanup_mb:.1f}MB can be safely removed. "
                f"Risk level: {optimization_plan.risk_assessment}"
            )

        # Compression recommendations
        if optimization_plan.compression_opportunities:
            recommendations.extend(
                f"Compression: {opp}" for opp in optimization_plan.compression_opportunities
            )

        # Archive recommendations
        if optimization_plan.archive_suggestions:
            recommendations.append(
                f"Archive opportunities: {len(optimization_plan.archive_suggestions)} suggestions available"
            )

        # Maintenance recommendations
        recommendations.extend([
            "Regular maintenance: Run optimization analysis monthly",
            "Monitor cache growth and set up automated cleanup policies",
            "Consider implementing compression for large content"
        ])

        return recommendations

    def _calculate_storage_health_score(
        self,
        storage_stats: StorageStats,
        optimization_plan: OptimizationPlan
    ) -> float:
        """Calculate overall storage health score (0-100)."""
        # Check for error conditions (all storage stats are zero except available space)
        # This indicates invalid paths or analysis failure
        if (storage_stats.total_size_bytes == 0 and
            storage_stats.database_size_bytes == 0 and
            storage_stats.assets_size_bytes == 0 and
            storage_stats.temp_size_bytes == 0 and
            storage_stats.utilization_percentage == 0.0 and
            not self.db_path.exists()):  # Additional check for invalid paths
            return 0.0

        score = 100.0

        # Size penalty
        total_gb = storage_stats.total_size_bytes / (1024 ** 3)
        if total_gb > self.max_cache_size_gb:
            penalty = min(30, (total_gb - self.max_cache_size_gb) * 10)
            score -= penalty

        # Available space penalty
        available_gb = storage_stats.available_space_bytes / (1024 ** 3)
        if available_gb < 1:
            score -= 40  # Critical space issue
        elif available_gb < 5:
            score -= 20  # Moderate space issue

        # Cleanup opportunity penalty (suggests inefficiency)
        cleanup_gb = optimization_plan.total_cleanup_bytes / (1024 ** 3)
        if cleanup_gb > 1:
            penalty = min(20, cleanup_gb * 5)
            score -= penalty

        # Utilization penalty
        if storage_stats.utilization_percentage > 90:
            score -= 15
        elif storage_stats.utilization_percentage > 80:
            score -= 10

        return max(0.0, min(100.0, score))

    async def execute_cleanup(
        self,
        candidates: List[CleanupCandidate],
        dry_run: bool = True
    ) -> Dict[str, int]:
        """
        Execute cleanup operations on selected candidates.

        Args:
            candidates: List of cleanup candidates to process
            dry_run: If True, only simulate the cleanup

        Returns:
            Dict with cleanup statistics
        """
        results = {
            "pages_removed": 0,
            "assets_removed": 0,
            "temp_removed": 0,
            "bytes_freed": 0,
            "errors": 0
        }

        for candidate in candidates:
            try:
                if candidate.content_type == "page":
                    if not dry_run:
                        await self._remove_page(candidate.identifier)
                    results["pages_removed"] += 1

                elif candidate.content_type == "asset":
                    if not dry_run:
                        await self._remove_asset(candidate.identifier)
                    results["assets_removed"] += 1

                elif candidate.content_type == "temp":
                    if not dry_run:
                        await self._remove_temp_file(candidate.identifier)
                    results["temp_removed"] += 1

                results["bytes_freed"] += candidate.size_bytes

            except Exception as e:
                results["errors"] += 1

        return results

    async def _remove_page(self, page_id: str) -> None:
        """Remove a page from the database cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM pages WHERE page_id = ?", (page_id,))
            conn.commit()

    async def _remove_asset(self, asset_path: str) -> None:
        """Remove an asset file from storage."""
        full_path = self.cache_dir / asset_path
        if full_path.exists():
            full_path.unlink()

    async def _remove_temp_file(self, temp_path: str) -> None:
        """Remove a temporary file."""
        full_path = self.cache_dir / temp_path
        if full_path.exists():
            full_path.unlink()
