"""
Semantic ranking system for OneNote cache search results.

Provides advanced relevance scoring with content analysis, query matching,
and machine learning-based ranking for improved search result quality.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import math

from ..models.cache import CachedPage
from .filter_manager import ContentType

logger = logging.getLogger(__name__)


class RankingFactor(Enum):
    """Different factors that contribute to relevance ranking."""
    QUERY_MATCH = "query_match"
    TITLE_MATCH = "title_match" 
    CONTENT_MATCH = "content_match"
    FRESHNESS = "freshness"
    LENGTH = "length"
    STRUCTURE = "structure"
    POPULARITY = "popularity"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    KEYWORD_DENSITY = "keyword_density"
    POSITION_BONUS = "position_bonus"


@dataclass
class RankingWeights:
    """Weights for different ranking factors."""
    
    query_match: float = 0.25
    title_match: float = 0.20
    content_match: float = 0.15
    freshness: float = 0.10
    length: float = 0.08
    structure: float = 0.07
    popularity: float = 0.05
    semantic_similarity: float = 0.05
    keyword_density: float = 0.03
    position_bonus: float = 0.02
    
    def normalize(self) -> 'RankingWeights':
        """Normalize weights to sum to 1.0."""
        total = sum(vars(self).values())
        if total == 0:
            return self
        
        factor = 1.0 / total
        return RankingWeights(
            query_match=self.query_match * factor,
            title_match=self.title_match * factor,
            content_match=self.content_match * factor,
            freshness=self.freshness * factor,
            length=self.length * factor,
            structure=self.structure * factor,
            popularity=self.popularity * factor,
            semantic_similarity=self.semantic_similarity * factor,
            keyword_density=self.keyword_density * factor,
            position_bonus=self.position_bonus * factor
        )


@dataclass
class RankingScore:
    """Detailed ranking score breakdown."""
    
    total_score: float
    page_id: str
    page_title: str
    
    # Individual factor scores
    query_match_score: float = 0.0
    title_match_score: float = 0.0
    content_match_score: float = 0.0
    freshness_score: float = 0.0
    length_score: float = 0.0
    structure_score: float = 0.0
    popularity_score: float = 0.0
    semantic_similarity_score: float = 0.0
    keyword_density_score: float = 0.0
    position_bonus_score: float = 0.0
    
    # Metadata
    matches_found: int = 0
    query_terms_matched: int = 0
    total_query_terms: int = 0
    
    def get_score_breakdown(self) -> Dict[str, float]:
        """Get detailed score breakdown."""
        return {
            "total": self.total_score,
            "query_match": self.query_match_score,
            "title_match": self.title_match_score,
            "content_match": self.content_match_score,
            "freshness": self.freshness_score,
            "length": self.length_score,
            "structure": self.structure_score,
            "popularity": self.popularity_score,
            "semantic_similarity": self.semantic_similarity_score,
            "keyword_density": self.keyword_density_score,
            "position_bonus": self.position_bonus_score
        }


@dataclass
class QueryAnalysis:
    """Analysis of a search query."""
    
    original_query: str
    normalized_query: str
    terms: List[str]
    important_terms: List[str]  # Terms that should have higher weight
    phrases: List[str]
    quoted_phrases: List[str]
    operators: Dict[str, Any]  # Boolean operators, negations, etc.
    intent: str  # question, command, search, etc.
    
    @classmethod
    def analyze(cls, query: str) -> 'QueryAnalysis':
        """Analyze a search query."""
        try:
            # Store original
            original_query = query.strip()
            
            # Extract quoted phrases first
            quoted_phrases = []
            quote_pattern = r'"([^"]*)"'
            quotes = re.findall(quote_pattern, query)
            quoted_phrases.extend(quotes)
            
            # Remove quoted phrases for term extraction
            normalized_query = re.sub(quote_pattern, '', query)
            
            # Basic normalization
            normalized_query = normalized_query.lower().strip()
            normalized_query = re.sub(r'[^\w\s-]', ' ', normalized_query)
            normalized_query = re.sub(r'\s+', ' ', normalized_query)
            
            # Extract terms
            terms = [term.strip() for term in normalized_query.split() if len(term.strip()) > 1]
            
            # Identify important terms (longer terms, capitalized in original, etc.)
            important_terms = []
            for term in terms:
                if len(term) > 5:  # Longer terms are often more specific
                    important_terms.append(term)
                elif term.upper() in original_query:  # Originally capitalized
                    important_terms.append(term)
            
            # Extract phrases (2-3 word combinations)
            phrases = []
            for i in range(len(terms) - 1):
                phrase = ' '.join(terms[i:i+2])
                phrases.append(phrase)
                if i < len(terms) - 2:
                    phrase3 = ' '.join(terms[i:i+3])
                    phrases.append(phrase3)
            
            # Detect operators and intent
            operators = {}
            intent = "search"
            
            # Check for question words
            question_words = ['what', 'how', 'why', 'when', 'where', 'who', 'which']
            if any(word in terms for word in question_words):
                intent = "question"
            
            # Check for command words
            command_words = ['show', 'find', 'get', 'list', 'search']
            if any(word in terms for word in command_words):
                intent = "command"
            
            return cls(
                original_query=original_query,
                normalized_query=normalized_query,
                terms=terms,
                important_terms=important_terms,
                phrases=phrases,
                quoted_phrases=quoted_phrases,
                operators=operators,
                intent=intent
            )
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return cls(
                original_query=query,
                normalized_query=query.lower(),
                terms=query.lower().split(),
                important_terms=[],
                phrases=[],
                quoted_phrases=[],
                operators={},
                intent="search"
            )


class SemanticRanking:
    """
    Advanced semantic ranking system for search results.
    
    Provides sophisticated relevance scoring using multiple ranking factors
    including query matching, content analysis, freshness, and structure.
    """

    def __init__(self, 
                 weights: Optional[RankingWeights] = None,
                 enable_caching: bool = True):
        """
        Initialize semantic ranking system.

        Args:
            weights: Custom ranking weights (uses defaults if None)
            enable_caching: Whether to cache ranking computations
        """
        self.weights = weights or RankingWeights().normalize()
        self.enable_caching = enable_caching
        
        # Caching
        self.score_cache: Dict[str, RankingScore] = {}
        self.analysis_cache: Dict[str, QueryAnalysis] = {}
        
        # Statistics
        self.ranking_stats = {
            "queries_processed": 0,
            "pages_ranked": 0,
            "cache_hits": 0,
            "avg_ranking_time": 0.0
        }
        
        logger.info("Initialized semantic ranking system")

    async def rank_results(self, 
                          pages: List[CachedPage], 
                          query: str,
                          max_results: Optional[int] = None) -> List[Tuple[CachedPage, RankingScore]]:
        """
        Rank search results by relevance.

        Args:
            pages: List of pages to rank
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of (page, score) tuples sorted by relevance
        """
        try:
            start_time = datetime.utcnow()
            logger.debug(f"Ranking {len(pages)} pages for query: '{query}'")
            
            # Analyze query
            query_analysis = await self._analyze_query(query)
            
            # Score all pages
            scored_pages = []
            for page in pages:
                score = await self._calculate_page_score(page, query_analysis)
                scored_pages.append((page, score))
            
            # Sort by score (highest first)
            scored_pages.sort(key=lambda x: x[1].total_score, reverse=True)
            
            # Apply max results limit
            if max_results:
                scored_pages = scored_pages[:max_results]
            
            # Update statistics
            ranking_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_stats(len(pages), ranking_time)
            
            logger.info(f"Ranked {len(scored_pages)} results in {ranking_time:.3f}s")
            return scored_pages
            
        except Exception as e:
            logger.error(f"Result ranking failed: {e}")
            # Return pages with default scores
            return [(page, RankingScore(total_score=0.5, page_id=page.id, page_title=page.title)) 
                   for page in pages]

    async def _analyze_query(self, query: str) -> QueryAnalysis:
        """Analyze search query with caching."""
        if self.enable_caching and query in self.analysis_cache:
            self.ranking_stats["cache_hits"] += 1
            return self.analysis_cache[query]
        
        analysis = QueryAnalysis.analyze(query)
        
        if self.enable_caching:
            self.analysis_cache[query] = analysis
        
        return analysis

    async def _calculate_page_score(self, 
                                  page: CachedPage, 
                                  query_analysis: QueryAnalysis) -> RankingScore:
        """Calculate comprehensive relevance score for a page."""
        try:
            # Create score object
            score = RankingScore(
                total_score=0.0,
                page_id=page.id,
                page_title=page.title
            )
            
            # Calculate individual factor scores
            score.query_match_score = await self._score_query_match(page, query_analysis)
            score.title_match_score = await self._score_title_match(page, query_analysis)
            score.content_match_score = await self._score_content_match(page, query_analysis)
            score.freshness_score = await self._score_freshness(page)
            score.length_score = await self._score_length(page)
            score.structure_score = await self._score_structure(page)
            score.popularity_score = await self._score_popularity(page)
            score.semantic_similarity_score = await self._score_semantic_similarity(page, query_analysis)
            score.keyword_density_score = await self._score_keyword_density(page, query_analysis)
            score.position_bonus_score = await self._score_position_bonus(page, query_analysis)
            
            # Calculate weighted total score
            score.total_score = (
                score.query_match_score * self.weights.query_match +
                score.title_match_score * self.weights.title_match +
                score.content_match_score * self.weights.content_match +
                score.freshness_score * self.weights.freshness +
                score.length_score * self.weights.length +
                score.structure_score * self.weights.structure +
                score.popularity_score * self.weights.popularity +
                score.semantic_similarity_score * self.weights.semantic_similarity +
                score.keyword_density_score * self.weights.keyword_density +
                score.position_bonus_score * self.weights.position_bonus
            )
            
            # Calculate metadata
            score.total_query_terms = len(query_analysis.terms)
            
            return score
            
        except Exception as e:
            logger.error(f"Score calculation failed for page {page.id}: {e}")
            return RankingScore(total_score=0.0, page_id=page.id, page_title=page.title)

    async def _score_query_match(self, page: CachedPage, query_analysis: QueryAnalysis) -> float:
        """Score overall query matching."""
        try:
            if not query_analysis.terms:
                return 0.0
            
            content = (page.title + " " + (page.content or "")).lower()
            matches = 0
            total_terms = len(query_analysis.terms)
            
            for term in query_analysis.terms:
                if term in content:
                    matches += 1
                    # Bonus for important terms
                    if term in query_analysis.important_terms:
                        matches += 0.5
            
            # Bonus for exact phrase matches
            for phrase in query_analysis.quoted_phrases:
                if phrase.lower() in content:
                    matches += len(phrase.split()) * 0.5
            
            # Bonus for multi-word phrases
            for phrase in query_analysis.phrases:
                if phrase in content:
                    matches += 0.3
            
            return min(matches / total_terms, 1.0) if total_terms > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Query match scoring failed: {e}")
            return 0.0

    async def _score_title_match(self, page: CachedPage, query_analysis: QueryAnalysis) -> float:
        """Score title matching with higher weight."""
        try:
            if not query_analysis.terms or not page.title:
                return 0.0
            
            title = page.title.lower()
            matches = 0
            total_terms = len(query_analysis.terms)
            
            for term in query_analysis.terms:
                if term in title:
                    # Higher score for title matches
                    matches += 2.0
                    # Extra bonus for exact word boundaries
                    if re.search(r'\b' + re.escape(term) + r'\b', title):
                        matches += 1.0
            
            # Major bonus for exact title match
            if query_analysis.normalized_query == title:
                matches += 5.0
            
            return min(matches / (total_terms * 2), 1.0) if total_terms > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Title match scoring failed: {e}")
            return 0.0

    async def _score_content_match(self, page: CachedPage, query_analysis: QueryAnalysis) -> float:
        """Score content matching quality."""
        try:
            if not query_analysis.terms or not page.content:
                return 0.0
            
            content = page.content.lower()
            matches = 0
            total_terms = len(query_analysis.terms)
            
            for term in query_analysis.terms:
                term_matches = content.count(term)
                if term_matches > 0:
                    # Logarithmic scoring to prevent spam
                    matches += math.log(term_matches + 1) * 0.5
            
            # Normalize by content length to prevent long documents from dominating
            content_length = len(content)
            if content_length > 0:
                matches = matches * min(1000.0 / content_length, 1.0)
            
            return min(matches / total_terms, 1.0) if total_terms > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Content match scoring failed: {e}")
            return 0.0

    async def _score_freshness(self, page: CachedPage) -> float:
        """Score based on page freshness."""
        try:
            now = datetime.utcnow()
            modified_date = page.last_modified
            
            if not modified_date:
                return 0.3  # Default score for unknown dates
            
            # Calculate days since modification
            days_old = (now - modified_date).days
            
            # Scoring curve: recent = 1.0, 1 year = 0.1
            if days_old <= 7:
                return 1.0
            elif days_old <= 30:
                return 0.8
            elif days_old <= 90:
                return 0.6
            elif days_old <= 365:
                return 0.4
            else:
                return 0.1
                
        except Exception as e:
            logger.error(f"Freshness scoring failed: {e}")
            return 0.3

    async def _score_length(self, page: CachedPage) -> float:
        """Score based on content length (optimal length gets highest score)."""
        try:
            content_length = len(page.content or "")
            
            if content_length == 0:
                return 0.1
            
            # Optimal range: 200-2000 characters
            if 200 <= content_length <= 2000:
                return 1.0
            elif content_length < 200:
                return content_length / 200.0
            else:
                # Diminishing returns for very long content
                return 1.0 / (1.0 + math.log(content_length / 2000.0))
                
        except Exception as e:
            logger.error(f"Length scoring failed: {e}")
            return 0.5

    async def _score_structure(self, page: CachedPage) -> float:
        """Score based on content structure quality."""
        try:
            content = page.content or ""
            score = 0.0
            
            # Bonus for structured content
            if '<h1' in content or '<h2' in content or '<h3' in content:
                score += 0.3  # Has headers
            
            if '<ul' in content or '<ol' in content:
                score += 0.2  # Has lists
            
            if '<table' in content:
                score += 0.2  # Has tables
            
            if '<p' in content:
                score += 0.1  # Has paragraphs
            
            # Bonus for good title
            if page.title and len(page.title.strip()) > 0:
                score += 0.2
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Structure scoring failed: {e}")
            return 0.5

    async def _score_popularity(self, page: CachedPage) -> float:
        """Score based on page popularity indicators."""
        try:
            # This is a placeholder - in a real system, you'd track:
            # - View count
            # - Edit frequency
            # - Link references
            # - User bookmarks
            
            # For now, use simple heuristics
            score = 0.5  # Default
            
            # Bonus for pages with substantial content
            if len(page.content or "") > 500:
                score += 0.2
            
            # Bonus for pages that seem well-structured
            if page.title and len(page.title) > 10:
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Popularity scoring failed: {e}")
            return 0.5

    async def _score_semantic_similarity(self, page: CachedPage, query_analysis: QueryAnalysis) -> float:
        """Score semantic similarity between query and content."""
        try:
            # This is a simplified semantic similarity
            # In production, you'd use embeddings or NLP models
            
            content = (page.title + " " + (page.content or "")).lower()
            query_text = query_analysis.normalized_query
            
            # Simple word overlap similarity
            content_words = set(re.findall(r'\w+', content))
            query_words = set(query_analysis.terms)
            
            if not query_words:
                return 0.0
            
            intersection = len(content_words.intersection(query_words))
            union = len(content_words.union(query_words))
            
            if union == 0:
                return 0.0
            
            jaccard_similarity = intersection / union
            return jaccard_similarity
            
        except Exception as e:
            logger.error(f"Semantic similarity scoring failed: {e}")
            return 0.0

    async def _score_keyword_density(self, page: CachedPage, query_analysis: QueryAnalysis) -> float:
        """Score based on keyword density."""
        try:
            if not query_analysis.terms or not page.content:
                return 0.0
            
            content = page.content.lower()
            content_words = len(re.findall(r'\w+', content))
            
            if content_words == 0:
                return 0.0
            
            keyword_count = 0
            for term in query_analysis.terms:
                keyword_count += content.count(term)
            
            # Optimal density is around 2-5%
            density = keyword_count / content_words
            optimal_density = 0.03
            
            if density <= optimal_density:
                return density / optimal_density
            else:
                # Penalty for keyword stuffing
                return max(0.0, optimal_density / density)
                
        except Exception as e:
            logger.error(f"Keyword density scoring failed: {e}")
            return 0.0

    async def _score_position_bonus(self, page: CachedPage, query_analysis: QueryAnalysis) -> float:
        """Score based on keyword position in content."""
        try:
            if not query_analysis.terms or not page.content:
                return 0.0
            
            content = page.content.lower()
            content_length = len(content)
            
            if content_length == 0:
                return 0.0
            
            position_scores = []
            
            for term in query_analysis.terms:
                first_pos = content.find(term)
                if first_pos != -1:
                    # Earlier positions get higher scores
                    position_ratio = 1.0 - (first_pos / content_length)
                    position_scores.append(position_ratio)
            
            if not position_scores:
                return 0.0
            
            return sum(position_scores) / len(position_scores)
            
        except Exception as e:
            logger.error(f"Position bonus scoring failed: {e}")
            return 0.0

    def _update_stats(self, pages_count: int, ranking_time: float) -> None:
        """Update ranking statistics."""
        self.ranking_stats["queries_processed"] += 1
        self.ranking_stats["pages_ranked"] += pages_count
        
        # Update rolling average ranking time
        current_avg = self.ranking_stats["avg_ranking_time"]
        queries_processed = self.ranking_stats["queries_processed"]
        
        self.ranking_stats["avg_ranking_time"] = (
            (current_avg * (queries_processed - 1) + ranking_time) / queries_processed
        )

    def get_ranking_stats(self) -> Dict[str, Any]:
        """Get ranking system statistics."""
        return dict(self.ranking_stats)

    def clear_cache(self) -> None:
        """Clear ranking caches."""
        self.score_cache.clear()
        self.analysis_cache.clear()
        logger.debug("Ranking caches cleared")

    def set_weights(self, weights: RankingWeights) -> None:
        """Update ranking weights."""
        self.weights = weights.normalize()
        # Clear cache since weights changed
        if self.enable_caching:
            self.clear_cache()
        logger.info("Ranking weights updated")

    async def explain_ranking(self, 
                            page: CachedPage, 
                            query: str) -> Dict[str, Any]:
        """
        Provide detailed explanation of how a page was ranked.

        Args:
            page: Page to explain
            query: Original query

        Returns:
            Detailed ranking explanation
        """
        try:
            query_analysis = await self._analyze_query(query)
            score = await self._calculate_page_score(page, query_analysis)
            
            explanation = {
                "page_id": page.id,
                "page_title": page.title,
                "query": query,
                "total_score": score.total_score,
                "score_breakdown": score.get_score_breakdown(),
                "weights_used": {
                    "query_match": self.weights.query_match,
                    "title_match": self.weights.title_match,
                    "content_match": self.weights.content_match,
                    "freshness": self.weights.freshness,
                    "length": self.weights.length,
                    "structure": self.weights.structure,
                    "popularity": self.weights.popularity,
                    "semantic_similarity": self.weights.semantic_similarity,
                    "keyword_density": self.weights.keyword_density,
                    "position_bonus": self.weights.position_bonus
                },
                "query_analysis": {
                    "terms": query_analysis.terms,
                    "important_terms": query_analysis.important_terms,
                    "phrases": query_analysis.phrases,
                    "intent": query_analysis.intent
                },
                "ranking_factors": {
                    "content_length": len(page.content or ""),
                    "title_length": len(page.title or ""),
                    "last_modified": page.last_modified.isoformat() if page.last_modified else None,
                    "days_old": (datetime.utcnow() - page.last_modified).days if page.last_modified else None
                }
            }
            
            return explanation
            
        except Exception as e:
            logger.error(f"Ranking explanation failed: {e}")
            return {"error": str(e)}

    def create_custom_weights(self, 
                            emphasis: str = "balanced") -> RankingWeights:
        """
        Create custom ranking weights for different use cases.

        Args:
            emphasis: Type of emphasis ("balanced", "freshness", "exactness", "popularity")

        Returns:
            Custom RankingWeights
        """
        if emphasis == "freshness":
            return RankingWeights(
                query_match=0.20,
                title_match=0.15,
                content_match=0.10,
                freshness=0.30,  # Higher weight on freshness
                length=0.05,
                structure=0.05,
                popularity=0.10,
                semantic_similarity=0.03,
                keyword_density=0.01,
                position_bonus=0.01
            ).normalize()
        
        elif emphasis == "exactness":
            return RankingWeights(
                query_match=0.35,  # Higher weight on exact matches
                title_match=0.30,
                content_match=0.20,
                freshness=0.05,
                length=0.03,
                structure=0.02,
                popularity=0.02,
                semantic_similarity=0.02,
                keyword_density=0.01,
                position_bonus=0.00
            ).normalize()
        
        elif emphasis == "popularity":
            return RankingWeights(
                query_match=0.15,
                title_match=0.10,
                content_match=0.10,
                freshness=0.05,
                length=0.10,
                structure=0.15,
                popularity=0.25,  # Higher weight on popularity
                semantic_similarity=0.05,
                keyword_density=0.03,
                position_bonus=0.02
            ).normalize()
        
        else:  # balanced
            return RankingWeights().normalize()
