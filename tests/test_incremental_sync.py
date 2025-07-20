"""
Tests for incremental sync manager.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from tempfile import TemporaryDirectory

from src.storage.incremental_sync import (
    IncrementalSyncManager, ContentChange, SyncOperation, SyncReport,
    SyncStrategy, ChangeType
)
from src.models.onenote import OneNoteNotebook, OneNoteSection, OneNotePage
from src.storage.onenote_fetcher import OneNoteContentFetcher


class TestIncrementalSyncManager:
    """Test incremental sync manager functionality."""

    @pytest.fixture
    def mock_content_fetcher(self):
        """Create mock content fetcher."""
        fetcher = AsyncMock(spec=OneNoteContentFetcher)
        return fetcher

    @pytest.fixture
    def mock_bulk_indexer(self):
        """Create mock bulk indexer."""
        return AsyncMock()

    @pytest.fixture
    def temp_cache_root(self):
        """Create temporary cache root directory."""
        with TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def sync_manager(self, temp_cache_root, mock_content_fetcher, mock_bulk_indexer):
        """Create sync manager instance."""
        mock_cache_manager = AsyncMock()
        return IncrementalSyncManager(
            cache_root=temp_cache_root,
            content_fetcher=mock_content_fetcher,
            cache_manager=mock_cache_manager,
            bulk_indexer=mock_bulk_indexer,
            default_strategy=SyncStrategy.NEWER_WINS
        )

    @pytest.fixture
    def sample_notebook(self):
        """Create sample notebook."""
        return {
            "id": "notebook-1",
            "displayName": "Test Notebook",
            "createdDateTime": datetime.utcnow().isoformat(),
            "lastModifiedDateTime": datetime.utcnow().isoformat()
        }

    @pytest.fixture
    def sample_section(self):
        """Create sample section."""
        return {
            "id": "section-1", 
            "displayName": "Test Section",
            "createdDateTime": datetime.utcnow().isoformat(),
            "lastModifiedDateTime": datetime.utcnow().isoformat()
        }

    @pytest.fixture
    def sample_page(self):
        """Create sample page."""
        return {
            "id": "page-1",
            "title": "Test Page",
            "createdDateTime": datetime.utcnow().isoformat(),
            "lastModifiedDateTime": datetime.utcnow().isoformat(),
            "contentUrl": "https://example.com/page1"
        }

    def test_initialization(self, sync_manager, temp_cache_root):
        """Test sync manager initialization."""
        assert sync_manager.cache_root == temp_cache_root
        assert sync_manager.default_strategy == SyncStrategy.NEWER_WINS
        assert sync_manager.last_sync_time is None
        assert sync_manager.pending_conflicts == []

    @pytest.mark.asyncio
    async def test_detect_changes_empty(self, sync_manager, mock_content_fetcher):
        """Test change detection with no content."""
        # Setup empty notebooks
        mock_content_fetcher._get_all_notebooks.return_value = []
        
        changes = await sync_manager.detect_changes(user_id="test-user")
        
        assert changes == []
        mock_content_fetcher._get_all_notebooks.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_changes_new_pages(self, sync_manager, mock_content_fetcher,
                                          sample_notebook, sample_section, sample_page):
        """Test detection of new pages."""
        # Setup mock data
        mock_content_fetcher._get_all_notebooks.return_value = [sample_notebook]
        mock_content_fetcher._get_all_sections.return_value = [sample_section]
        mock_content_fetcher._get_pages_from_section.return_value = [sample_page]
        
        # Mock local pages (empty)
        with patch.object(sync_manager, '_get_local_pages', return_value=[]):
            changes = await sync_manager.detect_changes(user_id="test-user")
        
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.ADDED
        assert changes[0].page_id == sample_page["id"]
        assert changes[0].page_title == sample_page["title"]

    @pytest.mark.asyncio
    async def test_detect_changes_modified_pages(self, sync_manager, mock_content_fetcher,
                                               sample_notebook, sample_section):
        """Test detection of modified pages."""
        # Create local and remote versions with different timestamps
        local_page = {
            "id": "page-1",
            "title": "Test Page",
            "createdDateTime": datetime.utcnow().isoformat(),
            "lastModifiedDateTime": (datetime.utcnow() - timedelta(hours=2)).isoformat()
        }
        
        remote_page = {
            "id": "page-1",
            "title": "Test Page",
            "createdDateTime": datetime.utcnow().isoformat(),
            "lastModifiedDateTime": (datetime.utcnow() - timedelta(hours=1)).isoformat()  # More recent
        }
        
        # Setup mock data
        mock_content_fetcher._get_all_notebooks.return_value = [sample_notebook]
        mock_content_fetcher._get_all_sections.return_value = [sample_section]
        mock_content_fetcher._get_pages_from_section.return_value = [remote_page]
        
        # Mock local pages
        with patch.object(sync_manager, '_get_local_pages', return_value=[local_page]):
            changes = await sync_manager.detect_changes(user_id="test-user")
        
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.MODIFIED
        assert changes[0].page_id == "page-1"

    @pytest.mark.asyncio
    async def test_detect_changes_deleted_pages(self, sync_manager, mock_content_fetcher,
                                              sample_notebook, sample_section):
        """Test detection of deleted pages."""
        # Create local page that doesn't exist remotely
        local_page = {
            "id": "page-1",
            "title": "Deleted Page",
            "createdDateTime": datetime.utcnow().isoformat(),
            "lastModifiedDateTime": datetime.utcnow().isoformat()
        }
        
        # Setup mock data (empty remote pages)
        mock_content_fetcher._get_all_notebooks.return_value = [sample_notebook]
        mock_content_fetcher._get_all_sections.return_value = [sample_section]
        mock_content_fetcher._get_pages_from_section.return_value = []
        
        # Mock local pages
        with patch.object(sync_manager, '_get_local_pages', return_value=[local_page]):
            changes = await sync_manager.detect_changes(user_id="test-user")
        
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.DELETED
        assert changes[0].page_id == "page-1"

    @pytest.mark.asyncio
    async def test_detect_changes_conflicts(self, sync_manager, mock_content_fetcher,
                                          sample_notebook, sample_section):
        """Test detection of conflicting changes."""
        base_time = datetime.utcnow()
        
        # Create pages modified within conflict window (5 minutes)
        local_page = {
            "id": "page-1",
            "title": "Conflicted Page",
            "createdDateTime": base_time.isoformat(),
            "lastModifiedDateTime": base_time.isoformat()
        }
        
        remote_page = {
            "id": "page-1",
            "title": "Conflicted Page",
            "createdDateTime": base_time.isoformat(),
            "lastModifiedDateTime": (base_time + timedelta(minutes=2)).isoformat()  # Within conflict window
        }
        
        # Setup mock data
        mock_content_fetcher._get_all_notebooks.return_value = [sample_notebook]
        mock_content_fetcher._get_all_sections.return_value = [sample_section]
        mock_content_fetcher._get_pages_from_section.return_value = [remote_page]
        
        # Mock local pages
        with patch.object(sync_manager, '_get_local_pages', return_value=[local_page]):
            changes = await sync_manager.detect_changes(user_id="test-user")
        
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.CONFLICTED
        assert "modified recently" in changes[0].conflict_reason

    @pytest.mark.asyncio
    async def test_plan_sync_operations_basic(self, sync_manager):
        """Test basic sync operation planning."""
        changes = [
            ContentChange(
                change_type=ChangeType.ADDED,
                page_id="page-1",
                page_title="New Page",
                notebook_id="notebook-1",
                section_id="section-1"
            ),
            ContentChange(
                change_type=ChangeType.MODIFIED,
                page_id="page-2",
                page_title="Modified Page",
                notebook_id="notebook-1",
                section_id="section-1"
            )
        ]
        
        operations = await sync_manager.plan_sync_operations(changes)
        
        assert len(operations) == 2
        assert operations[0].action in ["create", "update"]
        assert operations[1].action in ["create", "update"]

    @pytest.mark.asyncio
    async def test_plan_sync_operations_conflicts(self, sync_manager):
        """Test conflict resolution in operation planning."""
        conflict_change = ContentChange(
            change_type=ChangeType.CONFLICTED,
            page_id="page-1",
            page_title="Conflicted Page",
            notebook_id="notebook-1",
            section_id="section-1",
            conflict_reason="Both versions modified"
        )
        
        # Test REMOTE_WINS strategy
        sync_manager.default_strategy = SyncStrategy.REMOTE_WINS
        operations = await sync_manager.plan_sync_operations([conflict_change])
        
        assert len(operations) == 1
        assert operations[0].action == "update"  # Remote wins, so update local

    @pytest.mark.asyncio
    async def test_execute_sync_dry_run(self, sync_manager):
        """Test sync execution in dry run mode."""
        operations = [
            SyncOperation(
                change=ContentChange(
                    change_type=ChangeType.ADDED,
                    page_id="page-1",
                    page_title="New Page",
                    notebook_id="notebook-1",
                    section_id="section-1"
                ),
                action="create",
                strategy_used=SyncStrategy.NEWER_WINS
            )
        ]
        
        report = await sync_manager.execute_sync(operations, dry_run=True)
        
        assert report.total_changes == 1
        assert len(report.errors) == 0
        assert report.get_duration() is not None

    @pytest.mark.asyncio
    async def test_execute_sync_real_operations(self, sync_manager, mock_content_fetcher):
        """Test actual sync execution."""
        # Mock page content fetching
        mock_content_fetcher._fetch_single_page.return_value = {"id": "page-1", "title": "Test"}
        
        operations = [
            SyncOperation(
                change=ContentChange(
                    change_type=ChangeType.ADDED,
                    page_id="page-1",
                    page_title="New Page",
                    notebook_id="notebook-1",
                    section_id="section-1"
                ),
                action="create",
                strategy_used=SyncStrategy.NEWER_WINS
            )
        ]
        
        report = await sync_manager.execute_sync(operations, dry_run=False)
        
        assert report.pages_created == 1
        assert len(report.errors) == 0

    def test_content_change_is_conflict(self):
        """Test conflict detection in ContentChange."""
        # Non-conflicted change
        change1 = ContentChange(
            change_type=ChangeType.MODIFIED,
            page_id="page-1",
            page_title="Page",
            notebook_id="notebook-1",
            section_id="section-1"
        )
        assert not change1.is_conflict()
        
        # Conflicted change (by type)
        change2 = ContentChange(
            change_type=ChangeType.CONFLICTED,
            page_id="page-1",
            page_title="Page",
            notebook_id="notebook-1",
            section_id="section-1"
        )
        assert change2.is_conflict()
        
        # Conflicted change (by reason)
        change3 = ContentChange(
            change_type=ChangeType.MODIFIED,
            page_id="page-1",
            page_title="Page",
            notebook_id="notebook-1",
            section_id="section-1",
            conflict_reason="Manual conflict"
        )
        assert change3.is_conflict()

    def test_sync_report_metrics(self):
        """Test sync report metrics calculation."""
        report = SyncReport(
            start_time=datetime.utcnow(),
            pages_updated=5,
            pages_created=3,
            pages_deleted=1
        )
        report.errors = ["error1", "error2"]
        report.end_time = report.start_time + timedelta(minutes=5)
        
        # Test duration calculation
        duration = report.get_duration()
        assert duration == timedelta(minutes=5)
        
        # Test success rate calculation
        success_rate = report.get_success_rate()
        expected_rate = ((5 + 3 + 1) / (5 + 3 + 1 + 2)) * 100
        assert success_rate == expected_rate

    def test_get_pending_conflicts(self, sync_manager):
        """Test getting pending conflicts."""
        conflict = ContentChange(
            change_type=ChangeType.CONFLICTED,
            page_id="page-1",
            page_title="Conflicted Page",
            notebook_id="notebook-1",
            section_id="section-1"
        )
        
        sync_manager.pending_conflicts = [conflict]
        
        conflicts = sync_manager.get_pending_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].page_id == "page-1"
        
        # Ensure it returns a copy
        conflicts.clear()
        assert len(sync_manager.pending_conflicts) == 1

    @pytest.mark.asyncio
    async def test_resolve_conflict_manual(self, sync_manager):
        """Test manual conflict resolution."""
        conflict = ContentChange(
            change_type=ChangeType.CONFLICTED,
            page_id="page-1",
            page_title="Conflicted Page",
            notebook_id="notebook-1",
            section_id="section-1"
        )
        
        sync_manager.pending_conflicts = [conflict]
        
        with patch.object(sync_manager, '_execute_single_operation', new_callable=AsyncMock):
            await sync_manager.resolve_conflict(conflict, SyncStrategy.REMOTE_WINS)
        
        # Conflict should be removed from pending list
        assert len(sync_manager.pending_conflicts) == 0

    def test_get_sync_statistics(self, sync_manager):
        """Test sync statistics reporting."""
        # Set some state
        sync_manager.last_sync_time = datetime.utcnow()
        sync_manager.pending_conflicts = [
            ContentChange(
                change_type=ChangeType.CONFLICTED,
                page_id="page-1",
                page_title="Conflicted Page",
                notebook_id="notebook-1",
                section_id="section-1",
                conflict_reason="Test conflict"
            )
        ]
        
        stats = sync_manager.get_sync_statistics()
        
        assert stats["last_sync_time"] is not None
        assert stats["pending_conflicts"] == 1
        assert stats["default_strategy"] == SyncStrategy.NEWER_WINS.value
        assert len(stats["conflict_details"]) == 1
        assert stats["conflict_details"][0]["page_id"] == "page-1"

    @pytest.mark.asyncio
    async def test_force_full_scan(self, sync_manager, mock_content_fetcher,
                                 sample_notebook, sample_section):
        """Test forcing full scan regardless of timestamps."""
        # Set last sync time to recent
        sync_manager.last_sync_time = datetime.utcnow() - timedelta(minutes=5)
        
        old_page = {
            "id": "page-1",
            "title": "Old Page",
            "createdDateTime": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "lastModifiedDateTime": (datetime.utcnow() - timedelta(days=30)).isoformat()  # Very old
        }
        
        # Setup mock data
        mock_content_fetcher._get_all_notebooks.return_value = [sample_notebook]
        mock_content_fetcher._get_all_sections.return_value = [sample_section]
        mock_content_fetcher._get_pages_from_section.return_value = [old_page]
        
        # Mock local pages (empty)
        with patch.object(sync_manager, '_get_local_pages', return_value=[]):
            # Normal scan should filter out old page
            changes_normal = await sync_manager.detect_changes(user_id="test-user", force_full_scan=False)
            
            # Force full scan should include old page
            changes_full = await sync_manager.detect_changes(user_id="test-user", force_full_scan=True)
        
        # With force_full_scan=True, should detect the old page
        assert len(changes_full) >= len(changes_normal)

    @pytest.mark.asyncio
    async def test_error_handling_in_detection(self, sync_manager, mock_content_fetcher):
        """Test error handling during change detection."""
        # Make _get_all_notebooks raise an exception
        mock_content_fetcher._get_all_notebooks.side_effect = Exception("Network error")
        
        with pytest.raises(Exception, match="Network error"):
            await sync_manager.detect_changes(user_id="test-user")

    @pytest.mark.asyncio
    async def test_error_handling_in_execution(self, sync_manager):
        """Test error handling during sync execution."""
        operations = [
            SyncOperation(
                change=ContentChange(
                    change_type=ChangeType.ADDED,
                    page_id="page-1",
                    page_title="New Page",
                    notebook_id="notebook-1",
                    section_id="section-1"
                ),
                action="create",
                strategy_used=SyncStrategy.NEWER_WINS
            )
        ]
        
        # Mock _execute_single_operation to raise exception
        with patch.object(sync_manager, '_execute_single_operation', side_effect=Exception("Sync error")):
            report = await sync_manager.execute_sync(operations)
        
        assert len(report.errors) == 1
        assert "Sync error" in report.errors[0]
