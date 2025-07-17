"""
Pydantic models for OneNote data structures.

Provides type-safe data models for Microsoft Graph API OneNote responses.
Includes validation, serialization, and data transformation utilities.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import (BaseModel, ConfigDict, Field, HttpUrl, field_validator,
                      model_validator)


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

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            HttpUrl: str
        }
    )


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

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            HttpUrl: str
        }
    )


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
    processed_content: Optional[str] = Field(None, description="Processed text content for chunking")
    level: Optional[int] = Field(None, description="Page level in hierarchy")
    order: Optional[int] = Field(None, description="Page order within section")
    links: Dict[str, Any] = Field(default_factory=dict)
    parent_section: Optional[Dict[str, Any]] = Field(None, alias="parentSection")
    parent_notebook: Optional[Dict[str, Any]] = Field(None, alias="parentNotebook")

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            HttpUrl: str
        }
    )

    @field_validator('title', mode='before')
    @classmethod
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

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )

    @model_validator(mode='after')
    def set_total_count(self) -> 'SearchResult':
        """Set total count based on pages if not provided."""
        if self.total_count == 0 and self.pages:
            self.total_count = len(self.pages)
        return self

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


class ContentChunk(BaseModel):
    """
    A chunk of OneNote content with metadata for embedding.

    Represents a segmented piece of content that can be embedded and searched.
    """

    id: str = Field(..., description="Unique chunk identifier")
    page_id: str = Field(..., description="OneNote page ID this chunk belongs to")
    page_title: str = Field(..., description="Title of the source page")
    content: str = Field(..., description="The actual text content of the chunk")
    chunk_index: int = Field(..., description="Index of this chunk within the page", ge=0)
    start_position: int = Field(..., description="Start character position in original content", ge=0)
    end_position: int = Field(..., description="End character position in original content", ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional chunk metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When chunk was created")

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


class EmbeddedChunk(BaseModel):
    """
    A content chunk with its vector embedding.

    Extends ContentChunk with embedding vector for semantic search.
    """

    chunk: ContentChunk = Field(..., description="The content chunk")
    embedding: List[float] = Field(..., description="Vector embedding of the chunk content")
    embedding_model: str = Field(..., description="Model used to generate the embedding")
    embedding_dimensions: int = Field(..., description="Dimension count of the embedding vector")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When embedding was created")

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimensions(cls, v: List[float]) -> List[float]:
        """Validate embedding vector is not empty."""
        if not v:
            raise ValueError("Embedding vector cannot be empty")
        return v

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


class SemanticSearchResult(BaseModel):
    """
    Result from semantic search with similarity scores.

    Represents a chunk found through semantic search with relevance scoring.
    """

    chunk: ContentChunk = Field(..., description="The matching content chunk")
    similarity_score: float = Field(..., description="Cosine similarity score", ge=0.0, le=1.0)
    search_type: str = Field(..., description="Type of search that found this result")
    rank: int = Field(..., description="Ranking position in results", ge=1)
    page: Optional[OneNotePage] = Field(None, description="Full page data if available")

    model_config = ConfigDict(populate_by_name=True)


class QueryIntent(BaseModel):
    """
    Processed user query with intent analysis.

    Represents the analyzed intent and context of a user search query.
    """

    original_query: str = Field(..., description="Original user query")
    processed_query: str = Field(..., description="Processed/cleaned query")
    intent_type: str = Field(..., description="Detected intent type (search, content, question, etc.)")
    confidence: float = Field(..., description="Confidence in intent detection", ge=0.0, le=1.0)
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    temporal_filters: Dict[str, Any] = Field(default_factory=dict, description="Date/time filters if any")
    content_filters: Dict[str, Any] = Field(default_factory=dict, description="Content type filters")
    suggested_alternatives: List[str] = Field(default_factory=list, description="Alternative query suggestions")

    model_config = ConfigDict(populate_by_name=True)


class HybridSearchResult(BaseModel):
    """
    Combined result from hybrid semantic + keyword search.

    Represents results that combine both semantic similarity and keyword matching.
    """

    semantic_results: List[SemanticSearchResult] = Field(default_factory=list)
    keyword_results: List[SearchResult] = Field(default_factory=list)
    combined_results: List[SemanticSearchResult] = Field(default_factory=list)
    semantic_weight: float = Field(..., description="Weight applied to semantic results", ge=0.0, le=1.0)
    keyword_weight: float = Field(..., description="Weight applied to keyword results", ge=0.0, le=1.0)
    total_results: int = Field(..., description="Total number of unique results", ge=0)
    search_strategy: str = Field(..., description="Strategy used for hybrid search")

    model_config = ConfigDict(populate_by_name=True)


class StorageStats(BaseModel):
    """
    Statistics about vector storage and embedding cache.

    Provides metrics about the semantic search storage system.
    """

    total_embeddings: int = Field(default=0, description="Total number of stored embeddings")
    total_chunks: int = Field(default=0, description="Total number of content chunks")
    total_pages_indexed: int = Field(default=0, description="Total number of indexed pages")
    embedding_dimensions: int = Field(..., description="Embedding vector dimensions")
    storage_size_mb: float = Field(default=0.0, description="Storage size in megabytes")
    last_indexed: Optional[datetime] = Field(None, description="Last indexing timestamp")
    cache_hit_rate: float = Field(default=0.0, description="Cache hit rate percentage", ge=0.0, le=100.0)

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
