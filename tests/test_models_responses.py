"""
Tests for OneNote response models.

Comprehensive unit tests for response models used in LangGraph agent interactions,
including search responses, command responses, and streaming.
"""

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from src.models.onenote import OneNotePage, SearchResult
from src.models.responses import (AgentState, OneNoteCommandResponse,
                                  OneNoteSearchResponse, StreamingChunk)


class TestOneNoteSearchResponse:
    """Test OneNote search response model."""

    def test_search_response_creation_minimal(self):
        """Test creating search response with minimal required fields."""
        response = OneNoteSearchResponse(
            answer="This is the answer to your question.",
            search_query_used="test query"
        )

        assert response.answer == "This is the answer to your question."
        assert response.search_query_used == "test query"
        assert response.sources == []
        assert response.confidence == 0.0
        assert response.reasoning is None
        assert response.metadata == {}

    def test_search_response_with_sources(self):
        """Test search response with source pages."""
        page1_data = {
            "id": "1-page1",
            "title": "Source Page 1",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "text_content": "Content from page 1"
        }

        page2_data = {
            "id": "1-page2",
            "title": "Source Page 2",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "text_content": "Content from page 2"
        }

        sources = [OneNotePage(**data) for data in [page1_data, page2_data]]

        response = OneNoteSearchResponse(
            answer="Based on your OneNote pages, here's the answer.",
            sources=sources,
            search_query_used="test query",
            confidence=0.8,
            reasoning="Found relevant information in 2 pages"
        )

        assert len(response.sources) == 2
        assert response.confidence == 0.8
        assert response.reasoning == "Found relevant information in 2 pages"
        assert response.has_sources is True
        assert response.source_count == 2

    def test_search_response_answer_validation(self):
        """Test answer validation - empty answers get default message."""
        # Empty answer
        response = OneNoteSearchResponse(
            answer="",
            search_query_used="test"
        )
        assert response.answer == "I couldn't find a specific answer to your question based on your OneNote content."

        # Whitespace-only answer
        response = OneNoteSearchResponse(
            answer="   ",
            search_query_used="test"
        )
        assert response.answer == "I couldn't find a specific answer to your question based on your OneNote content."

    def test_search_response_confidence_validation(self):
        """Test confidence score validation and auto-calculation."""
        page_data = {
            "id": "1-page1",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        # Test with no sources - confidence remains 0.0 (no auto-calculation)
        response = OneNoteSearchResponse(
            answer="No sources found",
            sources=[],
            search_query_used="test"
        )
        assert response.confidence == 0.0

        # Test with multiple sources - should get higher confidence
        sources = [OneNotePage(**page_data) for _ in range(3)]
        response = OneNoteSearchResponse(
            answer="Found answer",
            sources=sources,
            search_query_used="test"
        )
        assert response.confidence > 0.3

        # Test with many sources - should get high confidence
        sources = [OneNotePage(**page_data) for _ in range(6)]
        response = OneNoteSearchResponse(
            answer="Found answer",
            sources=sources,
            search_query_used="test"
        )
        assert response.confidence == 0.9

    def test_search_response_confidence_bounds(self):
        """Test confidence score bounds validation."""
        with pytest.raises(ValueError):
            OneNoteSearchResponse(
                answer="test",
                search_query_used="test",
                confidence=-0.1  # Below 0.0
            )

        with pytest.raises(ValueError):
            OneNoteSearchResponse(
                answer="test",
                search_query_used="test",
                confidence=1.1  # Above 1.0
            )

    def test_search_response_unique_notebooks(self):
        """Test unique notebooks property."""
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

        sources = [OneNotePage(**data) for data in [page1_data, page2_data, page3_data]]

        response = OneNoteSearchResponse(
            answer="Answer from multiple notebooks",
            sources=sources,
            search_query_used="test"
        )

        notebooks = response.unique_notebooks
        assert len(notebooks) == 2
        assert "Personal" in notebooks
        assert "Work" in notebooks
        assert notebooks == sorted(notebooks)  # Should be sorted

    def test_search_response_get_formatted_sources(self):
        """Test formatted sources output."""
        page_data = {
            "id": "1-page1",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z",
            "parentNotebook": {"displayName": "Work"},
            "parentSection": {"displayName": "Meeting Notes"}
        }

        page = OneNotePage(**page_data)
        response = OneNoteSearchResponse(
            answer="Test answer",
            sources=[page],
            search_query_used="test"
        )

        formatted = response.get_formatted_sources()
        assert "1. **Test Page**" in formatted
        assert "(Work > Meeting Notes)" in formatted
        assert "2025-01-02" in formatted

    def test_search_response_add_metadata(self):
        """Test adding metadata to response."""
        response = OneNoteSearchResponse(
            answer="Test answer",
            search_query_used="test"
        )

        response.add_metadata("execution_time", 1.5)
        response.add_metadata("strategy", "semantic")

        assert response.metadata["execution_time"] == 1.5
        assert response.metadata["strategy"] == "semantic"


class TestOneNoteCommandResponse:
    """Test OneNote command response model."""

    def test_command_response_creation(self):
        """Test creating command response."""
        response = OneNoteCommandResponse(
            command="search",
            message="Search completed",
            data={"count": 5}
        )

        assert response.command == "search"
        assert response.success is True
        assert response.message == "Search completed"
        assert response.data["count"] == 5
        assert response.error is None

    def test_command_response_success_factory(self):
        """Test success response factory method."""
        response = OneNoteCommandResponse.success_response(
            command="notebooks",
            message="Retrieved 3 notebooks",
            data={"notebooks": ["Work", "Personal", "Archive"]}
        )

        assert response.command == "notebooks"
        assert response.success is True
        assert response.message == "Retrieved 3 notebooks"
        assert len(response.data["notebooks"]) == 3

    def test_command_response_error_factory(self):
        """Test error response factory method."""
        response = OneNoteCommandResponse.error_response(
            command="search",
            error="Authentication required"
        )

        assert response.command == "search"
        assert response.success is False
        assert response.message == "Command 'search' failed"
        assert response.error == "Authentication required"

    def test_command_response_with_error(self):
        """Test command response with error details."""
        response = OneNoteCommandResponse(
            command="sync",
            success=False,
            message="Sync failed",
            error="Network timeout"
        )

        assert response.success is False
        assert response.error == "Network timeout"


class TestStreamingChunk:
    """Test streaming chunk model."""

    def test_streaming_chunk_creation(self):
        """Test creating streaming chunk."""
        chunk = StreamingChunk(
            type="text",
            content="Processing your request...",
            metadata={"step": 1}
        )

        assert chunk.type == "text"
        assert chunk.content == "Processing your request..."
        assert chunk.metadata["step"] == 1
        assert chunk.is_final is False
        assert chunk.timestamp is not None

    def test_text_chunk_factory(self):
        """Test text chunk factory method."""
        chunk = StreamingChunk.text_chunk("Hello world", is_final=True)

        assert chunk.type == "text"
        assert chunk.content == "Hello world"
        assert chunk.is_final is True

    def test_status_chunk_factory(self):
        """Test status chunk factory method."""
        chunk = StreamingChunk.status_chunk("Searching OneNote...")

        assert chunk.type == "status"
        assert chunk.content == "Searching OneNote..."
        assert chunk.is_final is False

    def test_sources_chunk_factory(self):
        """Test sources chunk factory method."""
        page_data = {
            "id": "1-page1",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        pages = [OneNotePage(**page_data)]
        chunk = StreamingChunk.sources_chunk(pages)

        assert chunk.type == "sources"
        assert chunk.content == "Found 1 relevant pages"
        assert len(chunk.metadata["sources"]) == 1

    def test_error_chunk_factory(self):
        """Test error chunk factory method."""
        chunk = StreamingChunk.error_chunk("Authentication failed")

        assert chunk.type == "error"
        assert chunk.content == "Authentication failed"
        assert chunk.is_final is True


class TestAgentState:
    """Test agent state model."""

    def test_agent_state_creation(self):
        """Test creating agent state."""
        state = AgentState()

        assert state.messages == []
        assert state.current_query is None
        assert state.search_results is None
        assert state.context == {}
        assert state.step_count == 0

    def test_agent_state_add_message(self):
        """Test adding messages to agent state."""
        state = AgentState()

        state.add_message("user", "Hello")
        state.add_message("assistant", "Hi there!")

        assert len(state.messages) == 2
        assert state.messages[0]["role"] == "user"
        assert state.messages[0]["content"] == "Hello"
        assert state.messages[1]["role"] == "assistant"
        assert state.messages[1]["content"] == "Hi there!"
        assert "timestamp" in state.messages[0]

    def test_agent_state_get_last_user_message(self):
        """Test getting last user message."""
        state = AgentState()

        # No messages yet
        assert state.get_last_user_message() is None

        state.add_message("user", "First question")
        state.add_message("assistant", "First answer")
        state.add_message("user", "Second question")

        assert state.get_last_user_message() == "Second question"

    def test_agent_state_increment_step(self):
        """Test incrementing step counter."""
        state = AgentState()

        assert state.step_count == 0

        state.increment_step()
        assert state.step_count == 1

        state.increment_step()
        assert state.step_count == 2

    def test_agent_state_clear_context(self):
        """Test clearing agent context."""
        state = AgentState()

        # Add some data
        state.add_message("user", "Hello")
        state.current_query = "test query"
        state.context = {"key": "value"}
        state.step_count = 5

        # Clear context
        state.clear_context()

        # Messages should remain, but other context cleared
        assert len(state.messages) == 1
        assert state.current_query is None
        assert state.context == {}
        assert state.step_count == 0

    def test_agent_state_with_search_results(self):
        """Test agent state with search results."""
        page_data = {
            "id": "1-page1",
            "title": "Test Page",
            "createdDateTime": "2025-01-01T10:00:00Z",
            "lastModifiedDateTime": "2025-01-02T15:30:00Z"
        }

        page = OneNotePage(**page_data)
        search_results = SearchResult(pages=[page], query="test")

        state = AgentState(
            current_query="test query",
            search_results=search_results
        )

        assert state.current_query == "test query"
        assert state.search_results.query == "test"
        assert len(state.search_results.pages) == 1
