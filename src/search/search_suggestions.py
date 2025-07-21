"""
Search suggestions system for OneNote cache.

Provides intelligent query suggestions, search history management,
and auto-completion features for improved search experience.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import Counter
import re

from ..models.cache import CachedPage
from ..storage.local_search import LocalOneNoteSearch
from ..config.settings import Settings

logger = logging.getLogger(__name__)


class SuggestionType(str, Enum):
    """Types of search suggestions."""
    HISTORY = "history"
    AUTO_COMPLETE = "auto_complete"
    SIMILAR = "similar"
    POPULAR = "popular"
    CONTEXTUAL = "contextual"


@dataclass
class SearchSuggestion:
    """A search suggestion with metadata."""
    
    query: str
    suggestion_type: SuggestionType
    score: float = 0.0
    frequency: int = 0
    last_used: Optional[datetime] = None
    result_count: int = 0
    success_rate: float = 0.0
    
    # Contextual information
    related_notebooks: Set[str] = field(default_factory=set)
    related_sections: Set[str] = field(default_factory=set)
    common_terms: Set[str] = field(default_factory=set)


@dataclass
class SearchHistory:
    """Search history entry."""
    
    query: str
    timestamp: datetime
    result_count: int
    success: bool
    execution_time: float = 0.0
    
    # User interaction metrics
    clicked_results: int = 0
    session_id: Optional[str] = None


class SearchSuggestions:
    """
    Search suggestions and history management system.
    
    Provides intelligent query suggestions based on:
    - Search history
    - Popular searches
    - Auto-completion from content
    - Contextual suggestions
    """

    def __init__(self, 
                 settings: Optional[Settings] = None,
                 local_search: Optional[LocalOneNoteSearch] = None,
                 max_history: int = 1000,
                 max_suggestions: int = 10):
        """
        Initialize search suggestions system.

        Args:
            settings: Configuration settings
            local_search: Local search instance for content analysis
            max_history: Maximum number of history entries to keep
            max_suggestions: Maximum suggestions per request
        """
        self.settings = settings or Settings()
        self.local_search = local_search
        self.max_history = max_history
        self.max_suggestions = max_suggestions
        
        # Storage
        self.history_file = Path(self.settings.cache_path) / "search_history.json"
        self.suggestions_file = Path(self.settings.cache_path) / "suggestions_cache.json"
        
        # In-memory caches
        self.search_history: List[SearchHistory] = []
        self.suggestion_cache: Dict[str, List[SearchSuggestion]] = {}
        self.term_frequency: Counter = Counter()
        self.query_patterns: Counter = Counter()  # Changed to Counter
        
        # Statistics
        self.stats = {
            "suggestions_generated": 0,
            "suggestions_used": 0,
            "history_entries": 0,
            "cache_hits": 0
        }
        
        # Load existing data
        self._load_history()
        self._load_suggestions_cache()
        
        logger.info("Initialized search suggestions system")

    async def get_suggestions(self, 
                            query: str,
                            suggestion_types: Optional[List[SuggestionType]] = None,
                            max_results: Optional[int] = None) -> List[SearchSuggestion]:
        """
        Get search suggestions for a query.

        Args:
            query: Partial or complete query
            suggestion_types: Types of suggestions to include
            max_results: Maximum suggestions to return

        Returns:
            List of ranked suggestions
        """
        try:
            start_time = datetime.utcnow()
            max_results = max_results or self.max_suggestions
            suggestion_types = suggestion_types or list(SuggestionType)
            
            logger.debug(f"Getting suggestions for query: '{query}'")
            
            # Check cache first
            cache_key = f"{query.lower()}:{','.join(sorted(suggestion_types))}"
            if cache_key in self.suggestion_cache:
                self.stats["cache_hits"] += 1
                return self.suggestion_cache[cache_key][:max_results]
            
            suggestions = []
            
            # History-based suggestions
            if SuggestionType.HISTORY in suggestion_types:
                history_suggestions = await self._get_history_suggestions(query)
                suggestions.extend(history_suggestions)
            
            # Auto-completion suggestions
            if SuggestionType.AUTO_COMPLETE in suggestion_types:
                autocomplete_suggestions = await self._get_autocomplete_suggestions(query)
                suggestions.extend(autocomplete_suggestions)
            
            # Similar query suggestions
            if SuggestionType.SIMILAR in suggestion_types:
                similar_suggestions = await self._get_similar_suggestions(query)
                suggestions.extend(similar_suggestions)
            
            # Popular query suggestions
            if SuggestionType.POPULAR in suggestion_types:
                popular_suggestions = await self._get_popular_suggestions(query)
                suggestions.extend(popular_suggestions)
            
            # Contextual suggestions
            if SuggestionType.CONTEXTUAL in suggestion_types:
                contextual_suggestions = await self._get_contextual_suggestions(query)
                suggestions.extend(contextual_suggestions)
            
            # Deduplicate and rank
            suggestions = self._deduplicate_suggestions(suggestions)
            suggestions = self._rank_suggestions(suggestions, query)
            
            # Limit results
            suggestions = suggestions[:max_results]
            
            # Cache results
            self.suggestion_cache[cache_key] = suggestions
            
            # Update statistics
            self.stats["suggestions_generated"] += len(suggestions)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.debug(f"Generated {len(suggestions)} suggestions in {processing_time:.3f}s")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Suggestion generation failed: {e}")
            return []

    async def record_search(self, 
                          query: str,
                          result_count: int,
                          success: bool,
                          execution_time: float = 0.0,
                          clicked_results: int = 0,
                          session_id: Optional[str] = None) -> None:
        """
        Record a search query in history.

        Args:
            query: Search query
            result_count: Number of results returned
            success: Whether search was successful
            execution_time: Search execution time
            clicked_results: Number of results user clicked
            session_id: Session identifier
        """
        try:
            # Create history entry
            history_entry = SearchHistory(
                query=query,
                timestamp=datetime.utcnow(),
                result_count=result_count,
                success=success,
                execution_time=execution_time,
                clicked_results=clicked_results,
                session_id=session_id
            )
            
            # Add to history
            self.search_history.append(history_entry)
            
            # Update term frequency
            terms = self._extract_terms(query)
            self.term_frequency.update(terms)
            
            # Update query patterns
            normalized_query = self._normalize_query(query)
            self.query_patterns[normalized_query] += 1
            
            # Maintain history size limit
            if len(self.search_history) > self.max_history:
                self.search_history = self.search_history[-self.max_history:]
            
            # Clear relevant cache entries
            self._invalidate_suggestion_cache(query)
            
            # Update statistics
            self.stats["history_entries"] += 1
            
            logger.debug(f"Recorded search: '{query}' -> {result_count} results")
            
        except Exception as e:
            logger.error(f"Failed to record search: {e}")

    async def get_search_history(self, 
                               limit: int = 50,
                               successful_only: bool = False,
                               time_range: Optional[Tuple[datetime, datetime]] = None) -> List[SearchHistory]:
        """
        Get search history with filtering options.

        Args:
            limit: Maximum entries to return
            successful_only: Only return successful searches
            time_range: Optional time range filter

        Returns:
            Filtered search history
        """
        try:
            filtered_history = self.search_history.copy()
            
            # Filter by success
            if successful_only:
                filtered_history = [h for h in filtered_history if h.success]
            
            # Filter by time range
            if time_range:
                start_time, end_time = time_range
                filtered_history = [
                    h for h in filtered_history 
                    if start_time <= h.timestamp <= end_time
                ]
            
            # Sort by timestamp (most recent first)
            filtered_history.sort(key=lambda x: x.timestamp, reverse=True)
            
            # Apply limit
            return filtered_history[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get search history: {e}")
            return []

    async def get_popular_queries(self, 
                                limit: int = 20,
                                time_range: Optional[timedelta] = None) -> List[Tuple[str, int]]:
        """
        Get popular search queries.

        Args:
            limit: Maximum queries to return
            time_range: Optional time range (e.g., last 7 days)

        Returns:
            List of (query, frequency) tuples
        """
        try:
            if time_range:
                cutoff_time = datetime.utcnow() - time_range
                recent_history = [
                    h for h in self.search_history 
                    if h.timestamp >= cutoff_time
                ]
            else:
                recent_history = self.search_history
            
            # Count query frequencies
            query_counts = Counter(
                self._normalize_query(h.query) for h in recent_history
            )
            
            # Return most common
            return query_counts.most_common(limit)
            
        except Exception as e:
            logger.error(f"Failed to get popular queries: {e}")
            return []

    async def get_suggestion_analytics(self) -> Dict[str, Any]:
        """Get analytics about suggestion usage and effectiveness."""
        try:
            total_suggestions = self.stats["suggestions_generated"]
            used_suggestions = self.stats["suggestions_used"]
            
            # Calculate usage rate
            usage_rate = used_suggestions / total_suggestions if total_suggestions > 0 else 0.0
            
            # Analyze query patterns
            pattern_analysis = {
                "most_common_terms": self.term_frequency.most_common(10),
                "most_common_patterns": list(self.query_patterns.items())[:10]
            }
            
            # Analyze search success
            recent_history = self.search_history[-100:] if self.search_history else []
            success_rate = sum(1 for h in recent_history if h.success) / len(recent_history) if recent_history else 0.0
            
            avg_results = sum(h.result_count for h in recent_history) / len(recent_history) if recent_history else 0.0
            
            return {
                "statistics": dict(self.stats),
                "usage_rate": usage_rate,
                "success_rate": success_rate,
                "average_results": avg_results,
                "total_history_entries": len(self.search_history),
                "cache_size": len(self.suggestion_cache),
                "pattern_analysis": pattern_analysis
            }
            
        except Exception as e:
            logger.error(f"Failed to get suggestion analytics: {e}")
            return {}

    def clear_history(self, older_than: Optional[timedelta] = None) -> int:
        """
        Clear search history.

        Args:
            older_than: Optional time threshold (clear entries older than this)

        Returns:
            Number of entries removed
        """
        try:
            if older_than is None:
                # Clear all history
                removed_count = len(self.search_history)
                self.search_history.clear()
                self.term_frequency.clear()
                self.query_patterns.clear()
            else:
                # Clear old entries
                cutoff_time = datetime.utcnow() - older_than
                old_count = len(self.search_history)
                self.search_history = [
                    h for h in self.search_history 
                    if h.timestamp >= cutoff_time
                ]
                removed_count = old_count - len(self.search_history)
                
                # Rebuild term frequency and patterns
                self._rebuild_frequency_data()
            
            # Clear suggestion cache
            self.suggestion_cache.clear()
            
            logger.info(f"Cleared {removed_count} history entries")
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            return 0

    def save_data(self) -> None:
        """Save history and cache data to disk."""
        try:
            self._save_history()
            self._save_suggestions_cache()
            logger.debug("Search data saved to disk")
        except Exception as e:
            logger.error(f"Failed to save search data: {e}")

    # Private helper methods

    async def _get_history_suggestions(self, query: str) -> List[SearchSuggestion]:
        """Get suggestions based on search history."""
        suggestions = []
        query_lower = query.lower()
        
        for history_entry in self.search_history:
            if history_entry.query.lower().startswith(query_lower) and history_entry.query.lower() != query_lower:
                suggestion = SearchSuggestion(
                    query=history_entry.query,
                    suggestion_type=SuggestionType.HISTORY,
                    score=0.8 if history_entry.success else 0.4,
                    frequency=1,
                    last_used=history_entry.timestamp,
                    result_count=history_entry.result_count,
                    success_rate=1.0 if history_entry.success else 0.0
                )
                suggestions.append(suggestion)
        
        return suggestions

    async def _get_autocomplete_suggestions(self, query: str) -> List[SearchSuggestion]:
        """Get auto-completion suggestions from content."""
        suggestions = []
        
        if not self.local_search or len(query) < 2:
            return suggestions
        
        # Get common terms that start with the query
        query_lower = query.lower()
        matching_terms = [
            term for term, freq in self.term_frequency.most_common(100)
            if term.lower().startswith(query_lower) and term.lower() != query_lower
        ]
        
        for term in matching_terms[:10]:  # Limit to top 10
            suggestion = SearchSuggestion(
                query=term,
                suggestion_type=SuggestionType.AUTO_COMPLETE,
                score=0.6,
                frequency=self.term_frequency[term],
                common_terms={term}
            )
            suggestions.append(suggestion)
        
        return suggestions

    async def _get_similar_suggestions(self, query: str) -> List[SearchSuggestion]:
        """Get suggestions for similar queries."""
        suggestions = []
        
        query_terms = set(self._extract_terms(query))
        
        for pattern, freq in self.query_patterns.items():
            pattern_terms = set(self._extract_terms(pattern))
            
            # Calculate similarity
            if query_terms and pattern_terms:
                similarity = len(query_terms & pattern_terms) / len(query_terms | pattern_terms)
                
                if similarity > 0.3 and pattern.lower() != query.lower():
                    suggestion = SearchSuggestion(
                        query=pattern,
                        suggestion_type=SuggestionType.SIMILAR,
                        score=similarity * 0.7,
                        frequency=freq,
                        common_terms=query_terms & pattern_terms
                    )
                    suggestions.append(suggestion)
        
        return suggestions

    async def _get_popular_suggestions(self, query: str) -> List[SearchSuggestion]:
        """Get popular query suggestions."""
        suggestions = []
        
        # Get popular queries that contain any terms from the input query
        query_terms = set(self._extract_terms(query.lower()))
        
        for pattern, freq in self.query_patterns.most_common(20):
            pattern_terms = set(self._extract_terms(pattern.lower()))
            
            if query_terms & pattern_terms and pattern.lower() != query.lower():
                suggestion = SearchSuggestion(
                    query=pattern,
                    suggestion_type=SuggestionType.POPULAR,
                    score=min(freq / max(self.query_patterns.values()) * 0.6, 0.6),
                    frequency=freq,
                    common_terms=query_terms & pattern_terms
                )
                suggestions.append(suggestion)
        
        return suggestions

    async def _get_contextual_suggestions(self, query: str) -> List[SearchSuggestion]:
        """Get contextual suggestions based on content analysis."""
        suggestions = []
        
        # For now, return basic contextual suggestions
        # This could be enhanced with ML-based content analysis
        
        query_terms = self._extract_terms(query.lower())
        
        # Suggest adding common related terms
        related_terms = {
            "python": ["programming", "code", "tutorial", "example"],
            "javascript": ["web", "frontend", "function", "tutorial"],
            "machine": ["learning", "ai", "algorithm", "data"],
            "data": ["analysis", "science", "visualization", "processing"]
        }
        
        for term in query_terms:
            if term in related_terms:
                for related_term in related_terms[term]:
                    enhanced_query = f"{query} {related_term}"
                    suggestion = SearchSuggestion(
                        query=enhanced_query,
                        suggestion_type=SuggestionType.CONTEXTUAL,
                        score=0.5,
                        common_terms={term, related_term}
                    )
                    suggestions.append(suggestion)
        
        return suggestions

    def _deduplicate_suggestions(self, suggestions: List[SearchSuggestion]) -> List[SearchSuggestion]:
        """Remove duplicate suggestions, keeping the best one."""
        seen_queries = {}
        
        for suggestion in suggestions:
            query_lower = suggestion.query.lower()
            
            if query_lower not in seen_queries or suggestion.score > seen_queries[query_lower].score:
                seen_queries[query_lower] = suggestion
        
        return list(seen_queries.values())

    def _rank_suggestions(self, suggestions: List[SearchSuggestion], query: str) -> List[SearchSuggestion]:
        """Rank suggestions by relevance score."""
        
        def calculate_final_score(suggestion: SearchSuggestion) -> float:
            base_score = suggestion.score
            
            # Boost recent suggestions
            if suggestion.last_used:
                days_old = (datetime.utcnow() - suggestion.last_used).days
                recency_boost = max(0, (30 - days_old) / 30) * 0.2
                base_score += recency_boost
            
            # Boost frequent suggestions
            if suggestion.frequency > 0:
                freq_boost = min(suggestion.frequency / 10, 1.0) * 0.1
                base_score += freq_boost
            
            # Boost high success rate
            success_boost = suggestion.success_rate * 0.1
            base_score += success_boost
            
            return base_score
        
        # Calculate final scores
        for suggestion in suggestions:
            suggestion.score = calculate_final_score(suggestion)
        
        # Sort by score descending
        suggestions.sort(key=lambda x: x.score, reverse=True)
        
        return suggestions

    def _extract_terms(self, text: str) -> List[str]:
        """Extract searchable terms from text."""
        # Simple term extraction - split on whitespace and punctuation
        terms = re.findall(r'\b\w+\b', text.lower())
        # Filter out very short terms
        return [term for term in terms if len(term) >= 2]

    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern matching."""
        return ' '.join(self._extract_terms(query))

    def _invalidate_suggestion_cache(self, query: str) -> None:
        """Invalidate cache entries related to a query."""
        query_terms = set(self._extract_terms(query.lower()))
        
        keys_to_remove = []
        for cache_key in self.suggestion_cache:
            cache_query = cache_key.split(':')[0]
            cache_terms = set(self._extract_terms(cache_query))
            
            # Remove cache entries with overlapping terms
            if query_terms & cache_terms:
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            del self.suggestion_cache[key]

    def _rebuild_frequency_data(self) -> None:
        """Rebuild term frequency and query pattern data from current history."""
        self.term_frequency.clear()
        self.query_patterns.clear()
        
        for history_entry in self.search_history:
            terms = self._extract_terms(history_entry.query)
            self.term_frequency.update(terms)
            
            normalized_query = self._normalize_query(history_entry.query)
            self.query_patterns[normalized_query] += 1

    def _load_history(self) -> None:
        """Load search history from disk."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    for entry_data in data:
                        history_entry = SearchHistory(
                            query=entry_data['query'],
                            timestamp=datetime.fromisoformat(entry_data['timestamp']),
                            result_count=entry_data['result_count'],
                            success=entry_data['success'],
                            execution_time=entry_data.get('execution_time', 0.0),
                            clicked_results=entry_data.get('clicked_results', 0),
                            session_id=entry_data.get('session_id')
                        )
                        self.search_history.append(history_entry)
                
                # Rebuild frequency data
                self._rebuild_frequency_data()
                
                logger.debug(f"Loaded {len(self.search_history)} history entries")
        
        except Exception as e:
            logger.warning(f"Failed to load search history: {e}")

    def _save_history(self) -> None:
        """Save search history to disk."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = []
            for entry in self.search_history:
                entry_data = {
                    'query': entry.query,
                    'timestamp': entry.timestamp.isoformat(),
                    'result_count': entry.result_count,
                    'success': entry.success,
                    'execution_time': entry.execution_time,
                    'clicked_results': entry.clicked_results,
                    'session_id': entry.session_id
                }
                data.append(entry_data)
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save search history: {e}")

    def _load_suggestions_cache(self) -> None:
        """Load suggestions cache from disk."""
        try:
            if self.suggestions_file.exists():
                with open(self.suggestions_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                    for key, suggestions_data in cache_data.items():
                        suggestions = []
                        for suggestion_data in suggestions_data:
                            suggestion = SearchSuggestion(
                                query=suggestion_data['query'],
                                suggestion_type=SuggestionType(suggestion_data['suggestion_type']),
                                score=suggestion_data['score'],
                                frequency=suggestion_data['frequency'],
                                last_used=datetime.fromisoformat(suggestion_data['last_used']) if suggestion_data.get('last_used') else None,
                                result_count=suggestion_data.get('result_count', 0),
                                success_rate=suggestion_data.get('success_rate', 0.0),
                                related_notebooks=set(suggestion_data.get('related_notebooks', [])),
                                related_sections=set(suggestion_data.get('related_sections', [])),
                                common_terms=set(suggestion_data.get('common_terms', []))
                            )
                            suggestions.append(suggestion)
                        self.suggestion_cache[key] = suggestions
                
                logger.debug(f"Loaded {len(self.suggestion_cache)} cache entries")
        
        except Exception as e:
            logger.warning(f"Failed to load suggestions cache: {e}")

    def _save_suggestions_cache(self) -> None:
        """Save suggestions cache to disk."""
        try:
            self.suggestions_file.parent.mkdir(parents=True, exist_ok=True)
            
            cache_data = {}
            for key, suggestions in self.suggestion_cache.items():
                suggestions_data = []
                for suggestion in suggestions:
                    suggestion_data = {
                        'query': suggestion.query,
                        'suggestion_type': suggestion.suggestion_type.value,
                        'score': suggestion.score,
                        'frequency': suggestion.frequency,
                        'last_used': suggestion.last_used.isoformat() if suggestion.last_used else None,
                        'result_count': suggestion.result_count,
                        'success_rate': suggestion.success_rate,
                        'related_notebooks': list(suggestion.related_notebooks),
                        'related_sections': list(suggestion.related_sections),
                        'common_terms': list(suggestion.common_terms)
                    }
                    suggestions_data.append(suggestion_data)
                cache_data[key] = suggestions_data
            
            with open(self.suggestions_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save suggestions cache: {e}")
