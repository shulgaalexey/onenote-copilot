"""
Content chunking service for OneNote pages.

Provides intelligent text segmentation for optimal embedding generation.
Uses LangChain text splitters with OneNote-specific optimizations.
"""

import logging
import re
import uuid
from typing import Any, List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config.logging import log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import ContentChunk, OneNotePage

logger = logging.getLogger(__name__)


class ContentChunker:
    """
    Intelligent content chunking for OneNote pages.

    Segments OneNote content into chunks optimized for embedding generation
    while preserving context and maintaining semantic coherence.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the content chunker.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()

        # Configure text splitter with OneNote-optimized separators
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            separators=[
                "\n\n\n",  # Multiple line breaks (section boundaries)
                "\n\n",    # Paragraph breaks
                "\n",      # Line breaks
                ". ",      # Sentence endings with space
                "! ",      # Exclamation sentences
                "? ",      # Question sentences
                "; ",      # Semicolon breaks
                ", ",      # Comma breaks
                " ",       # Word boundaries
                "",        # Character level (last resort)
            ]
        )

    @logged("Clean OneNote content for chunking")
    def _clean_content(self, content: str) -> str:
        """
        Clean OneNote HTML content for better chunking.

        Args:
            content: Raw HTML content from OneNote

        Returns:
            Cleaned text content
        """
        if not content:
            return ""

        # Remove excessive whitespace and normalize line breaks
        cleaned = re.sub(r'\s+', ' ', content)
        cleaned = re.sub(r'\n+', '\n', cleaned)

        # Remove common OneNote artifacts
        cleaned = re.sub(r'<[^>]+>', '', cleaned)  # Remove any remaining HTML tags
        cleaned = re.sub(r'&[a-zA-Z]+;', ' ', cleaned)  # Remove HTML entities
        cleaned = re.sub(r'\[\s*\]', '', cleaned)  # Remove empty brackets

        # Normalize spacing around punctuation
        cleaned = re.sub(r'\s*([.!?])\s*', r'\1 ', cleaned)
        cleaned = re.sub(r'\s*([,;:])\s*', r'\1 ', cleaned)

        return cleaned.strip()

    @logged("Extract metadata from OneNote page")
    def _extract_page_metadata(self, page: OneNotePage) -> dict:
        """
        Extract relevant metadata from OneNote page.

        Args:
            page: OneNote page instance

        Returns:
            Dictionary with page metadata
        """
        return {
            "notebook_name": getattr(page, 'notebook_name', 'Unknown'),
            "section_name": getattr(page, 'section_name', 'Unknown'),
            "created_date": page.created_date_time.isoformat() if page.created_date_time else None,
            "modified_date": page.last_modified_date_time.isoformat() if page.last_modified_date_time else None,
            "content_url": str(page.content_url) if page.content_url else None,
            "tags": getattr(page, 'tags', []),
            "page_level": getattr(page, 'level', 0)
        }

    @logged("Generate content chunks from OneNote page")
    def chunk_page_content(self, page: OneNotePage) -> List[ContentChunk]:
        """
        Generate content chunks from a OneNote page.

        Args:
            page: OneNote page to chunk

        Returns:
            List of content chunks

        Raises:
            ValueError: If page content is invalid
        """
        if not page or not page.title:
            raise ValueError("Page must have a valid title")

        # Get content, preferring processed content over raw HTML
        content = getattr(page, 'processed_content', page.content) or ""

        # If we still have HTML content, try to clean it
        if '<' in content and '>' in content:
            content = self._clean_content(content)

        if not content.strip():
            logger.warning(f"Page '{page.title}' has no extractable content")
            return []

        # Add title as context for better semantic understanding
        full_content = f"Title: {page.title}\n\n{content}"

        # Split content into chunks
        text_chunks = self.text_splitter.split_text(full_content)

        # Create ContentChunk objects
        chunks = []
        page_metadata = self._extract_page_metadata(page)

        for i, chunk_text in enumerate(text_chunks):
            if not chunk_text.strip():
                continue

            # Calculate positions (approximate since we're working with cleaned text)
            start_pos = i * (self.settings.chunk_size - self.settings.chunk_overlap)
            end_pos = start_pos + len(chunk_text)

            chunk = ContentChunk(
                id=str(uuid.uuid4()),
                page_id=page.id,
                page_title=page.title,
                content=chunk_text.strip(),
                chunk_index=i,
                start_position=max(0, start_pos),
                end_position=end_pos,
                metadata=page_metadata
            )
            chunks.append(chunk)

        # Limit chunks per page to prevent excessive storage
        if len(chunks) > self.settings.max_chunks_per_page:
            logger.info(f"Page '{page.title}' has {len(chunks)} chunks, limiting to {self.settings.max_chunks_per_page}")
            chunks = chunks[:self.settings.max_chunks_per_page]

        logger.info(f"Generated {len(chunks)} chunks for page '{page.title}'")
        return chunks

    @logged("Generate chunks from raw content")
    async def chunk_content(self, content: str, source_id: str, metadata: dict) -> List[ContentChunk]:
        """
        Generate content chunks from raw content string.

        Args:
            content: Raw content to chunk
            source_id: Source identifier for the content
            metadata: Metadata to attach to chunks

        Returns:
            List of content chunks

        Raises:
            ValueError: If content is invalid
        """
        if not content or not content.strip():
            logger.warning("Empty or whitespace-only content provided")
            return []

        # Clean content
        cleaned_content = self._clean_content(content)
        if not cleaned_content:
            logger.warning("Content became empty after cleaning")
            return []

        # Generate text chunks using the text splitter
        text_chunks = self.text_splitter.split_text(cleaned_content)

        if not text_chunks:
            logger.warning("No chunks generated from content")
            return []

        # Convert to ContentChunk objects
        chunks = []
        current_position = 0

        for i, chunk_text in enumerate(text_chunks):
            chunk_id = str(uuid.uuid4())

            # Calculate positions
            start_pos = current_position
            end_pos = start_pos + len(chunk_text)
            current_position = end_pos

            # Create chunk metadata
            chunk_metadata = {
                **metadata,
                'chunk_index': i,
                'chunk_id': chunk_id,
                'source_id': source_id,
                'chunk_size': len(chunk_text),
                'chunk_type': 'content'
            }

            chunk = ContentChunk(
                id=chunk_id,
                content=chunk_text,
                metadata=chunk_metadata,
                page_id=source_id,
                page_title=metadata.get('title', 'Unknown'),
                chunk_index=i,
                start_position=start_pos,
                end_position=end_pos
            )
            chunks.append(chunk)

        # Apply chunk limit if configured
        if hasattr(self.settings, 'max_chunks_per_page') and self.settings.max_chunks_per_page > 0:
            chunks = chunks[:self.settings.max_chunks_per_page]

        logger.info(f"Generated {len(chunks)} chunks from raw content")
        return chunks

    @logged("Generate content chunks from multiple pages")
    def chunk_multiple_pages(self, pages: List[OneNotePage]) -> List[ContentChunk]:
        """
        Generate content chunks from multiple OneNote pages.

        Args:
            pages: List of OneNote pages to chunk

        Returns:
            List of all content chunks from all pages
        """
        if not pages:
            return []

        all_chunks = []

        for page in pages:
            try:
                page_chunks = self.chunk_page_content(page)
                all_chunks.extend(page_chunks)
            except Exception as e:
                logger.error(f"Error chunking page '{getattr(page, 'title', 'Unknown')}': {e}")
                continue

        logger.info(f"Generated {len(all_chunks)} total chunks from {len(pages)} pages")
        return all_chunks

    @logged("Optimize chunks for embeddings")
    def optimize_chunks_for_embeddings(self, chunks: List[ContentChunk]) -> List[ContentChunk]:
        """
        Optimize content chunks for better embedding quality.

        Args:
            chunks: List of content chunks to optimize

        Returns:
            List of optimized content chunks
        """
        optimized_chunks = []

        for chunk in chunks:
            # Skip very short chunks that won't provide good embeddings
            if len(chunk.content.strip()) < 50:
                logger.debug(f"Skipping short chunk: {chunk.content[:30]}...")
                continue

            # Enhance chunk content with context
            enhanced_content = self._enhance_chunk_context(chunk)

            # Create optimized chunk
            optimized_chunk = ContentChunk(
                id=chunk.id,
                page_id=chunk.page_id,
                page_title=chunk.page_title,
                content=enhanced_content,
                chunk_index=chunk.chunk_index,
                start_position=chunk.start_position,
                end_position=chunk.end_position,
                metadata=chunk.metadata,
                created_at=chunk.created_at
            )
            optimized_chunks.append(optimized_chunk)

        logger.info(f"Optimized {len(chunks)} chunks to {len(optimized_chunks)} chunks")
        return optimized_chunks

    def _enhance_chunk_context(self, chunk: ContentChunk) -> str:
        """
        Enhance chunk content with additional context for better embeddings.

        Args:
            chunk: Content chunk to enhance

        Returns:
            Enhanced content with context
        """
        # Start with original content
        enhanced = chunk.content

        # Add page title if not already present and chunk doesn't start with title
        if not enhanced.startswith("Title:") and chunk.page_title:
            enhanced = f"From page '{chunk.page_title}': {enhanced}"

        # Add notebook/section context if available
        metadata = chunk.metadata
        if isinstance(metadata, dict):
            context_parts = []

            if metadata.get('notebook_name') and metadata['notebook_name'] != 'Unknown':
                context_parts.append(f"Notebook: {metadata['notebook_name']}")

            if metadata.get('section_name') and metadata['section_name'] != 'Unknown':
                context_parts.append(f"Section: {metadata['section_name']}")

            if context_parts:
                context_prefix = " | ".join(context_parts)
                enhanced = f"[{context_prefix}] {enhanced}"

        return enhanced

    def get_chunking_stats(self, chunks: List[ContentChunk]) -> dict:
        """
        Get statistics about the chunking results.

        Args:
            chunks: List of content chunks

        Returns:
            Dictionary with chunking statistics
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "total_pages": 0,
                "average_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0
            }

        chunk_sizes = [len(chunk.content) for chunk in chunks]
        unique_pages = len(set(chunk.page_id for chunk in chunks))

        return {
            "total_chunks": len(chunks),
            "total_pages": unique_pages,
            "average_chunk_size": sum(chunk_sizes) // len(chunk_sizes),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes),
            "chunks_per_page": len(chunks) / unique_pages if unique_pages > 0 else 0
        }
