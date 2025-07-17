"""
OneNote content retrieval and processing utilities.

Provides utilities for content extraction, text processing, and
data formatting for OneNote pages and notebooks.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set

from ..models.onenote import OneNotePage, SearchResult

logger = logging.getLogger(__name__)


class OneNoteContentProcessor:
    """
    OneNote content processor for text extraction and analysis.

    Provides utilities for processing OneNote content including
    text extraction, keyword analysis, and content formatting.
    """

    def __init__(self):
        """Initialize the content processor."""
        # Common stop words to filter out
        self.stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'were', 'will', 'with', 'would', 'you', 'your', 'i',
            'me', 'my', 'we', 'us', 'our', 'they', 'them', 'their', 'this',
            'these', 'those', 'but', 'if', 'or', 'because', 'as', 'until',
            'while', 'although', 'through', 'during', 'before', 'after',
            'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under',
            'again', 'further', 'then', 'once'
        }

    def extract_keywords(self, text: str, max_keywords: int = 20) -> List[str]:
        """
        Extract keywords from text content.

        Args:
            text: Text content to analyze
            max_keywords: Maximum number of keywords to return

        Returns:
            List of extracted keywords
        """
        if not text:
            return []

        try:
            # Convert to lowercase and extract words
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

            # Filter out stop words and count occurrences
            word_counts = {}
            for word in words:
                if word not in self.stop_words and len(word) >= 3:
                    word_counts[word] = word_counts.get(word, 0) + 1

            # Sort by frequency and return top keywords
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            return [word for word, count in sorted_words[:max_keywords]]

        except Exception as e:
            logger.warning(f"Failed to extract keywords: {e}")
            return []

    def get_content_summary(self, page: OneNotePage, max_length: int = 500) -> str:
        """
        Get a summary of page content.

        Args:
            page: OneNote page to summarize
            max_length: Maximum summary length

        Returns:
            Content summary string
        """
        if not page.text_content:
            return f"**{page.title}**\n\n*No content available*"

        content = page.text_content.strip()

        # If content is short enough, return as is
        if len(content) <= max_length:
            summary = content
        else:
            # Extract first paragraph or truncate
            paragraphs = content.split('\n\n')
            if paragraphs and len(paragraphs[0]) <= max_length:
                summary = paragraphs[0]
            else:
                summary = content[:max_length - 3] + "..."

        # Format with title
        return f"**{page.title}**\n\n{summary}"

    def highlight_search_terms(self, text: str, search_query: str) -> str:
        """
        Highlight search terms in text content.

        Args:
            text: Text content
            search_query: Original search query

        Returns:
            Text with search terms highlighted
        """
        if not text or not search_query:
            return text

        try:
            # Extract search terms
            search_terms = re.findall(r'\b\w+\b', search_query.lower())

            # Highlight each term
            highlighted_text = text
            for term in search_terms:
                if len(term) >= 3:  # Only highlight meaningful terms
                    pattern = re.compile(f'\\b{re.escape(term)}\\b', re.IGNORECASE)
                    highlighted_text = pattern.sub(f'**{term}**', highlighted_text)

            return highlighted_text

        except Exception as e:
            logger.warning(f"Failed to highlight search terms: {e}")
            return text

    def find_relevant_excerpts(self, page: OneNotePage, search_query: str, max_excerpts: int = 3) -> List[str]:
        """
        Find relevant excerpts from page content based on search query.

        Args:
            page: OneNote page to analyze
            search_query: Search query to match against
            max_excerpts: Maximum number of excerpts to return

        Returns:
            List of relevant text excerpts
        """
        if not page.text_content or not search_query:
            return []

        try:
            # Extract search terms
            search_terms = set(re.findall(r'\b\w+\b', search_query.lower()))
            search_terms = {term for term in search_terms if len(term) >= 3 and term not in self.stop_words}

            if not search_terms:
                return []

            # Split content into sentences
            sentences = re.split(r'[.!?]+', page.text_content)

            # Score sentences based on search term presence
            scored_sentences = []
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 20:  # Skip very short sentences
                    continue

                sentence_words = set(re.findall(r'\b\w+\b', sentence.lower()))
                score = len(search_terms.intersection(sentence_words))

                if score > 0:
                    scored_sentences.append((sentence, score))

            # Sort by score and return top excerpts
            scored_sentences.sort(key=lambda x: x[1], reverse=True)
            excerpts = [sentence for sentence, score in scored_sentences[:max_excerpts]]

            return excerpts

        except Exception as e:
            logger.warning(f"Failed to find relevant excerpts: {e}")
            return []

    def get_page_context(self, page: OneNotePage) -> Dict[str, Any]:
        """
        Get contextual information about a page.

        Args:
            page: OneNote page to analyze

        Returns:
            Dictionary with page context information
        """
        context = {
            'title': page.title,
            'notebook': page.get_notebook_name(),
            'section': page.get_section_name(),
            'created': page.created_date_time.strftime('%Y-%m-%d'),
            'modified': page.last_modified_date_time.strftime('%Y-%m-%d'),
            'has_content': bool(page.text_content),
            'content_length': len(page.text_content) if page.text_content else 0
        }

        if page.text_content:
            context['keywords'] = self.extract_keywords(page.text_content, max_keywords=10)
            context['word_count'] = len(page.text_content.split())

        return context

    def format_search_results_for_ai(self, search_result: SearchResult) -> str:
        """
        Format search results for consumption by AI agent.

        Args:
            search_result: Search results to format

        Returns:
            Formatted string for AI processing
        """
        if not search_result.pages:
            return f"No results found for query: '{search_result.query}'"

        formatted_parts = [
            f"Search Query: {search_result.query}",
            f"Results Found: {search_result.total_count} pages",
            "",
            "Page Contents:"
        ]

        for i, page in enumerate(search_result.pages, 1):
            context = self.get_page_context(page)

            page_info = [
                f"\n--- Page {i}: {page.title} ---",
                f"Notebook: {context['notebook']}",
                f"Section: {context['section']}",
                f"Modified: {context['modified']}"
            ]

            if page.text_content:
                # Get relevant excerpts if possible
                excerpts = self.find_relevant_excerpts(page, search_result.query)
                if excerpts:
                    page_info.append("Relevant Content:")
                    for excerpt in excerpts[:2]:  # Limit to 2 excerpts per page
                        page_info.append(f"  • {excerpt}")
                else:
                    # Fall back to content summary
                    summary = self.get_content_summary(page, max_length=300)
                    page_info.append(f"Content: {summary}")
            else:
                page_info.append("Content: No text content available")

            formatted_parts.extend(page_info)

        return "\n".join(formatted_parts)

    def analyze_search_coverage(self, search_result: SearchResult) -> Dict[str, Any]:
        """
        Analyze the coverage and diversity of search results.

        Args:
            search_result: Search results to analyze

        Returns:
            Analysis of search result coverage
        """
        if not search_result.pages:
            return {
                'total_pages': 0,
                'unique_notebooks': 0,
                'unique_sections': 0,
                'date_coverage': {},
                'content_diversity': 'low'
            }

        # Collect metadata
        notebooks = set()
        sections = set()
        dates = []
        total_content_length = 0

        for page in search_result.pages:
            notebooks.add(page.get_notebook_name())
            sections.add(page.get_section_name())
            dates.append(page.last_modified_date_time)

            if page.text_content:
                total_content_length += len(page.text_content)

        # Calculate date range
        if dates:
            dates.sort()
            date_range = {
                'earliest': dates[0].strftime('%Y-%m-%d'),
                'latest': dates[-1].strftime('%Y-%m-%d'),
                'span_days': (dates[-1] - dates[0]).days
            }
        else:
            date_range = {}

        # Determine content diversity
        diversity = 'low'
        if len(notebooks) > 2 and len(sections) > 3:
            diversity = 'high'
        elif len(notebooks) > 1 or len(sections) > 2:
            diversity = 'medium'

        return {
            'total_pages': len(search_result.pages),
            'unique_notebooks': len(notebooks),
            'unique_sections': len(sections),
            'notebook_names': sorted(list(notebooks)),
            'section_names': sorted(list(sections)),
            'date_coverage': date_range,
            'total_content_length': total_content_length,
            'average_content_length': total_content_length / len(search_result.pages) if search_result.pages else 0,
            'content_diversity': diversity
        }


def create_ai_context_from_pages(pages: List[OneNotePage], query: str) -> str:
    """
    Create AI context from OneNote pages.

    Args:
        pages: List of OneNote pages
        query: Original search query

    Returns:
        Formatted context for AI processing
    """
    processor = OneNoteContentProcessor()

    search_result = SearchResult(
        pages=pages,
        query=query,
        total_count=len(pages)
    )

    return processor.format_search_results_for_ai(search_result)


def extract_page_summary(page: OneNotePage, max_length: int = 200) -> str:
    """
    Extract a summary from a OneNote page.

    Args:
        page: OneNote page to summarize
        max_length: Maximum summary length

    Returns:
        Page summary
    """
    processor = OneNoteContentProcessor()
    return processor.get_content_summary(page, max_length)


if __name__ == "__main__":
    """Test content processing functionality."""
    from datetime import datetime

    # Create test page
    test_page = OneNotePage(
        id="test-123",
        title="Test Page",
        created_date_time=datetime.now(),
        last_modified_date_time=datetime.now(),
        text_content="This is a test page about Python development and machine learning algorithms."
    )

    processor = OneNoteContentProcessor()

    print("Testing content processing...")

    # Test keyword extraction
    keywords = processor.extract_keywords(test_page.text_content)
    print(f"Keywords: {keywords}")

    # Test content summary
    summary = processor.get_content_summary(test_page)
    print(f"Summary: {summary}")

    # Test context
    context = processor.get_page_context(test_page)
    print(f"Context: {context}")

    print("✅ Content processing test completed")
