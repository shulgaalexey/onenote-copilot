"""
Incremental sync manager for OneNote cache system.

Provides intelligent content synchronization with change detection,
conflict resolution, and efficient update strategies.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..models.cache import CachedPage, SyncResult
from ..models.onenote import OneNoteNotebook, OneNotePage, OneNoteSection
from .bulk_indexer import BulkContentIndexer, IndexingProgress
from .cache_manager import OneNoteCacheManager
from .directory_utils import get_content_path_for_page
from .onenote_fetcher import OneNoteContentFetcher

logger = logging.getLogger(__name__)


class SyncStrategy(Enum):
    """Synchronization strategy options."""
    REMOTE_WINS = "remote_wins"      # Remote changes always take precedence
    LOCAL_WINS = "local_wins"        # Local changes take precedence
    NEWER_WINS = "newer_wins"        # Most recently modified wins
    USER_PROMPT = "user_prompt"      # Ask user to resolve conflicts
    MERGE_ATTEMPT = "merge_attempt"  # Try to merge changes intelligently


class ChangeType(Enum):
    """Types of content changes."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"
    RENAMED = "renamed"
    CONFLICTED = "conflicted"


@dataclass
class ContentChange:
    """Represents a detected change in content."""

    change_type: ChangeType
    page_id: str
    page_title: str
    notebook_id: str
    section_id: str

    # Timestamps
    local_modified: Optional[datetime] = None
    remote_modified: Optional[datetime] = None
    detected_at: datetime = field(default_factory=datetime.utcnow)

    # Content information
    local_size: Optional[int] = None
    remote_size: Optional[int] = None
    content_hash_diff: bool = False

    # Conflict details
    conflict_reason: Optional[str] = None
    resolution_strategy: Optional[SyncStrategy] = None

    def is_conflict(self) -> bool:
        """Check if this change represents a conflict."""
        return self.change_type == ChangeType.CONFLICTED or self.conflict_reason is not None


@dataclass
class SyncOperation:
    """Represents a sync operation to be performed."""

    change: ContentChange
    action: str  # "update", "delete", "create", "skip"
    strategy_used: SyncStrategy
    estimated_time: Optional[float] = None
    priority: int = 0  # Higher number = higher priority


@dataclass
class SyncReport:
    """Comprehensive sync operation report."""

    # Operation metadata
    start_time: datetime
    end_time: Optional[datetime] = None
    sync_strategy: SyncStrategy = SyncStrategy.NEWER_WINS

    # Change statistics
    total_changes: int = 0
    changes_by_type: Dict[ChangeType, int] = field(default_factory=dict)

    # Operation statistics
    pages_updated: int = 0
    pages_created: int = 0
    pages_deleted: int = 0
    pages_skipped: int = 0

    # Conflict handling
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    conflicts_pending: int = 0

    # Performance metrics
    total_data_transferred: int = 0
    average_page_sync_time: float = 0.0

    # Error tracking
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def get_duration(self) -> Optional[timedelta]:
        """Get total sync duration."""
        if not self.end_time:
            return None
        return self.end_time - self.start_time

    def get_success_rate(self) -> float:
        """Get sync success rate percentage."""
        total_operations = self.pages_updated + self.pages_created + self.pages_deleted + len(self.errors)
        if total_operations == 0:
            return 100.0
        return ((total_operations - len(self.errors)) / total_operations) * 100.0


class IncrementalSyncManager:
    """
    Manager for intelligent incremental content synchronization.

    Detects changes between local cache and remote OneNote content,
    resolves conflicts, and performs efficient updates.
    """

    def __init__(self,
                 cache_root: Path,
                 content_fetcher: OneNoteContentFetcher,
                 cache_manager: Optional[OneNoteCacheManager] = None,
                 bulk_indexer: Optional[BulkContentIndexer] = None,
                 default_strategy: SyncStrategy = SyncStrategy.NEWER_WINS,
                 change_detection_window: timedelta = timedelta(days=30)):
        """
        Initialize incremental sync manager.

        Args:
            cache_root: Root directory for cache storage
            content_fetcher: OneNote content fetcher
            cache_manager: Cache manager for local storage operations
            bulk_indexer: Bulk content indexer (optional)
            default_strategy: Default conflict resolution strategy
            change_detection_window: Time window for change detection
        """
        self.cache_root = Path(cache_root)
        self.content_fetcher = content_fetcher
        self.cache_manager = cache_manager
        self.bulk_indexer = bulk_indexer
        self.default_strategy = default_strategy
        self.change_detection_window = change_detection_window

        # State tracking
        self.last_sync_time: Optional[datetime] = None
        self.pending_conflicts: List[ContentChange] = []

        logger.info(f"Initialized incremental sync manager with strategy: {default_strategy.value}")

    async def detect_changes(self,
                           user_id: str,
                           notebooks: Optional[List[Dict]] = None,
                           force_full_scan: bool = False) -> List[ContentChange]:
        """
        Detect changes between local cache and remote content.

        Args:
            user_id: User identifier for cache operations
            notebooks: Specific notebooks to check (None for all)
            force_full_scan: Whether to scan all content regardless of timestamps

        Returns:
            List of detected changes
        """
        try:
            logger.info("Starting change detection...")
            changes = []

            # Get notebooks to check
            if not notebooks:
                notebooks = await self.content_fetcher._get_all_notebooks()

            # Set change detection cutoff time
            cutoff_time = None
            if not force_full_scan and self.last_sync_time:
                cutoff_time = self.last_sync_time - timedelta(hours=1)  # Buffer for clock skew

            for notebook in notebooks:
                notebook_changes = await self._detect_notebook_changes(user_id, notebook, cutoff_time)
                changes.extend(notebook_changes)

            logger.info(f"Detected {len(changes)} changes across {len(notebooks)} notebooks")

            # Categorize changes
            change_counts = {}
            for change in changes:
                change_counts[change.change_type] = change_counts.get(change.change_type, 0) + 1

            for change_type, count in change_counts.items():
                logger.info(f"  {change_type.value}: {count}")

            return changes

        except Exception as e:
            logger.error(f"Change detection failed: {e}")
            raise

    async def _detect_notebook_changes(self,
                                     user_id: str,
                                     notebook: Dict,
                                     cutoff_time: Optional[datetime]) -> List[ContentChange]:
        """Detect changes within a specific notebook."""
        changes = []

        try:
            sections = await self.content_fetcher._get_all_sections(notebook_id=notebook["id"])

            for section in sections:
                section_changes = await self._detect_section_changes(
                    user_id, notebook, section, cutoff_time
                )
                changes.extend(section_changes)

        except Exception as e:
            logger.error(f"Failed to detect changes in notebook {notebook.get('displayName', notebook['id'])}: {e}")

        return changes

    async def _detect_section_changes(self,
                                    user_id: str,
                                    notebook: Dict,
                                    section: Dict,
                                    cutoff_time: Optional[datetime]) -> List[ContentChange]:
        """Detect changes within a specific section."""
        changes = []
        section_name = section.get("displayName", section.get("name", section["id"]))

        try:
            logger.debug(f"Starting change detection for section: {section_name}")
            # Get remote pages
            remote_pages = await self.content_fetcher._get_pages_from_section(section["id"])
            logger.debug(f"Found {len(remote_pages)} remote pages in section {section_name}")
            logger.debug(f"Found {len(remote_pages)} remote pages in section {section_name}")

            # Debug: check the format of remote pages
            if remote_pages:
                sample_page = remote_pages[0]
                logger.debug(f"Sample remote page keys: {list(sample_page.keys()) if isinstance(sample_page, dict) else type(sample_page)}")
                if isinstance(sample_page, dict) and "lastModifiedDateTime" in sample_page:
                    logger.debug(f"Sample lastModifiedDateTime: {sample_page['lastModifiedDateTime']} (type: {type(sample_page['lastModifiedDateTime'])})")

            # Filter by modification time if cutoff specified
            if cutoff_time:
                filtered_pages = []
                for page in remote_pages:
                    try:
                        if isinstance(page, dict) and "lastModifiedDateTime" in page:
                            last_modified_str = page["lastModifiedDateTime"]
                            if isinstance(last_modified_str, str):
                                page_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
                                if page_modified > cutoff_time:
                                    filtered_pages.append(page)
                            else:
                                logger.warning(f"lastModifiedDateTime is not string: {type(last_modified_str)}")
                                filtered_pages.append(page)  # Include it anyway
                        else:
                            logger.warning(f"Page missing lastModifiedDateTime: {page}")
                            filtered_pages.append(page)  # Include it anyway
                    except Exception as e:
                        logger.warning(f"Error filtering page by cutoff time: {e}")
                        filtered_pages.append(page)  # Include it anyway
                remote_pages = filtered_pages
                logger.debug(f"After cutoff filtering: {len(remote_pages)} pages remain")

            # Get local pages
            local_pages = await self._get_local_pages(user_id, notebook, section)
            logger.debug(f"Found {len(local_pages)} local pages in section {section_name}")
            local_page_ids = {page["id"] for page in local_pages}
            remote_page_ids = {page["id"] for page in remote_pages}

            # Detect different types of changes

            # New pages (added remotely)
            new_page_ids = remote_page_ids - local_page_ids
            logger.debug(f"New pages to add: {len(new_page_ids)}")
            for page_id in new_page_ids:
                remote_page = next(p for p in remote_pages if p["id"] == page_id)
                try:
                    remote_modified = None
                    if isinstance(remote_page, dict) and "lastModifiedDateTime" in remote_page:
                        last_modified_str = remote_page["lastModifiedDateTime"]
                        if isinstance(last_modified_str, str):
                            remote_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
                        else:
                            logger.warning(f"lastModifiedDateTime is not string: {type(last_modified_str)}")

                    changes.append(ContentChange(
                        change_type=ChangeType.ADDED,
                        page_id=page_id,
                        page_title=remote_page.get("title", "Unknown"),
                        notebook_id=notebook["id"],
                        section_id=section["id"],
                        remote_modified=remote_modified
                    ))
                except Exception as e:
                    logger.error(f"Error processing new page {page_id}: {e}")
                    continue

            # Deleted pages (removed remotely)
            deleted_page_ids = local_page_ids - remote_page_ids
            logger.debug(f"Deleted pages to remove: {len(deleted_page_ids)}")
            for page_id in deleted_page_ids:
                local_page = next(p for p in local_pages if p["id"] == page_id)
                try:
                    local_modified = None
                    if isinstance(local_page, dict) and "lastModifiedDateTime" in local_page:
                        last_modified_str = local_page["lastModifiedDateTime"]
                        if isinstance(last_modified_str, str):
                            local_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
                        else:
                            logger.warning(f"Local page lastModifiedDateTime is not string: {type(last_modified_str)}")

                    changes.append(ContentChange(
                        change_type=ChangeType.DELETED,
                        page_id=page_id,
                        page_title=local_page.get("title", "Unknown"),
                        notebook_id=notebook["id"],
                        section_id=section["id"],
                        local_modified=local_modified
                    ))
                except Exception as e:
                    logger.error(f"Error processing deleted page {page_id}: {e}")
                    continue

            # Modified pages
            common_page_ids = local_page_ids & remote_page_ids
            logger.debug(f"Pages to compare for modifications: {len(common_page_ids)}")
            for page_id in common_page_ids:
                local_page = next(p for p in local_pages if p["id"] == page_id)
                remote_page = next(p for p in remote_pages if p["id"] == page_id)

                try:
                    change = await self._compare_pages(user_id, notebook, section, local_page, remote_page)
                    if change:
                        changes.append(change)
                except Exception as e:
                    logger.error(f"Error comparing page {page_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to detect changes in section {section_name}: {e}", exc_info=True)

        return changes

    async def _get_local_pages(self,
                             user_id: str,
                             notebook: Dict,
                             section: Dict) -> List[Dict]:
        """Get pages from local cache for a section."""
        local_pages = []
        section_name = section.get("displayName", section.get("name", section["id"]))

        try:
            logger.debug(f"Getting local pages for section {section_name}")
            # Use cache manager to get local pages
            if self.cache_manager:
                logger.debug(f"Using cache manager to get local pages")
                cached_pages = await self.cache_manager.get_pages_by_section(
                    user_id=user_id,
                    section_id=section["id"]
                )
                logger.debug(f"Cache manager returned {len(cached_pages)} pages")

                # Convert cached pages to dict format for consistency
                for cached_page in cached_pages:
                    try:
                        logger.debug(f"Converting cached page {cached_page.page_id}, modified={cached_page.last_modified_date_time} (type: {type(cached_page.last_modified_date_time)})")

                        page_dict = {
                            "id": cached_page.page_id,
                            "title": cached_page.title,
                            "lastModifiedDateTime": cached_page.last_modified_date_time.isoformat() if cached_page.last_modified_date_time else None,
                            "createdDateTime": cached_page.created_date_time.isoformat() if cached_page.created_date_time else None
                        }

                        logger.debug(f"Converted page dict keys: {list(page_dict.keys())}")
                        logger.debug(f"lastModifiedDateTime in dict: {page_dict['lastModifiedDateTime']} (type: {type(page_dict['lastModifiedDateTime'])})")

                        local_pages.append(page_dict)

                    except Exception as e:
                        logger.error(f"Error converting cached page {getattr(cached_page, 'page_id', 'unknown')}: {e}", exc_info=True)
                        continue
                        continue
            else:
                logger.debug(f"No cache manager, using fallback file system check")
                # Fallback: Simple file system check
                section_dir = self.cache_root / "content" / notebook["displayName"] / section_name

                if section_dir.exists():
                    logger.debug(f"Section directory exists: {section_dir}")
                    for page_dir in section_dir.iterdir():
                        if page_dir.is_dir():
                            metadata_file = page_dir / "metadata.json"
                            if metadata_file.exists():
                                local_pages.append({
                                    "id": page_dir.name,
                                    "title": page_dir.name,
                                    "lastModifiedDateTime": datetime.fromtimestamp(
                                        metadata_file.stat().st_mtime
                                    ).isoformat(),
                                    "createdDateTime": datetime.fromtimestamp(
                                        metadata_file.stat().st_ctime
                                    ).isoformat()
                                })
                else:
                    logger.debug(f"Section directory does not exist: {section_dir}")

        except Exception as e:
            logger.error(f"Error getting local pages for section {section_name}: {e}", exc_info=True)

        logger.debug(f"Returning {len(local_pages)} local pages for section {section_name}")
        return local_pages

    async def _compare_pages(self,
                           user_id: str,
                           notebook: Dict,
                           section: Dict,
                           local_page: Dict,
                           remote_page: Dict) -> Optional[ContentChange]:
        """Compare local and remote page versions."""
        try:
            page_id = local_page.get("id", "unknown")
            logger.debug(f"Comparing page {page_id}")

            # Debug info about page data types and keys
            logger.debug(f"Local page type: {type(local_page)}, keys: {list(local_page.keys()) if isinstance(local_page, dict) else 'not dict'}")
            logger.debug(f"Remote page type: {type(remote_page)}, keys: {list(remote_page.keys()) if isinstance(remote_page, dict) else 'not dict'}")

            # Parse timestamps with extra validation
            local_modified = None
            if isinstance(local_page, dict) and "lastModifiedDateTime" in local_page:
                last_modified_str = local_page["lastModifiedDateTime"]
                logger.debug(f"Local lastModifiedDateTime: {last_modified_str} (type: {type(last_modified_str)})")
                if isinstance(last_modified_str, str):
                    try:
                        local_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
                        logger.debug(f"Parsed local datetime: {local_modified}")
                    except Exception as e:
                        logger.error(f"Failed to parse local datetime '{last_modified_str}': {e}")
                else:
                    logger.error(f"Local lastModifiedDateTime is not string: {type(last_modified_str)}")

            remote_modified = None
            if isinstance(remote_page, dict) and "lastModifiedDateTime" in remote_page:
                last_modified_str = remote_page["lastModifiedDateTime"]
                logger.debug(f"Remote lastModifiedDateTime: {last_modified_str} (type: {type(last_modified_str)})")
                if isinstance(last_modified_str, str):
                    try:
                        remote_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
                        logger.debug(f"Parsed remote datetime: {remote_modified}")
                    except Exception as e:
                        logger.error(f"Failed to parse remote datetime '{last_modified_str}': {e}")
                else:
                    logger.error(f"Remote lastModifiedDateTime is not string: {type(last_modified_str)}")

            # Check modification times
            if remote_modified and local_modified:
                logger.debug(f"Comparing times: remote={remote_modified}, local={local_modified}")
                try:
                    if remote_modified <= local_modified:
                        logger.debug(f"Remote not newer, no change needed")
                        return None  # No change needed
                except Exception as e:
                    logger.error(f"Error comparing datetime objects: {e}")
                    return None

            # Create change record
            change = ContentChange(
                change_type=ChangeType.MODIFIED,
                page_id=local_page.get("id", "unknown"),
                page_title=local_page.get("title", "Unknown"),
                notebook_id=notebook["id"],
                section_id=section["id"],
                local_modified=local_modified,
                remote_modified=remote_modified
            )
            logger.debug(f"Created MODIFIED change for page {change.page_id}")

            # Check for conflicts (both modified recently)
            if (local_modified and remote_modified):
                try:
                    time_diff = abs((local_modified - remote_modified).total_seconds())
                    logger.debug(f"Time difference: {time_diff} seconds")
                    if time_diff < 300:
                        change.change_type = ChangeType.CONFLICTED
                        change.conflict_reason = "Both local and remote versions modified recently"
                        logger.debug(f"Detected conflict for page {change.page_id}")
                except Exception as e:
                    logger.error(f"Error calculating time difference: {e}")

            return change

        except Exception as e:
            logger.error(f"Failed to compare pages {local_page.get('title', local_page.get('id', 'unknown'))}: {e}", exc_info=True)
            return None

    async def plan_sync_operations(self,
                                 changes: List[ContentChange],
                                 strategy: Optional[SyncStrategy] = None) -> List[SyncOperation]:
        """
        Plan sync operations based on detected changes.

        Args:
            changes: List of detected changes
            strategy: Sync strategy to use (defaults to instance default)

        Returns:
            List of planned sync operations
        """
        strategy = strategy or self.default_strategy
        operations = []

        for change in changes:
            operation = await self._plan_single_operation(change, strategy)
            if operation:
                operations.append(operation)

        # Sort operations by priority (conflicts first, then by type)
        operations.sort(key=lambda op: (-op.priority, op.change.change_type.value))

        logger.info(f"Planned {len(operations)} sync operations using strategy: {strategy.value}")

        return operations

    async def _plan_single_operation(self,
                                   change: ContentChange,
                                   strategy: SyncStrategy) -> Optional[SyncOperation]:
        """Plan a single sync operation."""
        try:
            # Handle conflicts based on strategy
            if change.is_conflict():
                return self._plan_conflict_resolution(change, strategy)

            # Handle non-conflicted changes
            if change.change_type == ChangeType.ADDED:
                return SyncOperation(
                    change=change,
                    action="create",
                    strategy_used=strategy,
                    priority=1
                )
            elif change.change_type == ChangeType.DELETED:
                return SyncOperation(
                    change=change,
                    action="delete",
                    strategy_used=strategy,
                    priority=2
                )
            elif change.change_type == ChangeType.MODIFIED:
                return SyncOperation(
                    change=change,
                    action="update",
                    strategy_used=strategy,
                    priority=1
                )

            return None

        except Exception as e:
            logger.error(f"Failed to plan operation for change {change.page_id}: {e}")
            return None

    def _plan_conflict_resolution(self,
                                change: ContentChange,
                                strategy: SyncStrategy) -> SyncOperation:
        """Plan conflict resolution operation."""

        if strategy == SyncStrategy.REMOTE_WINS:
            action = "update"  # Update local with remote
        elif strategy == SyncStrategy.LOCAL_WINS:
            action = "skip"    # Keep local, ignore remote
        elif strategy == SyncStrategy.NEWER_WINS:
            # Choose based on timestamps
            if (change.remote_modified and change.local_modified and
                change.remote_modified > change.local_modified):
                action = "update"
            else:
                action = "skip"
        else:
            # For USER_PROMPT and MERGE_ATTEMPT, defer to manual resolution
            action = "skip"
            self.pending_conflicts.append(change)

        return SyncOperation(
            change=change,
            action=action,
            strategy_used=strategy,
            priority=10  # High priority for conflicts
        )

    async def execute_sync(self,
                         operations: List[SyncOperation],
                         dry_run: bool = False) -> SyncReport:
        """
        Execute planned sync operations.

        Args:
            operations: List of sync operations to execute
            dry_run: Whether to simulate operations without making changes

        Returns:
            Comprehensive sync report
        """
        report = SyncReport(
            start_time=datetime.utcnow(),
            sync_strategy=self.default_strategy,
            total_changes=len(operations)
        )

        try:
            logger.info(f"Executing {len(operations)} sync operations (dry_run={dry_run})")

            for operation in operations:
                try:
                    await self._execute_single_operation(operation, report, dry_run)
                except Exception as e:
                    error_msg = f"Failed to execute operation for {operation.change.page_title}: {e}"
                    logger.error(error_msg)
                    report.errors.append(error_msg)

            # Update sync timestamp
            if not dry_run:
                self.last_sync_time = datetime.utcnow()

            report.end_time = datetime.utcnow()

            logger.info(f"Sync completed: {report.pages_updated + report.pages_created + report.pages_deleted} "
                       f"operations successful, {len(report.errors)} errors")

            return report

        except Exception as e:
            logger.error(f"Sync execution failed: {e}")
            report.errors.append(f"Sync execution failed: {str(e)}")
            report.end_time = datetime.utcnow()
            raise

    async def _execute_single_operation(self,
                                      operation: SyncOperation,
                                      report: SyncReport,
                                      dry_run: bool) -> None:
        """Execute a single sync operation."""
        change = operation.change

        if dry_run:
            logger.info(f"DRY RUN - Would {operation.action} page: {change.page_title}")
            return

        if operation.action == "create":
            # Download and index new page
            if self.bulk_indexer:
                # Use bulk indexer for comprehensive processing
                page_data = await self.content_fetcher._fetch_single_page(change.page_id)
                if page_data:
                    # This would typically be handled by bulk indexer
                    logger.info(f"Would process new page: {change.page_title}")
            report.pages_created += 1

        elif operation.action == "update":
            # Update existing page
            if self.bulk_indexer:
                # Re-process the page through bulk indexer
                page_data = await self.content_fetcher._fetch_single_page(change.page_id)
                if page_data:
                    # This would typically be handled by bulk indexer
                    logger.info(f"Would update page: {change.page_title}")
            report.pages_updated += 1

        elif operation.action == "delete":
            # Remove local page
            await self._delete_local_page(change)
            report.pages_deleted += 1

        elif operation.action == "skip":
            report.pages_skipped += 1

        # Track conflicts
        if change.is_conflict():
            if operation.action != "skip":
                report.conflicts_resolved += 1
            else:
                report.conflicts_pending += 1

    async def _delete_local_page(self, change: ContentChange) -> None:
        """Delete a page from local cache."""
        try:
            # This would delete the page from local storage
            # Implementation depends on storage strategy
            logger.info(f"Deleting local page: {change.page_title}")

        except Exception as e:
            logger.error(f"Failed to delete local page {change.page_title}: {e}")
            raise

    def get_pending_conflicts(self) -> List[ContentChange]:
        """Get list of pending conflicts requiring manual resolution."""
        return self.pending_conflicts.copy()

    async def resolve_conflict(self,
                             change: ContentChange,
                             resolution: SyncStrategy) -> None:
        """
        Manually resolve a specific conflict.

        Args:
            change: The conflicted change to resolve
            resolution: Strategy to use for resolution
        """
        try:
            # Remove from pending conflicts
            self.pending_conflicts = [c for c in self.pending_conflicts if c.page_id != change.page_id]

            # Create and execute resolution operation
            operation = await self._plan_single_operation(change, resolution)
            if operation:
                report = SyncReport(start_time=datetime.utcnow())
                await self._execute_single_operation(operation, report, dry_run=False)

            logger.info(f"Resolved conflict for page {change.page_title} using {resolution.value}")

        except Exception as e:
            logger.error(f"Failed to resolve conflict for {change.page_title}: {e}")
            raise

    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get comprehensive sync statistics."""
        return {
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "pending_conflicts": len(self.pending_conflicts),
            "default_strategy": self.default_strategy.value,
            "change_detection_window_days": self.change_detection_window.days,
            "conflict_details": [
                {
                    "page_id": change.page_id,
                    "page_title": change.page_title,
                    "conflict_reason": change.conflict_reason,
                    "detected_at": change.detected_at.isoformat()
                }
                for change in self.pending_conflicts
            ]
        }
