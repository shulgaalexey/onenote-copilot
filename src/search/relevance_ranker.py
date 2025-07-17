"""
Relevance ranking service for search results.

Provides intelligent ranking and scoring of search results using multiple
relevance signals including semantic similarity, keyword matching, and metadata.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..config.logging import log_performance, logged
from ..config.settings import get_settings
from ..models.onenote import QueryIntent, SearchResult, SemanticSearchResult

logger = logging.getLogger(__name__)


class RelevanceRanker:
    """
    Intelligent relevance ranking for search results.

    Combines multiple relevance signals to provide optimal ranking of
    search results for user queries.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the relevance ranker.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()

        # Ranking weights for different signals
        self.ranking_weights = {
            'semantic_similarity': 0.4,
            'keyword_match': 0.3,
            'title_match': 0.2,
            'recency': 0.1
        }

    @logged("Rank semantic search results")
    async def rank_semantic_results(
        self,
        results: List[SemanticSearchResult],
        query_intent: QueryIntent
    ) -> List[SemanticSearchResult]:
        """
        Rank semantic search results using multiple relevance signals.

        Args:
            results: List of semantic search results
            query_intent: Processed query intent

        Returns:
            Ranked list of semantic search results
        """
        if not results:
            return []

        start_time = time.time()

        # Calculate relevance scores for each result
        scored_results = []

        for result in results:
            relevance_score = self._calculate_relevance_score(result, query_intent)

            # Update the result with new ranking
            enhanced_result = SemanticSearchResult(
                chunk=result.chunk,
                similarity_score=result.similarity_score,
                search_type=result.search_type,
                rank=result.rank,
                page=result.page
            )

            scored_results.append((enhanced_result, relevance_score))

        # Sort by relevance score (descending)
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Update ranks and return results
        ranked_results = []
        for rank, (result, score) in enumerate(scored_results, 1):
            result.rank = rank
            ranked_results.append(result)

        log_performance(
            "rank_semantic_results",
            time.time() - start_time,
            results_count=len(results),
            query_keywords=len(query_intent.keywords),
            intent_type=query_intent.intent_type
        )

        logger.debug(f"Ranked {len(results)} semantic search results")
        return ranked_results

    def _calculate_relevance_score(
        self,
        result: SemanticSearchResult,
        query_intent: QueryIntent
    ) -> float:
        """
        Calculate overall relevance score for a search result.

        Args:
            result: Semantic search result
            query_intent: Processed query intent

        Returns:
            Overall relevance score (0.0 to 1.0)
        """
        scores = {}

        # Semantic similarity score (already calculated)
        scores['semantic_similarity'] = result.similarity_score

        # Keyword matching score
        scores['keyword_match'] = self._calculate_keyword_match_score(
            result.chunk.content,
            result.chunk.page_title,
            query_intent.keywords
        )

        # Title matching score
        scores['title_match'] = self._calculate_title_match_score(
            result.chunk.page_title,
            query_intent.keywords
        )

        # Recency score (if page data available)
        scores['recency'] = self._calculate_recency_score(result)

        # Calculate weighted average
        weighted_score = 0.0
        for signal, weight in self.ranking_weights.items():
            if signal in scores:
                weighted_score += scores[signal] * weight

        return min(weighted_score, 1.0)

    def _calculate_keyword_match_score(
        self,
        content: str,
        title: str,
        keywords: List[str]
    ) -> float:
        """
        Calculate keyword matching score for content.

        Args:
            content: Content text
            title: Page title
            keywords: Query keywords

        Returns:
            Keyword match score (0.0 to 1.0)
        """
        if not keywords:
            return 0.0

        content_lower = content.lower()
        title_lower = title.lower()

        matches = 0
        for keyword in keywords:
            keyword_lower = keyword.lower()

            # Count matches in content and title
            content_matches = content_lower.count(keyword_lower)
            title_matches = title_lower.count(keyword_lower)

            if content_matches > 0 or title_matches > 0:
                matches += 1

        return matches / len(keywords)

    def _calculate_title_match_score(
        self,
        title: str,
        keywords: List[str]
    ) -> float:
        """
        Calculate title matching score.

        Args:
            title: Page title
            keywords: Query keywords

        Returns:
            Title match score (0.0 to 1.0)
        """
        if not keywords or not title:
            return 0.0

        title_lower = title.lower()
        matches = 0

        for keyword in keywords:
            if keyword.lower() in title_lower:
                matches += 1

        # Give higher scores for exact title matches
        if matches == len(keywords) and len(keywords) > 1:
            return 1.0

        return matches / len(keywords)

    def _calculate_recency_score(self, result: SemanticSearchResult) -> float:
        """
        Calculate recency score based on page modification date.

        Args:
            result: Semantic search result

        Returns:
            Recency score (0.0 to 1.0)
        """
        # If no page data or date available, return neutral score
        if not result.page or not hasattr(result.page, 'last_modified_date_time'):
            return 0.5

        try:
            from datetime import datetime, timezone

            modified_date = result.page.last_modified_date_time
            if not modified_date:
                return 0.5

            # Ensure timezone awareness
            if modified_date.tzinfo is None:
                modified_date = modified_date.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            days_ago = (now - modified_date).days

            # Score based on recency (higher scores for more recent content)
            if days_ago <= 7:
                return 1.0  # Within a week
            elif days_ago <= 30:
                return 0.8  # Within a month
            elif days_ago <= 90:
                return 0.6  # Within 3 months
            elif days_ago <= 365:
                return 0.4  # Within a year
            else:
                return 0.2  # Older than a year

        except Exception as e:
            logger.debug(f"Error calculating recency score: {e}")
            return 0.5

    @logged("Combine hybrid search results")
    async def combine_hybrid_results(
        self,
        semantic_results: List[SemanticSearchResult],
        keyword_results: List[SearchResult],
        semantic_weight: float,
        keyword_weight: float,
        limit: int
    ) -> List[SemanticSearchResult]:
        """
        Combine and rank results from semantic and keyword searches.

        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            semantic_weight: Weight for semantic results
            keyword_weight: Weight for keyword results
            limit: Maximum number of results to return

        Returns:
            Combined and ranked results
        """
        start_time = time.time()

        # Convert keyword results to semantic format
        semantic_from_keyword = []

        for search_result in keyword_results:
            if not search_result.pages:
                continue

            for i, page in enumerate(search_result.pages):
                # Create a simple chunk from page
                from ..models.onenote import ContentChunk
                chunk = ContentChunk(
                    id=f"{page.id}_keyword_{i}",
                    page_id=page.id,
                    page_title=page.title,
                    content=getattr(page, 'processed_content', page.content) or page.title,
                    chunk_index=0,
                    start_position=0,
                    end_position=len(page.title),
                    metadata={"source": "keyword_search"}
                )

                semantic_result = SemanticSearchResult(
                    chunk=chunk,
                    similarity_score=0.8 - (i * 0.05),  # Decreasing score based on rank
                    search_type="keyword",
                    rank=i + 1,
                    page=page
                )
                semantic_from_keyword.append(semantic_result)

        # Combine results with weighted scoring
        all_results = []
        seen_page_ids = set()

        # Add semantic results with their weights
        for result in semantic_results:
            if result.chunk.page_id not in seen_page_ids:
                weighted_score = result.similarity_score * semantic_weight
                all_results.append((result, weighted_score, "semantic"))
                seen_page_ids.add(result.chunk.page_id)

        # Add keyword results with their weights (avoid duplicates)
        for result in semantic_from_keyword:
            if result.chunk.page_id not in seen_page_ids:
                weighted_score = result.similarity_score * keyword_weight
                all_results.append((result, weighted_score, "keyword"))
                seen_page_ids.add(result.chunk.page_id)

        # Sort by weighted score
        all_results.sort(key=lambda x: x[1], reverse=True)

        # Create final results with updated ranks and search type
        combined_results = []
        for rank, (result, score, source) in enumerate(all_results[:limit], 1):
            enhanced_result = SemanticSearchResult(
                chunk=result.chunk,
                similarity_score=score,  # Use weighted score
                search_type=f"hybrid_{source}",
                rank=rank,
                page=result.page
            )
            combined_results.append(enhanced_result)

        log_performance(
            "combine_hybrid_results",
            time.time() - start_time,
            semantic_count=len(semantic_results),
            keyword_count=len(keyword_results),
            combined_count=len(combined_results),
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
            limit=limit
        )

        logger.debug(f"Combined {len(semantic_results)} semantic + {len(keyword_results)} keyword results into {len(combined_results)} hybrid results")
        return combined_results

    @logged("Apply query filters to results")
    async def apply_query_filters(
        self,
        results: List[SemanticSearchResult],
        query_intent: QueryIntent
    ) -> List[SemanticSearchResult]:
        """
        Apply query-specific filters to search results.

        Args:
            results: Search results to filter
            query_intent: Processed query intent

        Returns:
            Filtered search results
        """
        if not results:
            return []

        filtered_results = results[:]

        # Apply temporal filters
        if query_intent.temporal_filters:
            filtered_results = self._apply_temporal_filters(
                filtered_results,
                query_intent.temporal_filters
            )

        # Apply content filters
        if query_intent.content_filters:
            filtered_results = self._apply_content_filters(
                filtered_results,
                query_intent.content_filters
            )

        logger.debug(f"Applied filters: {len(results)} -> {len(filtered_results)} results")
        return filtered_results

    def _apply_temporal_filters(
        self,
        results: List[SemanticSearchResult],
        temporal_filters: Dict[str, Any]
    ) -> List[SemanticSearchResult]:
        """
        Apply temporal filters to results.

        Args:
            results: Results to filter
            temporal_filters: Temporal filter criteria

        Returns:
            Filtered results
        """
        # For now, return all results (temporal filtering would require
        # implementing date parsing and comparison logic)
        logger.debug(f"Temporal filters applied: {temporal_filters}")
        return results

    def _apply_content_filters(
        self,
        results: List[SemanticSearchResult],
        content_filters: Dict[str, Any]
    ) -> List[SemanticSearchResult]:
        """
        Apply content type filters to results.

        Args:
            results: Results to filter
            content_filters: Content filter criteria

        Returns:
            Filtered results
        """
        # For now, return all results (content filtering would require
        # implementing content type detection logic)
        logger.debug(f"Content filters applied: {content_filters}")
        return results

    def get_ranking_stats(self) -> Dict[str, Any]:
        """
        Get ranking statistics and configuration.

        Returns:
            Dictionary with ranking metrics
        """
        return {
            "ranking_weights": self.ranking_weights,
            "total_weight": sum(self.ranking_weights.values())
        }
