"""
Tests for OneNote data models.

Comprehensive unit tests for Pydantic models used in OneNote integration,
including validation, serialization, and business logic.
"""

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from src.models.onenote import (OneNoteNotebook, OneNotePage,
                                OneNoteSearchSummary, OneNoteSection,
                                SearchResult)


class TestOneNoteNotebook:
    """Test OneNote notebook model."""

    def test_notebook_creation_with_required_fields(self):
        """Test creating notebook with minimal required fields."""
        data = {
            "id": "1-abc123",
            "displayName": "Test Notebook",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        notebook = OneNoteNotebook(**data)

        assert notebook.id == "1-abc123"
        assert notebook.display_name == "Test Notebook"
        assert notebook.created_date_time == datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        assert notebook.last_modified_date_time == datetime(2025, 1, 2, 15, 30, 0, tzinfo=timezone.utc)

    def test_notebook_creation_with_all_fields(self):
        """Test creating notebook with all optional fields."""
        data = {
            "id": "1-abc123",
            "displayName": "Complete Notebook",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "isDefault": True,
            "userRole": "Owner",
            "isShared": False,
            "sectionsUrl": "https://graph.microsoft.com/v1.0/me/onenote/notebooks/1-abc123/sections",
            "sectionGroupsUrl": "https://graph.microsoft.com/v1.0/me/onenote/notebooks/1-abc123/sectionGroups",
            "links": {
                "oneNoteClientUrl": {"href": "onenote:https://..."},
                "oneNoteWebUrl": {"href": "https://onedrive.live.com/..."}
            }
        }

        notebook = OneNoteNotebook(**data)

        assert notebook.is_default is True
        assert notebook.user_role == "Owner"
        assert notebook.is_shared is False
        assert str(notebook.sections_url) == "https://graph.microsoft.com/v1.0/me/onenote/notebooks/1-abc123/sections"
        assert notebook.links["oneNoteClientUrl"]["href"] == "onenote:https://..."

    def test_notebook_alias_mapping(self):
        """Test that API field aliases are properly mapped."""
        data = {
            "id": "1-abc123",
            "displayName": "Alias Test",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        notebook = OneNoteNotebook(**data)

        # Test that we can access both alias and field names
        assert notebook.display_name == "Alias Test"
        assert notebook.dict()["display_name"] == "Alias Test"

    def test_notebook_json_serialization(self):
        """Test JSON serialization with datetime encoding."""
        data = {
            "id": "1-abc123",
            "displayName": "JSON Test",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "sectionsUrl": "https://example.com/sections"
        }

        notebook = OneNoteNotebook(**data)
        json_data = notebook.dict()

        # Verify datetime is properly handled
        assert "created_date_time" in json_data
        assert isinstance(json_data["created_date_time"], datetime)


class TestOneNoteSection:
    """Test OneNote section model."""

    def test_section_creation_with_required_fields(self):
        """Test creating section with minimal required fields."""
        data = {
            "id": "1-section123",
            "displayName": "Test Section",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        section = OneNoteSection(**data)

        assert section.id == "1-section123"
        assert section.display_name == "Test Section"
        assert section.created_date_time == datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_section_with_parent_references(self):
        """Test section with parent notebook and section group."""
        data = {
            "id": "1-section123",
            "displayName": "Child Section",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "parentNotebook": {
                "id": "1-notebook123",
                "displayName": "Parent Notebook"
            },
            "parentSectionGroup": {
                "id": "1-group123",
                "displayName": "Parent Group"
            }
        }

        section = OneNoteSection(**data)

        assert section.parent_notebook["id"] == "1-notebook123"
        assert section.parent_section_group["displayName"] == "Parent Group"

    def test_section_optional_fields(self):
        """Test section with all optional fields."""
        data = {
            "id": "1-section123",
            "displayName": "Complete Section",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "isDefault": True,
            "pagesUrl": "https://graph.microsoft.com/v1.0/me/onenote/sections/1-section123/pages"
        }

        section = OneNoteSection(**data)

        assert section.is_default is True
        assert str(section.pages_url) == "https://graph.microsoft.com/v1.0/me/onenote/sections/1-section123/pages"


class TestOneNotePage:
    """Test OneNote page model with business logic."""

    def test_page_creation_with_required_fields(self):
        """Test creating page with minimal required fields."""
        data = {
            "id": "1-page123",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        page = OneNotePage(**data)

        assert page.id == "1-page123"
        assert page.title == "Test Page"
        assert page.created_date_time == datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_title_cleaning_validator(self):
        """Test title cleaning and normalization."""
        # Test with extra whitespace
        data = {
            "id": "1-page123",
            "title": "  Test   Page   With   Spaces  ",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        page = OneNotePage(**data)
        assert page.title == "Test Page With Spaces"

    def test_empty_title_default(self):
        """Test empty title gets default value."""
        data = {
            "id": "1-page123",
            "title": "",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        page = OneNotePage(**data)
        assert page.title == "Untitled Page"

    def test_short_content_property(self):
        """Test short content generation."""
        data = {
            "id": "1-page123",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "text_content": "This is a very long content that should be truncated after 200 characters. " * 5
        }

        page = OneNotePage(**data)
        short = page.short_content

        assert len(short) <= 200
        assert short.endswith("...")

    def test_short_content_with_no_content(self):
        """Test short content when no text content available."""
        data = {
            "id": "1-page123",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        page = OneNotePage(**data)
        assert page.short_content == "Page: Test Page"

    def test_search_text_property(self):
        """Test search text combining title and content."""
        data = {
            "id": "1-page123",
            "title": "Meeting Notes",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "text_content": "Discussion about project timeline and deliverables."
        }

        page = OneNotePage(**data)
        search_text = page.search_text

        assert "Meeting Notes" in search_text
        assert "Discussion about project timeline" in search_text

    def test_get_notebook_name(self):
        """Test notebook name extraction."""
        data = {
            "id": "1-page123",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "parentNotebook": {
                "id": "1-notebook123",
                "displayName": "Work Notebook"
            }
        }

        page = OneNotePage(**data)
        assert page.get_notebook_name() == "Work Notebook"

    def test_get_notebook_name_missing(self):
        """Test notebook name when parent not available."""
        data = {
            "id": "1-page123",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        page = OneNotePage(**data)
        assert page.get_notebook_name() == "Unknown Notebook"

    def test_get_section_name(self):
        """Test section name extraction."""
        data = {
            "id": "1-page123",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "parentSection": {
                "id": "1-section123",
                "displayName": "Meeting Notes"
            }
        }

        page = OneNotePage(**data)
        assert page.get_section_name() == "Meeting Notes"

    def test_get_section_name_missing(self):
        """Test section name when parent not available."""
        data = {
            "id": "1-page123",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        page = OneNotePage(**data)
        assert page.get_section_name() == "Unknown Section"

    def test_page_with_all_fields(self):
        """Test page creation with all possible fields."""
        data = {
            "id": "1-page123",
            "title": "Complete Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "contentUrl": "https://graph.microsoft.com/v1.0/me/onenote/pages/1-page123/content",
            "content": "<html><body>Page content</body></html>",
            "text_content": "Page content",
            "level": 1,
            "order": 0,
            "links": {
                "oneNoteClientUrl": {"href": "onenote:https://..."},
                "oneNoteWebUrl": {"href": "https://onedrive.live.com/..."}
            },
            "parentSection": {
                "id": "1-section123",
                "displayName": "Test Section"
            },
            "parentNotebook": {
                "id": "1-notebook123",
                "displayName": "Test Notebook"
            }
        }

        page = OneNotePage(**data)

        assert page.content == "<html><body>Page content</body></html>"
        assert page.text_content == "Page content"
        assert page.level == 1
        assert page.order == 0
        assert page.links["oneNoteClientUrl"]["href"] == "onenote:https://..."


class TestSearchResult:
    """Test search result model."""

    def test_search_result_creation(self):
        """Test creating search result with pages."""
        page_data = {
            "id": "1-page123",
            "title": "Search Result Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "text_content": "This page contains search terms."
        }

        page = OneNotePage(**page_data)
        result = SearchResult(
            pages=[page],
            query="search terms",
            search_metadata={"source": "test"}
        )

        assert result.pages[0].title == "Search Result Page"
        assert result.query == "search terms"
        assert result.total_count == 1  # Auto-calculated from pages
        assert result.has_results is True

    def test_search_result_empty(self):
        """Test empty search result."""
        result = SearchResult(
            pages=[],
            query="no results"
        )

        assert result.total_count == 0
        assert result.has_results is False
        assert result.unique_notebooks == []
        assert result.unique_sections == []

    def test_search_result_unique_notebooks(self):
        """Test unique notebook extraction."""
        page1_data = {
            "id": "1-page1",
            "title": "Page 1",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "parentNotebook": {"displayName": "Work"}
        }

        page2_data = {
            "id": "1-page2",
            "title": "Page 2",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "parentNotebook": {"displayName": "Personal"}
        }

        page3_data = {
            "id": "1-page3",
            "title": "Page 3",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "parentNotebook": {"displayName": "Work"}  # Duplicate
        }

        pages = [OneNotePage(**data) for data in [page1_data, page2_data, page3_data]]
        result = SearchResult(pages=pages, query="test")

        notebooks = result.unique_notebooks
        assert len(notebooks) == 2
        assert "Personal" in notebooks
        assert "Work" in notebooks

    def test_search_result_filter_by_notebook(self):
        """Test filtering pages by notebook."""
        page1_data = {
            "id": "1-page1",
            "title": "Work Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "parentNotebook": {"displayName": "Work"}
        }

        page2_data = {
            "id": "1-page2",
            "title": "Personal Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "parentNotebook": {"displayName": "Personal"}
        }

        pages = [OneNotePage(**data) for data in [page1_data, page2_data]]
        result = SearchResult(pages=pages, query="test")

        work_pages = result.get_pages_by_notebook("Work")
        assert len(work_pages) == 1
        assert work_pages[0].title == "Work Page"

    def test_search_result_sort_by_relevance(self):
        """Test sorting by relevance (most recent first)."""
        page1_data = {
            "id": "1-page1",
            "title": "Older Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-01T15:30:00Z"
        }

        page2_data = {
            "id": "1-page2",
            "title": "Newer Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-03T15:30:00Z"
        }

        pages = [OneNotePage(**data) for data in [page1_data, page2_data]]
        result = SearchResult(pages=pages, query="test")

        sorted_result = result.sort_by_relevance()
        assert sorted_result.pages[0].title == "Newer Page"
        assert sorted_result.pages[1].title == "Older Page"


class TestOneNoteSearchSummary:
    """Test search summary model."""

    def test_summary_from_empty_search(self):
        """Test summary creation from empty search result."""
        result = SearchResult(pages=[], query="test")
        summary = OneNoteSearchSummary.from_search_result(result)

        assert summary.total_pages == 0
        assert summary.unique_notebooks == 0
        assert summary.unique_sections == 0
        assert summary.date_range is None
        assert summary.most_recent_page is None
        assert summary.oldest_page is None

    def test_summary_from_search_result(self):
        """Test summary creation from search result with pages."""
        page1_data = {
            "id": "1-page1",
            "title": "Older Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-01T15:30:00Z",
            "parentNotebook": {"displayName": "Work"},
            "parentSection": {"displayName": "Meeting Notes"}
        }

        page2_data = {
            "id": "1-page2",
            "title": "Newer Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-03T15:30:00Z",
            "parentNotebook": {"displayName": "Personal"},
            "parentSection": {"displayName": "Ideas"}
        }

        pages = [OneNotePage(**data) for data in [page1_data, page2_data]]
        result = SearchResult(pages=pages, query="test")
        summary = OneNoteSearchSummary.from_search_result(result)

        assert summary.total_pages == 2
        assert summary.unique_notebooks == 2  # Work, Personal
        assert summary.unique_sections == 2   # Meeting Notes, Ideas
        assert summary.most_recent_page.title == "Newer Page"
        assert summary.oldest_page.title == "Older Page"
        assert summary.date_range is not None
        assert summary.date_range["earliest"] == datetime(2025, 1, 1, 15, 30, 0, tzinfo=timezone.utc)
        assert summary.date_range["latest"] == datetime(2025, 1, 3, 15, 30, 0, tzinfo=timezone.utc)
