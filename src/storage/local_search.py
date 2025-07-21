"""
Local OneNote search engine for cached content.

Provides fast full-text search capabilities over locally cached OneNote content,
integrating SQLite FTS for text search with the existing semantic search framework.
"""

import asyncio
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config.logging import log_performance, logged
from ..config.settings import Settings, get_settings
from ..models.cache import CachedPage, CacheSearchResult, PageMatch
from ..models.onenote import (
    ContentChunk,
    OneNotePage,
    SearchResult,
    SemanticSearchResult
)
from .cache_manager import OneNoteCacheManager

logger = logging.getLogger(__name__)


class LocalSearchError(Exception):
    """Exception raised when local search operations fail."""
    pass


class LocalOneNoteSearch:
    """
    Local search engine for cached OneNote content.
    
    Provides fast full-text search using SQLite FTS5 with integration
    to existing semantic search infrastructure.
    """

    def __init__(
        self, 
        settings: Optional[Settings] = None,
        cache_manager: Optional[OneNoteCacheManager] = None
    ):
        """
        Initialize the local search engine.

        Args:
            settings: Optional settings instance
            cache_manager: Optional cache manager instance
        """
        self.settings = settings or get_settings()
        self.cache_manager = cache_manager or OneNoteCacheManager(self.settings)
        
        # Database path for search index
        self.db_path = self.cache_manager.cache_root / "search_index.db"
        self._connection: Optional[sqlite3.Connection] = None
        
        # Search statistics
        self._search_count = 0
        self._index_operations = 0
        
    async def initialize(self) -> None:
        """
        Initialize the search engine and create database schema.
        
        Raises:
            LocalSearchError: If initialization fails
        """
        try:
            # Ensure cache directory exists
            self.cache_manager.cache_root.mkdir(parents=True, exist_ok=True)
            
            # Initialize database schema
            await self._create_schema()
            
            logger.info(f"Local search engine initialized with database: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize local search engine: {e}")
            raise LocalSearchError(f"Initialization failed: {e}")

    async def _create_schema(self) -> None:
        """Create the search database schema."""
        try:
            conn = await self._get_connection()
            
            # Create FTS5 table for full-text search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS page_content_fts USING fts5(
                    page_id UNINDEXED,
                    notebook_id UNINDEXED,
                    section_id UNINDEXED,
                    page_title,
                    content,
                    tags,
                    created_time UNINDEXED,
                    modified_time UNINDEXED
                );
            """)
            
            # Create metadata table for search optimization
            conn.execute("""
                CREATE TABLE IF NOT EXISTS page_metadata (
                    page_id TEXT PRIMARY KEY,
                    notebook_id TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    notebook_name TEXT,
                    section_name TEXT,
                    page_title TEXT NOT NULL,
                    content_length INTEGER,
                    asset_count INTEGER,
                    link_count INTEGER,
                    created_time TEXT,
                    modified_time TEXT,
                    cached_time TEXT,
                    FOREIGN KEY (page_id) REFERENCES page_content_fts(page_id)
                );
            """)
            
            # Create index for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_page_metadata_notebook 
                ON page_metadata(notebook_id);
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_page_metadata_section 
                ON page_metadata(section_id);
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_page_metadata_modified 
                ON page_metadata(modified_time);
            """)
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to create search schema: {e}")
            raise LocalSearchError(f"Schema creation failed: {e}")

    async def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with FTS5 enabled."""
        if self._connection is None or self._connection.execute("PRAGMA schema_version").fetchone() is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._connection.row_factory = sqlite3.Row
            
            # Enable FTS5 and optimize settings
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL") 
            self._connection.execute("PRAGMA cache_size=10000")
            self._connection.execute("PRAGMA temp_store=memory")
            
        return self._connection

    @logged("Index cached page for search")
    async def index_page(self, cached_page: CachedPage) -> bool:
        """
        Index a cached page for full-text search.

        Args:
            cached_page: Cached page to index

        Returns:
            True if indexing succeeded, False otherwise

        Raises:
            LocalSearchError: If indexing fails critically
        """
        if not cached_page.metadata.id:
            raise LocalSearchError("Page must have a valid page_id")

        start_time = time.time()

        try:
            conn = await self._get_connection()
            
            # Remove existing entries for this page
            conn.execute(
                "DELETE FROM page_content_fts WHERE page_id = ?",
                (cached_page.metadata.id,)
            )
            conn.execute(
                "DELETE FROM page_metadata WHERE page_id = ?", 
                (cached_page.metadata.id,)
            )
            
            # Extract searchable content
            content_text = self._extract_searchable_content(cached_page)
            tags_text = ""  # Tags not available in current model
            
            # Get parent info
            notebook_id = cached_page.metadata.parent_notebook.get("id", "")
            notebook_name = cached_page.metadata.parent_notebook.get("name", "")
            section_id = cached_page.metadata.parent_section.get("id", "")
            section_name = cached_page.metadata.parent_section.get("name", "")
            
            # Insert into FTS table
            conn.execute("""
                INSERT INTO page_content_fts (
                    page_id, notebook_id, section_id, page_title, 
                    content, tags, created_time, modified_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cached_page.metadata.id,
                notebook_id,
                section_id,
                cached_page.metadata.title,
                content_text,
                tags_text,
                cached_page.metadata.created_date_time.isoformat(),
                cached_page.metadata.last_modified_date_time.isoformat()
            ))
            
            # Insert metadata
            conn.execute("""
                INSERT INTO page_metadata (
                    page_id, notebook_id, section_id, notebook_name, section_name,
                    page_title, content_length, asset_count, link_count,
                    created_time, modified_time, cached_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cached_page.metadata.id,
                notebook_id,
                section_id,
                notebook_name,
                section_name,
                cached_page.metadata.title,
                len(content_text),
                len(cached_page.metadata.attachments or []),
                len(cached_page.metadata.internal_links or []) + len(cached_page.metadata.external_links or []),
                cached_page.metadata.created_date_time.isoformat(),
                cached_page.metadata.last_modified_date_time.isoformat(),
                cached_page.metadata.cached_at.isoformat()
            ))
            
            conn.commit()
            self._index_operations += 1
            
            log_performance(
                "local_search_index_page",
                time.time() - start_time,
                page_id=cached_page.metadata.id,
                content_length=len(content_text),
                page_title=cached_page.metadata.title
            )
            
            logger.debug(f"Indexed page '{cached_page.metadata.title}' ({cached_page.metadata.id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index page '{cached_page.metadata.title}': {e}")
            return False

    def _extract_searchable_content(self, cached_page: CachedPage) -> str:
        """
        Extract searchable text content from a cached page.
        
        Args:
            cached_page: Cached page to extract content from
            
        Returns:
            Searchable text content
        """
        content_parts = []
        
        # Add page title (weighted higher in searches)
        if cached_page.metadata.title:
            content_parts.append(cached_page.metadata.title)
        
        # Add markdown content
        if cached_page.markdown_content:
            content_parts.append(cached_page.markdown_content)
            
        # Add internal link text context
        if cached_page.metadata.internal_links:
            link_texts = [
                link.link_text for link in cached_page.metadata.internal_links 
                if link.link_text and link.link_text.strip()
            ]
            if link_texts:
                content_parts.append(" ".join(link_texts))
                
        # Add external link text context
        if cached_page.metadata.external_links:
            link_texts = [
                link.link_text for link in cached_page.metadata.external_links 
                if link.link_text and link.link_text.strip()
            ]
            if link_texts:
                content_parts.append(" ".join(link_texts))
        
        # Add asset filenames
        if cached_page.metadata.attachments:
            filenames = [
                asset.filename for asset in cached_page.metadata.attachments
                if asset.filename and asset.filename.strip()
            ]
            if filenames:
                content_parts.append(" ".join(filenames))
                
        return " ".join(content_parts)

    @logged("Search cached content")
    async def search(
        self,
        query: str,
        limit: int = None,
        notebook_ids: Optional[List[str]] = None,
        section_ids: Optional[List[str]] = None,
        title_only: bool = False
    ) -> List[SemanticSearchResult]:
        """
        Search cached OneNote content.

        Args:
            query: Search query
            limit: Maximum number of results (uses setting default if None)
            notebook_ids: Optional list of notebook IDs to search within
            section_ids: Optional list of section IDs to search within  
            title_only: Whether to search only page titles

        Returns:
            List of semantic search results

        Raises:
            LocalSearchError: If search fails
        """
        if not query.strip():
            raise LocalSearchError("Search query cannot be empty")

        limit = limit or self.settings.semantic_search_limit
        start_time = time.time()

        try:
            conn = await self._get_connection()
            
            # Build FTS query
            fts_query = self._build_fts_query(query, title_only)
            
            # Build SQL with filters
            sql = self._build_search_sql(notebook_ids, section_ids)
            params = [fts_query]
            
            # Add filter parameters
            if notebook_ids:
                params.extend(notebook_ids)
            if section_ids:
                params.extend(section_ids)
                
            # Add limit
            params.append(limit)
            
            # Execute search
            cursor = conn.execute(sql, params)
            results = cursor.fetchall()
            
            # Convert to semantic search results
            search_results = []
            for i, row in enumerate(results):
                # Create content chunk from search result
                chunk = ContentChunk(
                    id=f"{row['page_id']}_local_search",
                    page_id=row['page_id'],
                    page_title=row['page_title'],
                    content=row['content'][:500] + "..." if len(row['content']) > 500 else row['content'],
                    chunk_index=0,
                    start_position=0,
                    end_position=min(500, len(row['content']))
                )
                
                # Create OneNote page representation
                page = OneNotePage(
                    id=row['page_id'],
                    title=row['page_title'],
                    content="",  # Content is in chunk
                    createdDateTime=row['created_time'],
                    lastModifiedDateTime=row['modified_time']
                )
                
                # Calculate relevance score based on FTS rank
                similarity_score = max(0.1, 1.0 - (i * 0.05))  # Decreasing score
                
                result = SemanticSearchResult(
                    chunk=chunk,
                    similarity_score=similarity_score,
                    search_type="local_cache_fts",
                    rank=i + 1,
                    page=page
                )
                
                search_results.append(result)
            
            self._search_count += 1
            
            log_performance(
                "local_search",
                time.time() - start_time,
                query_length=len(query),
                results_found=len(search_results),
                limit=limit,
                title_only=title_only,
                filtered_notebooks=len(notebook_ids) if notebook_ids else 0,
                filtered_sections=len(section_ids) if section_ids else 0
            )
            
            logger.info(f"Local search for '{query}' found {len(search_results)} results")
            return search_results
            
        except Exception as e:
            logger.error(f"Local search failed: {e}")
            raise LocalSearchError(f"Search failed: {e}")

    def _build_fts_query(self, query: str, title_only: bool = False) -> str:
        """
        Build FTS5 query from user input.
        
        Args:
            query: User search query
            title_only: Whether to search only titles
            
        Returns:
            FTS5 query string
        """
        # Clean and prepare query terms
        terms = [term.strip() for term in query.split() if term.strip()]
        
        if not terms:
            return query  # Fallback to original
            
        # Handle quoted phrases
        if '"' in query:
            return query  # Pass through quoted queries as-is
            
        # For title-only search, prefix with column
        if title_only:
            if len(terms) == 1:
                return f'page_title:{terms[0]}*'
            else:
                return 'page_title:("' + '" OR "'.join(terms) + '")'
        
        # Build phrase query for better relevance
        if len(terms) == 1:
            return f'{terms[0]}*'  # Prefix matching for single term
        else:
            # Combine terms as phrase with OR fallback
            phrase = '"' + " ".join(terms) + '"'
            individual = " OR ".join(f"{term}*" for term in terms)
            return f'({phrase}) OR ({individual})'

    def _build_search_sql(
        self, 
        notebook_ids: Optional[List[str]] = None,
        section_ids: Optional[List[str]] = None
    ) -> str:
        """
        Build SQL query with optional filters.
        
        Args:
            notebook_ids: Optional notebook ID filters
            section_ids: Optional section ID filters
            
        Returns:
            SQL query string
        """
        base_sql = """
            SELECT 
                f.page_id, f.notebook_id, f.section_id, f.page_title, 
                f.content, f.created_time, f.modified_time,
                m.notebook_name, m.section_name, m.content_length,
                rank
            FROM page_content_fts f
            LEFT JOIN page_metadata m ON f.page_id = m.page_id
            WHERE page_content_fts MATCH ?
        """
        
        conditions = []
        
        if notebook_ids:
            placeholders = ",".join("?" * len(notebook_ids))
            conditions.append(f"f.notebook_id IN ({placeholders})")
            
        if section_ids:
            placeholders = ",".join("?" * len(section_ids))
            conditions.append(f"f.section_id IN ({placeholders})")
        
        if conditions:
            base_sql += " AND " + " AND ".join(conditions)
            
        base_sql += " ORDER BY rank LIMIT ?"
        
        return base_sql

    @logged("Get search statistics") 
    async def get_search_stats(self) -> Dict[str, Any]:
        """
        Get local search engine statistics.
        
        Returns:
            Dictionary with search metrics
        """
        try:
            conn = await self._get_connection()
            
            # Get index statistics
            cursor = conn.execute("SELECT COUNT(*) as page_count FROM page_content_fts")
            page_count = cursor.fetchone()['page_count']
            
            cursor = conn.execute("SELECT COUNT(DISTINCT notebook_id) as notebook_count FROM page_metadata")
            notebook_count = cursor.fetchone()['notebook_count']
            
            cursor = conn.execute("SELECT COUNT(DISTINCT section_id) as section_count FROM page_metadata") 
            section_count = cursor.fetchone()['section_count']
            
            cursor = conn.execute("SELECT AVG(content_length) as avg_content_length FROM page_metadata")
            avg_content_length = cursor.fetchone()['avg_content_length'] or 0
            
            return {
                "total_searches": self._search_count,
                "index_operations": self._index_operations,
                "indexed_pages": page_count,
                "indexed_notebooks": notebook_count,
                "indexed_sections": section_count,
                "average_content_length": round(avg_content_length, 2),
                "database_path": str(self.db_path),
                "database_size_mb": round(self.db_path.stat().st_size / (1024 * 1024), 2) if self.db_path.exists() else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get search statistics: {e}")
            return {
                "total_searches": self._search_count,
                "index_operations": self._index_operations,
                "error": str(e)
            }

    async def rebuild_index(self, user_id: str) -> Dict[str, Any]:
        """
        Rebuild the search index from cached content.
        
        Args:
            user_id: User identifier to rebuild index for
            
        Returns:
            Dictionary with rebuild statistics
            
        Raises:
            LocalSearchError: If rebuild fails
        """
        start_time = time.time()
        
        try:
            # Clear existing index
            conn = await self._get_connection()
            conn.execute("DELETE FROM page_content_fts")
            conn.execute("DELETE FROM page_metadata")
            conn.commit()
            
            # Get all cached pages for user
            all_pages = await self.cache_manager.get_all_cached_pages(user_id)
            
            # Index all pages
            indexed_count = 0
            failed_count = 0
            
            for cached_page in all_pages:
                try:
                    if await self.index_page(cached_page):
                        indexed_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Failed to index page during rebuild: {e}")
                    failed_count += 1
            
            log_performance(
                "local_search_rebuild_index",
                time.time() - start_time,
                user_id=user_id,
                total_pages=len(all_pages),
                indexed_pages=indexed_count,
                failed_pages=failed_count
            )
            
            logger.info(f"Rebuilt search index: {indexed_count} pages indexed, {failed_count} failed")
            
            return {
                "total_pages": len(all_pages),
                "indexed_pages": indexed_count,
                "failed_pages": failed_count,
                "rebuild_time_seconds": round(time.time() - start_time, 2),
                "success_rate": round(indexed_count / len(all_pages) * 100, 1) if all_pages else 100
            }
            
        except Exception as e:
            logger.error(f"Failed to rebuild search index: {e}")
            raise LocalSearchError(f"Index rebuild failed: {e}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Local search database connection closed")
