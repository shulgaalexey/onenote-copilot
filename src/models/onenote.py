"""
Pydantic models for OneNote data structures.

Provides type-safe data models for Microsoft Graph API OneNote responses.
Includes validation, serialization, and data transformation utilities.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, validator


class OneNoteNotebook(BaseModel):
    """
    OneNote notebook model matching Microsoft Graph API response.

    Represents a OneNote notebook with metadata and access information.
    """

    id: str = Field(..., description="Unique notebook identifier")
    display_name: str = Field(..., alias="displayName")
    created_date_time: datetime = Field(..., alias="createdDateTime")
    last_modified_date_time: datetime = Field(..., alias="lastModifiedDateTime")
    is_default: Optional[bool] = Field(None, alias="isDefault")
    user_role: Optional[str] = Field(None, alias="userRole")
    is_shared: Optional[bool] = Field(None, alias="isShared")
    sections_url: Optional[HttpUrl] = Field(None, alias="sectionsUrl")
    section_groups_url: Optional[HttpUrl] = Field(None, alias="sectionGroupsUrl")
    links: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration."""
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            HttpUrl: str
        }


class OneNoteSection(BaseModel):
    """
    OneNote section model matching Microsoft Graph API response.

    Represents a section within a OneNote notebook.
    """

    id: str = Field(..., description="Unique section identifier")
    display_name: str = Field(..., alias="displayName")
    created_date_time: datetime = Field(..., alias="createdDateTime")
    last_modified_date_time: datetime = Field(..., alias="lastModifiedDateTime")
    is_default: Optional[bool] = Field(None, alias="isDefault")
    pages_url: Optional[HttpUrl] = Field(None, alias="pagesUrl")
    parent_notebook: Optional[Dict[str, Any]] = Field(None, alias="parentNotebook")
    parent_section_group: Optional[Dict[str, Any]] = Field(None, alias="parentSectionGroup")

    class Config:
        """Pydantic configuration."""
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            HttpUrl: str
        }


class OneNotePage(BaseModel):
    """
    OneNote page model matching Microsoft Graph API response.

    Represents a single page within a OneNote section with content and metadata.
    """

    id: str = Field(..., description="Unique page identifier")
    title: str = Field(..., description="Page title")
    created_date_time: datetime = Field(..., alias="createdDateTime")
    last_modified_date_time: datetime = Field(..., alias="lastModifiedDateTime")
    content_url: Optional[HttpUrl] = Field(None, alias="contentUrl")
    content: Optional[str] = Field(None, description="HTML content when retrieved")
    text_content: Optional[str] = Field(None, description="Extracted text content for AI processing")
    level: Optional[int] = Field(None, description="Page level in hierarchy")
    order: Optional[int] = Field(None, description="Page order within section")
    links: Dict[str, Any] = Field(default_factory=dict)
    parent_section: Optional[Dict[str, Any]] = Field(None, alias="parentSection")
    parent_notebook: Optional[Dict[str, Any]] = Field(None, alias="parentNotebook")

    class Config:
        """Pydantic configuration."""
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            HttpUrl: str
        }

    @validator('title', pre=True)
    def clean_title(cls, v: str) -> str:
        """Clean and normalize page title."""
        if not v:
            return "Untitled Page"
        # Remove extra whitespace and normalize
        return ' '.join(v.split())

    @property
    def short_content(self) -> str:
        """
        Get a short preview of the page content.

        Returns:
            First 200 characters of text content or title if no content
        """
        if self.text_content:
            content = self.text_content.strip()
            if len(content) > 200:
                return content[:197] + "..."
            return content
        return f"Page: {self.title}"

    @property
    def search_text(self) -> str:
        """
        Get searchable text content combining title and content.

        Returns:
            Combined title and text content for search indexing
        """
        parts = [self.title]
        if self.text_content:
            parts.append(self.text_content)
        return ' '.join(parts)

    def get_notebook_name(self) -> str:
        """
        Get the name of the parent notebook.

        Returns:
            Parent notebook display name or 'Unknown Notebook'
        """
        if self.parent_notebook:
            return self.parent_notebook.get('displayName', 'Unknown Notebook')
        return 'Unknown Notebook'

    def get_section_name(self) -> str:
        """
        Get the name of the parent section.

        Returns:
            Parent section display name or 'Unknown Section'
        """
        if self.parent_section:
            return self.parent_section.get('displayName', 'Unknown Section')
        return 'Unknown Section'


class SearchResult(BaseModel):
    """
    Search result container for OneNote search operations.

    Contains the search query, results, and metadata about the search operation.
    """

    pages: List[OneNotePage] = Field(default_factory=list)
    query: str = Field(..., description="Original search query")
    total_count: int = Field(default=0, description="Total number of results found")
    search_metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_time: Optional[float] = Field(None, description="Search execution time in seconds")
    api_calls_made: int = Field(default=0, description="Number of API calls made")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator('total_count', pre=True)
    def set_total_count(cls, v: int, values: Dict[str, Any]) -> int:
        """Set total count based on pages if not provided."""
        if v == 0 and 'pages' in values:
            return len(values['pages'])
        return v

    @property
    def has_results(self) -> bool:
        """Check if search returned any results."""
        return len(self.pages) > 0

    @property
    def unique_notebooks(self) -> List[str]:
        """Get list of unique notebook names in results."""
        notebooks = set()
        for page in self.pages:
            notebooks.add(page.get_notebook_name())
        return sorted(list(notebooks))

    @property
    def unique_sections(self) -> List[str]:
        """Get list of unique section names in results."""
        sections = set()
        for page in self.pages:
            sections.add(page.get_section_name())
        return sorted(list(sections))

    def get_pages_by_notebook(self, notebook_name: str) -> List[OneNotePage]:
        """
        Get pages filtered by notebook name.

        Args:
            notebook_name: Name of the notebook to filter by

        Returns:
            List of pages in the specified notebook
        """
        return [page for page in self.pages if page.get_notebook_name() == notebook_name]

    def get_pages_by_section(self, section_name: str) -> List[OneNotePage]:
        """
        Get pages filtered by section name.

        Args:
            section_name: Name of the section to filter by

        Returns:
            List of pages in the specified section
        """
        return [page for page in self.pages if page.get_section_name() == section_name]

    def sort_by_relevance(self) -> 'SearchResult':
        """
        Sort pages by relevance (most recent first).

        Returns:
            New SearchResult with pages sorted by last modified date
        """
        sorted_pages = sorted(
            self.pages,
            key=lambda p: p.last_modified_date_time,
            reverse=True
        )

        return SearchResult(
            pages=sorted_pages,
            query=self.query,
            total_count=self.total_count,
            search_metadata=self.search_metadata,
            execution_time=self.execution_time,
            api_calls_made=self.api_calls_made
        )


class OneNoteSearchSummary(BaseModel):
    """
    Summary statistics for OneNote search results.

    Provides aggregated information about search results for display and analysis.
    """

    total_pages: int = Field(default=0)
    unique_notebooks: int = Field(default=0)
    unique_sections: int = Field(default=0)
    date_range: Optional[Dict[str, datetime]] = Field(None)
    most_recent_page: Optional[OneNotePage] = Field(None)
    oldest_page: Optional[OneNotePage] = Field(None)

    @classmethod
    def from_search_result(cls, search_result: SearchResult) -> 'OneNoteSearchSummary':
        """
        Create summary from search result.

        Args:
            search_result: Search result to summarize

        Returns:
            Summary statistics for the search result
        """
        if not search_result.pages:
            return cls()

        # Sort pages by date
        sorted_pages = sorted(search_result.pages, key=lambda p: p.last_modified_date_time)

        # Calculate date range
        oldest_page = sorted_pages[0]
        most_recent_page = sorted_pages[-1]

        date_range = {
            'earliest': oldest_page.last_modified_date_time,
            'latest': most_recent_page.last_modified_date_time
        }

        return cls(
            total_pages=len(search_result.pages),
            unique_notebooks=len(search_result.unique_notebooks),
            unique_sections=len(search_result.unique_sections),
            date_range=date_range,
            most_recent_page=most_recent_page,
            oldest_page=oldest_page
        )
