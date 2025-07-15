"""
Response models for OneNote Copilot agent outputs.

Provides structured response formats for LangGraph agent interactions,
including search responses, summaries, and error handling.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .onenote import OneNotePage, SearchResult


class OneNoteSearchResponse(BaseModel):
    """
    Response model for OneNote search agent.

    Structured response from the LangGraph agent containing AI-generated
    answer, source pages, and metadata about the search operation.
    """

    answer: str = Field(..., description="AI-generated answer to user query")
    sources: List[OneNotePage] = Field(default_factory=list, description="Source OneNote pages")
    confidence: float = Field(
        default=0.0,
        description="Confidence score for the answer",
        ge=0.0,
        le=1.0
    )
    search_query_used: str = Field(..., description="Actual search query sent to OneNote API")
    reasoning: Optional[str] = Field(None, description="AI reasoning process for debugging")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @field_validator('answer')
    @classmethod
    def validate_answer(cls, v: str) -> str:
        """Ensure answer is not empty."""
        if not v or not v.strip():
            return "I couldn't find a specific answer to your question based on your OneNote content."
        return v.strip()

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate confidence is within bounds."""
        if v < 0.0:
            return 0.0
        elif v > 1.0:
            return 1.0
        return v

    @model_validator(mode='after')
    def calculate_confidence_from_sources(self) -> 'OneNoteSearchResponse':
        """Calculate confidence based on sources if not explicitly set."""
        if self.confidence == 0.0 and hasattr(self, 'sources'):
            # Simple confidence calculation based on number of sources
            source_count = len(self.sources)
            if source_count == 0:
                self.confidence = 0.0  # Keep as 0.0 for no sources
            elif source_count >= 5:
                self.confidence = 0.9
            else:
                self.confidence = 0.3 + (source_count * 0.15)
        return self

    @property
    def has_sources(self) -> bool:
        """Check if response has source pages."""
        return len(self.sources) > 0

    @property
    def source_count(self) -> int:
        """Get number of source pages."""
        return len(self.sources)

    @property
    def unique_notebooks(self) -> List[str]:
        """Get unique notebook names from sources."""
        notebooks = set()
        for page in self.sources:
            notebooks.add(page.get_notebook_name())
        return sorted(list(notebooks))

    def get_formatted_sources(self) -> str:
        """
        Get formatted source information for display.

        Returns:
            Formatted string with source page information
        """
        if not self.sources:
            return "No sources found."

        source_lines = []
        for i, page in enumerate(self.sources, 1):
            notebook = page.get_notebook_name()
            section = page.get_section_name()
            date_str = page.last_modified_date_time.strftime("%Y-%m-%d")
            source_lines.append(f"{i}. **{page.title}** ({notebook} > {section}) - {date_str}")

        return "\n".join(source_lines)

    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to the response.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value


class OneNoteCommandResponse(BaseModel):
    """
    Response model for CLI command operations.

    Used for responses to CLI commands like /notebooks, /recent, etc.
    """

    command: str = Field(..., description="Command that was executed")
    success: bool = Field(default=True, description="Whether command succeeded")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Command result data")
    error: Optional[str] = Field(None, description="Error message if command failed")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @classmethod
    def success_response(cls, command: str, message: str, data: Optional[Dict[str, Any]] = None) -> 'OneNoteCommandResponse':
        """
        Create a successful command response.

        Args:
            command: Command that was executed
            message: Success message
            data: Optional result data

        Returns:
            Successful command response
        """
        return cls(
            command=command,
            success=True,
            message=message,
            data=data
        )

    @classmethod
    def error_response(cls, command: str, error: str) -> 'OneNoteCommandResponse':
        """
        Create an error command response.

        Args:
            command: Command that was executed
            error: Error message

        Returns:
            Error command response
        """
        return cls(
            command=command,
            success=False,
            message=f"Command '{command}' failed",
            error=error
        )


class StreamingChunk(BaseModel):
    """
    Model for streaming response chunks from LangGraph agent.

    Used to provide real-time updates during agent processing.
    """

    type: str = Field(..., description="Type of chunk (text, status, sources, etc.)")
    content: str = Field(default="", description="Chunk content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    is_final: bool = Field(default=False, description="Whether this is the final chunk")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(), description="Chunk timestamp")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @classmethod
    def text_chunk(cls, content: str, is_final: bool = False) -> 'StreamingChunk':
        """
        Create a text content chunk.

        Args:
            content: Text content
            is_final: Whether this is the final chunk

        Returns:
            Text streaming chunk
        """
        return cls(
            type="text",
            content=content,
            is_final=is_final
        )

    @classmethod
    def status_chunk(cls, status: str) -> 'StreamingChunk':
        """
        Create a status update chunk.

        Args:
            status: Status message

        Returns:
            Status streaming chunk
        """
        return cls(
            type="status",
            content=status
        )

    @classmethod
    def sources_chunk(cls, sources: List[OneNotePage]) -> 'StreamingChunk':
        """
        Create a sources chunk.

        Args:
            sources: List of source pages

        Returns:
            Sources streaming chunk
        """
        return cls(
            type="sources",
            content=f"Found {len(sources)} relevant pages",
            metadata={"sources": [page.dict() for page in sources]}
        )

    @classmethod
    def error_chunk(cls, error: str) -> 'StreamingChunk':
        """
        Create an error chunk.

        Args:
            error: Error message

        Returns:
            Error streaming chunk
        """
        return cls(
            type="error",
            content=error,
            is_final=True
        )


class AgentState(BaseModel):
    """
    State model for LangGraph agent.

    Maintains conversation state and context throughout the agent execution.
    """

    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation messages")
    current_query: Optional[str] = Field(None, description="Current user query")
    search_results: Optional[SearchResult] = Field(None, description="Current search results")
    context: Dict[str, Any] = Field(default_factory=dict, description="Agent context")
    step_count: int = Field(default=0, description="Number of processing steps")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
        """
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def get_last_user_message(self) -> Optional[str]:
        """
        Get the last user message.

        Returns:
            Last user message content or None
        """
        for message in reversed(self.messages):
            if message.get("role") == "user":
                return message.get("content")
        return None

    def increment_step(self) -> None:
        """Increment the step counter."""
        self.step_count += 1

    def clear_context(self) -> None:
        """Clear agent context while preserving messages."""
        self.context.clear()
        self.current_query = None
        self.search_results = None
        self.step_count = 0
