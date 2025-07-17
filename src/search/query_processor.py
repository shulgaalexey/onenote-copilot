"""
Query processing service for semantic search.

Provides intelligent query analysis, intent detection, and query enhancement
for optimal semantic search performance.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from ..config.logging import logged
from ..config.settings import get_settings
from ..models.onenote import QueryIntent

logger = logging.getLogger(__name__)


class QueryProcessor:
    """
    Intelligent query processing for semantic search.

    Analyzes user queries to detect intent, extract keywords, and optimize
    queries for better semantic search results.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize the query processor.

        Args:
            settings: Optional settings instance
        """
        self.settings = settings or get_settings()

        # Common stop words for OneNote content
        self.stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'i', 'you', 'my', 'me', 'we', 'us'
        }

        # Intent detection patterns
        self.intent_patterns = {
            'question': [
                r'\bwhat\b', r'\bhow\b', r'\bwhy\b', r'\bwhen\b', r'\bwhere\b',
                r'\bwhich\b', r'\bwho\b', r'\?\s*$', r'\bdid\s+i\b', r'\bdo\s+i\b'
            ],
            'content_request': [
                r'\bshow\s+me\b', r'\bfind\b', r'\bget\b', r'\bdisplay\b',
                r'\blist\b', r'\bsearch\s+for\b', r'\blook\s+for\b'
            ],
            'temporal': [
                r'\blast\s+\w+\b', r'\brecent\b', r'\byesterday\b', r'\btoday\b',
                r'\bthis\s+week\b', r'\bthis\s+month\b', r'\byear\b', r'\bago\b'
            ],
            'conceptual': [
                r'\bthoughts?\s+about\b', r'\bideas?\s+about\b', r'\bthink\s+about\b',
                r'\bopinion\s+on\b', r'\bfeels?\s+about\b', r'\bviews?\s+on\b'
            ]
        }

        # Common OneNote terms and patterns
        self.onenote_terms = {
            'notebook', 'section', 'page', 'note', 'notes', 'meeting', 'project',
            'task', 'todo', 'idea', 'research', 'brainstorm', 'plan', 'draft'
        }

    @logged("Process user query")
    async def process_query(self, query: str) -> QueryIntent:
        """
        Process and analyze a user query for semantic search.

        Args:
            query: Raw user query

        Returns:
            Processed query with intent analysis

        Raises:
            ValueError: If query is empty or invalid
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        original_query = query

        # Clean and normalize the query
        processed_query = self._clean_query(query)

        # Detect intent
        intent_type, confidence = self._detect_intent(processed_query)

        # Extract keywords
        keywords = self._extract_keywords(processed_query)

        # Extract temporal filters
        temporal_filters = self._extract_temporal_filters(processed_query)

        # Extract content filters
        content_filters = self._extract_content_filters(processed_query)

        # Generate alternative suggestions
        suggested_alternatives = self._generate_alternatives(processed_query, intent_type)

        return QueryIntent(
            original_query=original_query,
            processed_query=processed_query,
            intent_type=intent_type,
            confidence=confidence,
            keywords=keywords,
            temporal_filters=temporal_filters,
            content_filters=content_filters,
            suggested_alternatives=suggested_alternatives
        )

    def _clean_query(self, query: str) -> str:
        """
        Clean and normalize the query text.

        Args:
            query: Raw query text

        Returns:
            Cleaned query text
        """
        # Convert to lowercase
        cleaned = query.lower()

        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Handle common contractions
        contractions = {
            "don't": "do not",
            "doesn't": "does not",
            "didn't": "did not",
            "won't": "will not",
            "can't": "cannot",
            "i'm": "i am",
            "you're": "you are",
            "we're": "we are",
            "they're": "they are",
            "it's": "it is",
            "that's": "that is"
        }

        for contraction, expansion in contractions.items():
            cleaned = cleaned.replace(contraction, expansion)

        # Remove common filler words at the beginning
        cleaned = re.sub(r'^(can you |could you |please |help me )', '', cleaned)

        return cleaned.strip()

    def _detect_intent(self, query: str) -> tuple[str, float]:
        """
        Detect the intent of the query.

        Args:
            query: Processed query text

        Returns:
            Tuple of (intent_type, confidence_score)
        """
        intent_scores = {}

        for intent_type, patterns in self.intent_patterns.items():
            score = 0.0
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    score += 1.0

            if score > 0:
                # Normalize score by number of patterns
                intent_scores[intent_type] = score / len(patterns)

        if not intent_scores:
            return "search", 0.5  # Default to search intent

        # Get the highest scoring intent
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        return best_intent[0], min(best_intent[1], 1.0)

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract meaningful keywords from the query.

        Args:
            query: Processed query text

        Returns:
            List of extracted keywords
        """
        # Split into words and filter
        words = re.findall(r'\b\w+\b', query.lower())

        # Remove stop words and short words
        keywords = [
            word for word in words
            if len(word) > 2 and word not in self.stop_words
        ]

        # Add multi-word phrases that might be important
        phrases = self._extract_phrases(query)
        keywords.extend(phrases)

        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for keyword in keywords:
            if keyword not in seen:
                seen.add(keyword)
                unique_keywords.append(keyword)

        return unique_keywords[:10]  # Limit to top 10 keywords

    def _extract_phrases(self, query: str) -> List[str]:
        """
        Extract meaningful phrases from the query.

        Args:
            query: Query text

        Returns:
            List of extracted phrases
        """
        phrases = []

        # Common OneNote phrase patterns
        phrase_patterns = [
            r'\b\w+\s+coding\b',  # "vibe coding", "pair coding", etc.
            r'\b\w+\s+development\b',
            r'\b\w+\s+project\b',
            r'\b\w+\s+meeting\b',
            r'\b\w+\s+research\b',
            r'\bproject\s+\w+\b',
            r'\bmeeting\s+\w+\b',
            r'\bidea\s+about\s+\w+\b'
        ]

        for pattern in phrase_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            phrases.extend([match.lower() for match in matches])

        return phrases

    def _extract_temporal_filters(self, query: str) -> Dict[str, Any]:
        """
        Extract temporal/date filters from the query.

        Args:
            query: Query text

        Returns:
            Dictionary with temporal filters
        """
        temporal_filters = {}

        # Temporal patterns
        patterns = {
            'last_week': r'\blast\s+week\b',
            'last_month': r'\blast\s+month\b',
            'yesterday': r'\byesterday\b',
            'today': r'\btoday\b',
            'this_week': r'\bthis\s+week\b',
            'this_month': r'\bthis\s+month\b',
            'recent': r'\brecent\b|\blately\b',
            'old': r'\bold\b|\bearlier\b|\bbefore\b'
        }

        for filter_name, pattern in patterns.items():
            if re.search(pattern, query, re.IGNORECASE):
                temporal_filters[filter_name] = True

        return temporal_filters

    def _extract_content_filters(self, query: str) -> Dict[str, Any]:
        """
        Extract content type filters from the query.

        Args:
            query: Query text

        Returns:
            Dictionary with content filters
        """
        content_filters = {}

        # Content type patterns
        patterns = {
            'meeting_notes': r'\bmeeting\b|\bmtg\b',
            'project_info': r'\bproject\b|\bproj\b',
            'ideas': r'\bidea\b|\bbrainstorm\b|\bconcept\b',
            'research': r'\bresearch\b|\bstudy\b|\binvestigat\b',
            'tasks': r'\btask\b|\btodo\b|\baction\s+item\b',
            'code_related': r'\bcode\b|\bcoding\b|\bprogramm\b|\bdevelop\b'
        }

        for filter_name, pattern in patterns.items():
            if re.search(pattern, query, re.IGNORECASE):
                content_filters[filter_name] = True

        return content_filters

    def _generate_alternatives(self, query: str, intent_type: str) -> List[str]:
        """
        Generate alternative query suggestions.

        Args:
            query: Processed query
            intent_type: Detected intent type

        Returns:
            List of alternative query suggestions
        """
        alternatives = []

        # Extract main concepts from query
        keywords = self._extract_keywords(query)
        if not keywords:
            return alternatives

        main_concept = keywords[0] if keywords else "content"

        # Generate alternatives based on intent
        if intent_type == "question":
            alternatives.extend([
                f"notes about {main_concept}",
                f"information on {main_concept}",
                f"details about {main_concept}"
            ])
        elif intent_type == "conceptual":
            alternatives.extend([
                f"thoughts on {main_concept}",
                f"ideas about {main_concept}",
                f"opinions on {main_concept}"
            ])
        elif intent_type == "content_request":
            alternatives.extend([
                f"find {main_concept}",
                f"search {main_concept}",
                f"show {main_concept} notes"
            ])
        else:
            # General alternatives
            if len(keywords) > 1:
                alternatives.append(" ".join(keywords[:2]))
            alternatives.extend([
                f"{main_concept} notes",
                f"{main_concept} information"
            ])

        # Remove duplicates and limit
        return list(set(alternatives))[:3]

    @logged("Expand query with synonyms")
    async def expand_query(self, query: str) -> List[str]:
        """
        Expand query with synonyms and related terms.

        Args:
            query: Original query

        Returns:
            List of expanded query variations
        """
        # Process the original query
        processed = await self.process_query(query)

        expanded_queries = [processed.processed_query]

        # Add variations with different phrasings
        keywords = processed.keywords
        if keywords:
            # Create variations
            variations = [
                " ".join(keywords),  # Just keywords
                f"notes about {' '.join(keywords[:2])}",  # Notes about main concepts
                f"information on {keywords[0]}" if keywords else query,  # Information on main concept
            ]

            expanded_queries.extend(variations)

        # Remove duplicates
        return list(set(expanded_queries))

    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get query processing statistics.

        Returns:
            Dictionary with processing metrics
        """
        return {
            "stop_words_count": len(self.stop_words),
            "intent_patterns": {k: len(v) for k, v in self.intent_patterns.items()},
            "onenote_terms_count": len(self.onenote_terms)
        }
