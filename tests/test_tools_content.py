"""
Tests for OneNote content processing utilities.

Comprehensive unit tests for content extraction, text processing,
and data formatting functionality.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.models.onenote import OneNotePage, SearchResult
from src.tools.onenote_content import (OneNoteContentProcessor,
                                       create_ai_context_from_pages,
                                       extract_page_summary)

# Common test datetime for consistent tests
TEST_DATETIME = datetime(2023, 1, 1, 12, 0, 0)


class TestOneNoteContentProcessor:
    """Test OneNote content processor."""

    def test_content_processor_initialization(self):
        """Test content processor initialization."""
        processor = OneNoteContentProcessor()

        assert processor is not None
        assert hasattr(processor, 'stop_words')
        assert len(processor.stop_words) > 0
        assert 'the' in processor.stop_words
        assert 'and' in processor.stop_words

    def test_extract_keywords_basic(self):
        """Test basic keyword extraction."""
        processor = OneNoteContentProcessor()

        text = "Python programming language machine learning data science"
        keywords = processor.extract_keywords(text, max_keywords=5)

        assert isinstance(keywords, list)
        assert len(keywords) <= 5
        assert 'python' in [k.lower() for k in keywords]
        assert 'programming' in [k.lower() for k in keywords]

    def test_extract_keywords_empty_text(self):
        """Test keyword extraction with empty text."""
        processor = OneNoteContentProcessor()

        keywords = processor.extract_keywords("", max_keywords=10)
        assert keywords == []

        keywords = processor.extract_keywords(None, max_keywords=10)
        assert keywords == []

    def test_extract_keywords_filters_stop_words(self):
        """Test that stop words are filtered out."""
        processor = OneNoteContentProcessor()

        text = "the quick brown fox jumps over the lazy dog programming"
        keywords = processor.extract_keywords(text, max_keywords=10)

        # Should not contain common stop words
        keyword_lower = [k.lower() for k in keywords]
        assert 'the' not in keyword_lower
        assert 'over' not in keyword_lower

        # Should contain meaningful words
        assert 'programming' in keyword_lower

    def test_extract_keywords_case_insensitive(self):
        """Test keyword extraction is case insensitive."""
        processor = OneNoteContentProcessor()

        text = "Python PYTHON python Programming PROGRAMMING"
        keywords = processor.extract_keywords(text, max_keywords=5)

        # Should merge different cases of the same word
        keyword_lower = [k.lower() for k in keywords]
        assert 'python' in keyword_lower
        assert 'programming' in keyword_lower

    def test_extract_keywords_max_limit(self):
        """Test keyword extraction respects max limit."""
        processor = OneNoteContentProcessor()

        text = " ".join([f"word{i}" for i in range(50)])  # 50 unique words
        keywords = processor.extract_keywords(text, max_keywords=5)

        assert len(keywords) <= 5

    def test_get_content_summary_basic(self):
        """Test basic content summary generation."""
        processor = OneNoteContentProcessor()

        page = OneNotePage(
            id="test-page",
            title="Test Page",
            text_content="This is test content for the page.",
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        summary = processor.get_content_summary(page, max_length=100)

        assert isinstance(summary, str)
        assert "Test Page" in summary
        assert "This is test content" in summary

    def test_get_content_summary_no_content(self):
        """Test content summary with no content."""
        processor = OneNoteContentProcessor()

        page = OneNotePage(
            id="test-page",
            title="Test Page",
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        summary = processor.get_content_summary(page)

        assert isinstance(summary, str)
        assert "Test Page" in summary
        assert "No content available" in summary

    def test_get_content_summary_long_content(self):
        """Test content summary with long content."""
        processor = OneNoteContentProcessor()

        long_content = "This is a very long piece of content. " * 20
        page = OneNotePage(
            id="test-page",
            title="Test Page",
            text_content=long_content,
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        summary = processor.get_content_summary(page, max_length=100)

        assert isinstance(summary, str)
        assert len(summary) <= 150  # Allow some overhead for formatting
        assert "Test Page" in summary

    def test_highlight_search_terms(self):
        """Test search term highlighting."""
        processor = OneNoteContentProcessor()

        text = "Python programming is fun and Python is powerful"
        highlighted = processor.highlight_search_terms(text, "Python")

        assert isinstance(highlighted, str)
        assert "**python**" in highlighted  # Search terms are highlighted in lowercase

    def test_highlight_search_terms_case_insensitive(self):
        """Test highlighting is case insensitive."""
        processor = OneNoteContentProcessor()

        text = "Python programming and PYTHON development"
        highlighted = processor.highlight_search_terms(text, "python")

        assert "**python**" in highlighted.lower()

    def test_find_relevant_excerpts(self):
        """Test finding relevant excerpts from page."""
        processor = OneNoteContentProcessor()

        page = OneNotePage(
            id="test-page",
            title="Test Page",
            text_content="This is about Python programming. Python is great for data science. Machine learning with Python is popular.",
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        excerpts = processor.find_relevant_excerpts(page, "Python", max_excerpts=2)

        assert isinstance(excerpts, list)
        assert len(excerpts) <= 2

    def test_find_relevant_excerpts_empty_query(self):
        """Test finding excerpts with empty query."""
        processor = OneNoteContentProcessor()

        page = OneNotePage(
            id="test-page",
            title="Test Page",
            text_content="Some content here",
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        excerpts = processor.find_relevant_excerpts(page, "", max_excerpts=3)

        assert isinstance(excerpts, list)

    def test_get_page_context(self):
        """Test getting page context information."""
        processor = OneNoteContentProcessor()

        page = OneNotePage(
            id="test-page",
            title="Meeting Notes",
            text_content="Discussion about project timeline and deliverables",
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME,
            parent_notebook={"displayName": "Work Notebook"},
            parent_section={"displayName": "Meetings"}
        )

        context = processor.get_page_context(page)

        assert isinstance(context, dict)
        assert "notebook" in context
        assert "section" in context

    def test_format_search_results_for_ai(self):
        """Test formatting search results for AI consumption."""
        processor = OneNoteContentProcessor()

        pages = [
            OneNotePage(
                id="page1",
                title="Page 1",
                text_content="Content about Python programming",
                createdDateTime=TEST_DATETIME,
                lastModifiedDateTime=TEST_DATETIME
            ),
            OneNotePage(
                id="page2",
                title="Page 2",
                text_content="More Python development tips",
                createdDateTime=TEST_DATETIME,
                lastModifiedDateTime=TEST_DATETIME
            )
        ]

        search_result = SearchResult(
            pages=pages,
            query="Python programming"
        )

        formatted = processor.format_search_results_for_ai(search_result)

        assert isinstance(formatted, str)
        assert "Page 1" in formatted
        assert "Page 2" in formatted

    def test_format_search_results_empty(self):
        """Test formatting empty search results."""
        processor = OneNoteContentProcessor()

        search_result = SearchResult(pages=[], query="test query")
        formatted = processor.format_search_results_for_ai(search_result)

        assert isinstance(formatted, str)
        assert len(formatted) > 0

    def test_analyze_search_coverage(self):
        """Test search coverage analysis."""
        processor = OneNoteContentProcessor()

        pages = [
            OneNotePage(
                id="page1",
                title="Meeting Notes",
                text_content="Discussion about project",
                createdDateTime=TEST_DATETIME,
                lastModifiedDateTime=TEST_DATETIME,
                parent_notebook={"displayName": "Work"}
            ),
            OneNotePage(
                id="page2",
                title="Project Plan",
                text_content="Technical requirements",
                createdDateTime=TEST_DATETIME,
                lastModifiedDateTime=TEST_DATETIME,
                parent_notebook={"displayName": "Work"}
            )
        ]

        search_result = SearchResult(
            pages=pages,
            query="project"
        )

        coverage = processor.analyze_search_coverage(search_result)

        assert isinstance(coverage, dict)
        assert "total_pages" in coverage
        assert "notebook_names" in coverage


class TestContentUtilityFunctions:
    """Test content utility functions."""

    def test_create_ai_context_from_pages(self):
        """Test creating AI context from pages."""
        pages = [
            OneNotePage(
                id="page1",
                title="Python Guide",
                text_content="Python programming basics",
                createdDateTime=TEST_DATETIME,
                lastModifiedDateTime=TEST_DATETIME
            ),
            OneNotePage(
                id="page2",
                title="Advanced Python",
                text_content="Advanced Python concepts",
                createdDateTime=TEST_DATETIME,
                lastModifiedDateTime=TEST_DATETIME
            )
        ]

        context = create_ai_context_from_pages(pages, "Python programming")

        assert isinstance(context, str)
        assert "Python Guide" in context
        assert "Advanced Python" in context

    def test_create_ai_context_empty_pages(self):
        """Test creating AI context with empty pages list."""
        context = create_ai_context_from_pages([], "test query")

        assert isinstance(context, str)
        assert len(context) > 0

    def test_extract_page_summary(self):
        """Test extracting page summary."""
        page = OneNotePage(
            id="test-page",
            title="Test Page",
            text_content="This is test content for summarization. It contains multiple sentences to test the summarization logic.",
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        summary = extract_page_summary(page, max_length=50)

        assert isinstance(summary, str)
        assert len(summary) <= 70  # Allow some overhead
        assert "Test Page" in summary or "This is test content" in summary

    def test_extract_page_summary_short_content(self):
        """Test extracting summary from short content."""
        page = OneNotePage(
            id="test-page",
            title="Short",
            text_content="Brief",
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        summary = extract_page_summary(page, max_length=100)

        assert isinstance(summary, str)
        assert "Brief" in summary

    def test_extract_page_summary_no_content(self):
        """Test extracting summary with no content."""
        page = OneNotePage(
            id="test-page",
            title="Empty Page",
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        summary = extract_page_summary(page)

        assert isinstance(summary, str)
        assert "Empty Page" in summary


class TestContentProcessorIntegration:
    """Test content processor integration scenarios."""

    def test_full_workflow_with_search_result(self):
        """Test complete workflow with search result."""
        processor = OneNoteContentProcessor()

        pages = [
            OneNotePage(
                id="page1",
                title="Python Tutorial",
                text_content="Learn Python programming with examples and exercises",
                createdDateTime=TEST_DATETIME,
                lastModifiedDateTime=TEST_DATETIME,
                parent_notebook={"displayName": "Programming"},
                parent_section={"displayName": "Tutorials"}
            ),
            OneNotePage(
                id="page2",
                title="Python Best Practices",
                text_content="Best practices for Python development and code quality",
                createdDateTime=TEST_DATETIME,
                lastModifiedDateTime=TEST_DATETIME,
                parent_notebook={"displayName": "Programming"},
                parent_section={"displayName": "Guidelines"}
            )
        ]

        search_result = SearchResult(
            pages=pages,
            query="Python programming"
        )

        # Test the full workflow
        formatted = processor.format_search_results_for_ai(search_result)
        keywords = processor.extract_keywords(formatted)
        coverage = processor.analyze_search_coverage(search_result)

        assert isinstance(formatted, str)
        assert isinstance(keywords, list)
        assert isinstance(coverage, dict)

    def test_error_handling_with_invalid_data(self):
        """Test processor error handling."""
        processor = OneNoteContentProcessor()

        # Test with None input
        keywords = processor.extract_keywords(None)
        assert keywords == []

        # Test with page without content
        page = OneNotePage(
            id="test",
            title="Test",
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        summary = processor.get_content_summary(page)
        assert isinstance(summary, str)

        excerpts = processor.find_relevant_excerpts(page, "test")
        assert isinstance(excerpts, list)

    def test_performance_with_large_content(self):
        """Test processor performance with large content."""
        processor = OneNoteContentProcessor()

        # Create a large content string
        large_content = "This is a performance test. " * 1000

        page = OneNotePage(
            id="perf-test",
            title="Performance Test",
            text_content=large_content,
            createdDateTime=TEST_DATETIME,
            lastModifiedDateTime=TEST_DATETIME
        )

        # These should complete without errors
        keywords = processor.extract_keywords(large_content, max_keywords=10)
        summary = processor.get_content_summary(page, max_length=200)

        assert len(keywords) <= 10
        assert len(summary) <= 250  # Allow overhead
