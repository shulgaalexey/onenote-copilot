"""
Pydantic models for local OneNote cache system.

Provides type-safe data models for local cache metadata, synchronization,
and content management. Extends existing OneNote models for local storage.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .onenote import OneNotePage


class SyncType(str, Enum):
    """Types of synchronization operations."""
    FULL = "full"
    INCREMENTAL = "incremental"
    FORCE = "force"


class SyncStatus(str, Enum):
    """Status of synchronization operations."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ContentChangeType(str, Enum):
    """Types of content changes during sync."""
    ADDED = "added"
    UPDATED = "updated"
    DELETED = "deleted"
    NO_CHANGE = "no_change"


class DownloadStatus(str, Enum):
    """Status of asset download operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"


class AssetInfo(BaseModel):
    """Information about an asset (image, file) to be downloaded."""

    type: str = Field(..., description="Asset type (image, file)")
    original_url: str = Field(..., description="Original OneNote resource URL")
    local_path: str = Field(..., description="Local file path for storage")
    filename: str = Field(..., description="Original filename")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type of the asset")
    download_status: str = Field(default="pending", description="Download status")


class InternalLink(BaseModel):
    """Information about internal OneNote page links."""

    target_page_id: str = Field(..., description="ID of the linked page")
    target_page_title: Optional[str] = Field(None, description="Title of linked page")
    link_text: str = Field(..., description="Display text of the link")
    markdown_link: Optional[str] = Field(None, description="Generated markdown link")
    original_url: str = Field(..., description="Original OneNote link URL")


class ExternalLink(BaseModel):
    """Information about external links."""

    url: str = Field(..., description="External URL")
    link_text: str = Field(..., description="Display text of the link")
    title: Optional[str] = Field(None, description="Link title attribute")


class LinkInfo(BaseModel):
    """Information about a link found in content."""

    original_url: str = Field(..., description="Original URL from the content")
    resolved_path: str = Field(default="", description="Resolved local path")
    link_text: str = Field(..., description="Display text of the link")
    link_type: str = Field(..., description="Type of link (page, section, external)")
    resolution_status: str = Field(default="pending", description="Resolution status")
    error_message: Optional[str] = Field(None, description="Error message if resolution failed")


class MarkdownConversionResult(BaseModel):
    """Result of HTML to Markdown conversion."""

    success: bool = Field(default=False, description="Whether conversion succeeded")
    original_html: str = Field(default="", description="Original HTML content")
    markdown_content: str = Field(default="", description="Converted markdown content")

    # Conversion statistics
    elements_converted: int = Field(default=0, description="Number of HTML elements converted")
    assets_linked: int = Field(default=0, description="Number of assets linked")
    internal_links_resolved: int = Field(default=0, description="Number of internal links resolved")
    external_links_preserved: int = Field(default=0, description="Number of external links preserved")

    # Issues and warnings
    warnings: List[str] = Field(default_factory=list, description="Conversion warnings")
    error: Optional[str] = Field(None, description="Error message if conversion failed")

    # Timing
    conversion_time_seconds: float = Field(default=0.0, description="Time taken for conversion")


class LinkResolutionResult(BaseModel):
    """Result of link resolution operations."""

    success: bool = Field(default=False, description="Whether resolution succeeded")
    total_links: int = Field(default=0, description="Total number of links to resolve")
    resolved_count: int = Field(default=0, description="Number of successfully resolved links")
    failed_count: int = Field(default=0, description="Number of failed resolutions")

    # Results
    resolved_links: List[LinkInfo] = Field(default_factory=list, description="Successfully resolved links")
    failed_links: List[LinkInfo] = Field(default_factory=list, description="Failed link resolutions")

    # Error information
    error: Optional[str] = Field(None, description="Error message if batch resolution failed")


class AssetDownloadResult(BaseModel):
    """Result of asset download operations."""

    status: DownloadStatus = Field(default=DownloadStatus.PENDING, description="Overall download status")
    total_assets: int = Field(default=0, description="Total number of assets to download")
    successful_count: int = Field(default=0, description="Number of successful downloads")
    failed_count: int = Field(default=0, description="Number of failed downloads")
    total_bytes: int = Field(default=0, description="Total bytes downloaded")

    # Detailed results
    successful_downloads: List[Dict[str, Any]] = Field(default_factory=list, description="List of successful downloads")
    failed_downloads: List[Dict[str, Any]] = Field(default_factory=list, description="List of failed downloads with error info")

    # Timing
    started_at: Optional[datetime] = Field(None, description="Download start time")
    completed_at: Optional[datetime] = Field(None, description="Download completion time")

    @property
    def duration_seconds(self) -> float:
        """Get download duration in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_assets == 0:
            return 0.0
        return (self.successful_count / self.total_assets) * 100.0

    @property
    def success(self) -> bool:
        """Check if all downloads were successful."""
        return self.status == DownloadStatus.COMPLETED and self.failed_count == 0


class CachedPageMetadata(BaseModel):
    """Extended metadata for cached OneNote pages."""

    # Core page information (from OneNotePage)
    id: str = Field(..., description="OneNote page ID")
    title: str = Field(..., description="Page title")
    created_date_time: datetime = Field(..., description="Page creation date")
    last_modified_date_time: datetime = Field(..., description="Page last modified date")

    # Parent structure
    parent_section: Dict[str, Any] = Field(..., description="Parent section info")
    parent_notebook: Dict[str, Any] = Field(..., description="Parent notebook info")

    # Cache-specific metadata
    content_url: str = Field(..., description="Original OneNote content URL")
    local_content_path: str = Field(..., description="Local markdown file path")
    local_html_path: str = Field(..., description="Local HTML file path")

    # Assets and links
    attachments: List[AssetInfo] = Field(default_factory=list)
    internal_links: List[InternalLink] = Field(default_factory=list)
    external_links: List[ExternalLink] = Field(default_factory=list)

    # Cache timestamps
    cached_at: datetime = Field(default_factory=datetime.utcnow)
    last_synced: datetime = Field(default_factory=datetime.utcnow)

    # Status flags
    content_downloaded: bool = Field(default=False)
    markdown_converted: bool = Field(default=False)
    assets_downloaded: bool = Field(default=False)
    links_resolved: bool = Field(default=False)

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
        }
    )


class CachedPage(BaseModel):
    """A cached OneNote page with content and metadata."""

    metadata: CachedPageMetadata = Field(..., description="Page metadata")
    content: Optional[str] = Field(None, description="Original HTML content")
    markdown_content: Optional[str] = Field(None, description="Converted markdown content")
    text_content: Optional[str] = Field(None, description="Extracted text content")

    @property
    def id(self) -> str:
        """Get page ID."""
        return self.metadata.id

    @property
    def title(self) -> str:
        """Get page title."""
        return self.metadata.title

    @property
    def last_modified(self) -> datetime:
        """Get last modified date."""
        return self.metadata.last_modified_date_time

    def to_onenote_page(self) -> OneNotePage:
        """Convert to OneNotePage model for compatibility."""
        return OneNotePage(
            id=self.metadata.id,
            title=self.metadata.title,
            created_date_time=self.metadata.created_date_time,
            last_modified_date_time=self.metadata.last_modified_date_time,
            content_url=self.metadata.content_url,
            content=self.content,
            text_content=self.text_content,
            processed_content=self.text_content,
            parent_section=self.metadata.parent_section,
            parent_notebook=self.metadata.parent_notebook
        )


class NotebookMetadata(BaseModel):
    """Metadata for a cached notebook."""

    id: str = Field(..., description="Notebook ID")
    display_name: str = Field(..., description="Notebook display name")
    created_date_time: datetime = Field(..., description="Creation date")
    last_modified_date_time: datetime = Field(..., description="Last modified date")
    is_default: Optional[bool] = Field(None, description="Is default notebook")

    # Cache-specific
    cached_at: datetime = Field(default_factory=datetime.utcnow)
    section_count: int = Field(default=0, description="Number of sections")
    page_count: int = Field(default=0, description="Total number of pages")


class SectionMetadata(BaseModel):
    """Metadata for a cached section."""

    id: str = Field(..., description="Section ID")
    display_name: str = Field(..., description="Section display name")
    created_date_time: datetime = Field(..., description="Creation date")
    last_modified_date_time: datetime = Field(..., description="Last modified date")
    parent_notebook_id: str = Field(..., description="Parent notebook ID")

    # Cache-specific
    cached_at: datetime = Field(default_factory=datetime.utcnow)
    page_count: int = Field(default=0, description="Number of pages")


class SyncStatistics(BaseModel):
    """Statistics from a sync operation."""

    pages_added: int = Field(default=0)
    pages_updated: int = Field(default=0)
    pages_deleted: int = Field(default=0)
    pages_unchanged: int = Field(default=0)
    images_downloaded: int = Field(default=0)
    files_downloaded: int = Field(default=0)
    errors_encountered: int = Field(default=0)
    total_api_calls: int = Field(default=0)
    total_time_seconds: float = Field(default=0.0)


class CacheMetadata(BaseModel):
    """Metadata for the entire cache for a user."""

    cache_version: str = Field(default="1.0.0", description="Cache format version")
    user_id: str = Field(..., description="User identifier")

    # Sync timestamps
    cache_created: datetime = Field(default_factory=datetime.utcnow)
    last_full_sync: Optional[datetime] = Field(None, description="Last full sync timestamp")
    last_incremental_sync: Optional[datetime] = Field(None, description="Last incremental sync")

    # Content counts
    total_notebooks: int = Field(default=0)
    total_sections: int = Field(default=0)
    total_pages: int = Field(default=0)
    total_size_mb: float = Field(default=0.0)

    # Sync statistics from last sync
    sync_statistics: SyncStatistics = Field(default_factory=SyncStatistics)

    # Cache configuration
    cache_root_path: str = Field(..., description="Root path of the cache")
    sync_enabled: bool = Field(default=True)
    auto_sync_interval_hours: int = Field(default=24)

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
        }
    )


class ContentChange(BaseModel):
    """Represents a detected change in OneNote content."""

    page_id: str = Field(..., description="ID of changed page")
    change_type: ContentChangeType = Field(..., description="Type of change")
    remote_modified: datetime = Field(..., description="Remote modification timestamp")
    local_modified: Optional[datetime] = Field(None, description="Local modification timestamp")
    title: str = Field(..., description="Page title")
    notebook_name: str = Field(..., description="Parent notebook name")
    section_name: str = Field(..., description="Parent section name")


class SyncConflict(BaseModel):
    """Represents a conflict between local and remote content."""

    page_id: str = Field(..., description="ID of conflicted page")
    conflict_type: str = Field(..., description="Type of conflict")
    local_modified: datetime = Field(..., description="Local modification timestamp")
    remote_modified: datetime = Field(..., description="Remote modification timestamp")
    description: str = Field(..., description="Conflict description")


class ConflictResolution(BaseModel):
    """Resolution strategy for a sync conflict."""

    conflict: SyncConflict = Field(..., description="The conflict being resolved")
    resolution_strategy: str = Field(..., description="Resolution strategy chosen")
    resolved_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = Field(None, description="Additional notes")


class SyncResult(BaseModel):
    """Result of a synchronization operation."""

    sync_type: SyncType = Field(..., description="Type of sync performed")
    status: SyncStatus = Field(..., description="Sync completion status")
    started_at: datetime = Field(..., description="Sync start time")
    completed_at: Optional[datetime] = Field(None, description="Sync completion time")

    # Changes detected and applied
    changes_detected: List[ContentChange] = Field(default_factory=list)
    conflicts_found: List[SyncConflict] = Field(default_factory=list)
    conflicts_resolved: List[ConflictResolution] = Field(default_factory=list)

    # Statistics
    statistics: SyncStatistics = Field(default_factory=SyncStatistics)

    # Error information
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Get sync duration in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def success(self) -> bool:
        """Check if sync was successful."""
        return self.status in [SyncStatus.COMPLETED, SyncStatus.PARTIAL]


class DownloadResult(BaseModel):
    """Result of downloading an asset or content."""

    success: bool = Field(..., description="Whether download succeeded")
    local_path: Optional[str] = Field(None, description="Local file path if successful")
    size_bytes: Optional[int] = Field(None, description="Downloaded file size")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    download_time_seconds: float = Field(default=0.0)
    retries_attempted: int = Field(default=0)


class ConversionResult(BaseModel):
    """Result of HTML to Markdown conversion."""

    success: bool = Field(..., description="Whether conversion succeeded")
    markdown_content: Optional[str] = Field(None, description="Converted markdown content")
    assets_processed: List[AssetInfo] = Field(default_factory=list)
    links_processed: LinkResolutionResult = Field(default_factory=LinkResolutionResult)
    warnings: List[str] = Field(default_factory=list)
    conversion_time_seconds: float = Field(default=0.0)


class CacheSyncResult(BaseModel):
    """High-level result of a cache synchronization operation."""

    user_id: str = Field(..., description="User ID that was synced")
    sync_result: SyncResult = Field(..., description="Detailed sync result")
    cache_updated: bool = Field(..., description="Whether cache was updated")
    new_cache_metadata: CacheMetadata = Field(..., description="Updated cache metadata")


class CacheStatistics(BaseModel):
    """Statistics about the local cache."""

    user_id: str = Field(..., description="User ID")
    total_notebooks: int = Field(default=0)
    total_sections: int = Field(default=0)
    total_pages: int = Field(default=0)
    total_images: int = Field(default=0)
    total_files: int = Field(default=0)

    # Storage statistics
    total_size_bytes: int = Field(default=0)
    markdown_size_bytes: int = Field(default=0)
    assets_size_bytes: int = Field(default=0)

    # Sync statistics
    last_sync: Optional[datetime] = Field(None)
    sync_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # Performance statistics
    average_search_time_ms: float = Field(default=0.0)
    cache_hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
        }
    )


class CleanupResult(BaseModel):
    """Result of cache cleanup operations."""

    orphaned_assets_removed: int = Field(default=0)
    deleted_pages_cleaned: int = Field(default=0)
    space_freed_bytes: int = Field(default=0)
    cleanup_time_seconds: float = Field(default=0.0)
    errors: List[str] = Field(default_factory=list)

    @property
    def space_freed_mb(self) -> float:
        """Get space freed in megabytes."""
        return self.space_freed_bytes / (1024 * 1024)


# Search-related models for local cache search
class CacheSearchResult(BaseModel):
    """Search result from local cache."""

    pages: List[CachedPage] = Field(default_factory=list)
    query: str = Field(..., description="Original search query")
    total_count: int = Field(default=0)
    search_time_ms: float = Field(default=0.0)
    search_type: str = Field(..., description="Type of search performed")

    @property
    def has_results(self) -> bool:
        """Check if search has results."""
        return len(self.pages) > 0


class SearchMatch(BaseModel):
    """Individual search match with score."""

    page: CachedPage = Field(..., description="Matched page")
    score: float = Field(..., description="Match score", ge=0.0, le=1.0)
    match_type: str = Field(..., description="Type of match (title, content, etc.)")
    snippet: Optional[str] = Field(None, description="Relevant content snippet")


class PageMatch(BaseModel):
    """Page match for title or metadata searches."""

    page: CachedPage = Field(..., description="Matched page")
    match_score: float = Field(..., description="Match confidence", ge=0.0, le=1.0)
    match_reason: str = Field(..., description="Why this page matched")


class RelatedPage(BaseModel):
    """Page related through links or content similarity."""

    page: CachedPage = Field(..., description="Related page")
    relation_type: str = Field(..., description="Type of relationship")
    relation_score: float = Field(..., description="Strength of relationship", ge=0.0, le=1.0)
    relation_description: str = Field(..., description="Description of relationship")
