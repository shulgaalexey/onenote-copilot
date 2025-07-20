"""
Search filter manager for OneNote cache system.

Provides advanced filtering capabilities for search operations including
date ranges, notebooks, sections, content types, and custom filters.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..models.cache import CachedPage
from ..models.onenote import OneNoteNotebook, OneNoteSection
from .local_search import LocalOneNoteSearch

logger = logging.getLogger(__name__)


class FilterOperator(Enum):
    """Filter operation types."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    IN = "in"
    NOT_IN = "not_in"
    REGEX = "regex"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class ContentType(Enum):
    """Content type categories for filtering."""
    TEXT = "text"
    IMAGES = "images"
    TABLES = "tables"
    LISTS = "lists"
    CODE_BLOCKS = "code_blocks"
    LINKS = "links"
    ATTACHMENTS = "attachments"
    DRAWINGS = "drawings"
    EQUATIONS = "equations"
    TAGS = "tags"


@dataclass
class FilterCondition:
    """Represents a single filter condition."""
    
    field: str
    operator: FilterOperator
    value: Any
    case_sensitive: bool = False
    
    def __post_init__(self):
        """Validate filter condition."""
        if self.operator in [FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL]:
            self.value = None
        elif self.operator in [FilterOperator.IN, FilterOperator.NOT_IN]:
            if not isinstance(self.value, (list, tuple, set)):
                raise ValueError(f"Value for {self.operator.value} must be a collection")


@dataclass
class DateRangeFilter:
    """Date range filter with relative and absolute support."""
    
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Relative date options
    days_back: Optional[int] = None
    weeks_back: Optional[int] = None
    months_back: Optional[int] = None
    years_back: Optional[int] = None
    
    # Named ranges
    today: bool = False
    yesterday: bool = False
    this_week: bool = False
    last_week: bool = False
    this_month: bool = False
    last_month: bool = False
    this_year: bool = False
    last_year: bool = False
    
    def get_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Calculate actual date range from filter settings."""
        now = datetime.utcnow()
        start, end = self.start_date, self.end_date
        
        # Handle relative dates
        if self.days_back:
            start = now - timedelta(days=self.days_back)
        elif self.weeks_back:
            start = now - timedelta(weeks=self.weeks_back)
        elif self.months_back:
            start = now - timedelta(days=self.months_back * 30)  # Approximate
        elif self.years_back:
            start = now - timedelta(days=self.years_back * 365)  # Approximate
            
        # Handle named ranges
        if self.today:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif self.yesterday:
            end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - timedelta(days=1)
        elif self.this_week:
            days_since_monday = now.weekday()
            start = now - timedelta(days=days_since_monday)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.last_week:
            days_since_monday = now.weekday()
            end = now - timedelta(days=days_since_monday)
            end = end.replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - timedelta(days=7)
        elif self.this_month:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif self.last_month:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start = start.replace(month=start.month - 1 if start.month > 1 else 12)
            if start.month == 12:
                start = start.replace(year=start.year - 1)
            end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif self.this_year:
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif self.last_year:
            start = now.replace(year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            
        return start, end


@dataclass
class SearchFilter:
    """Complete search filter configuration."""
    
    # Text filters
    conditions: List[FilterCondition] = field(default_factory=list)
    
    # Date filters
    created_date: Optional[DateRangeFilter] = None
    modified_date: Optional[DateRangeFilter] = None
    
    # Location filters
    notebook_ids: Optional[List[str]] = None
    notebook_names: Optional[List[str]] = None
    section_ids: Optional[List[str]] = None
    section_names: Optional[List[str]] = None
    
    # Content type filters
    content_types: Optional[List[ContentType]] = None
    exclude_content_types: Optional[List[ContentType]] = None
    
    # Size filters
    min_content_length: Optional[int] = None
    max_content_length: Optional[int] = None
    
    # Quality filters
    has_images: Optional[bool] = None
    has_tables: Optional[bool] = None
    has_links: Optional[bool] = None
    has_attachments: Optional[bool] = None
    
    # Custom filters
    custom_filters: Dict[str, Callable[[CachedPage], bool]] = field(default_factory=dict)
    
    # Combination logic
    combine_conditions_with_and: bool = True  # True for AND, False for OR


class SearchFilterManager:
    """
    Manager for advanced search filtering capabilities.
    
    Provides comprehensive filtering for OneNote cache search operations
    with support for date ranges, content types, locations, and custom filters.
    """

    def __init__(self, local_search: Optional[LocalOneNoteSearch] = None):
        """
        Initialize search filter manager.

        Args:
            local_search: Local OneNote search instance
        """
        self.local_search = local_search
        self.registered_filters: Dict[str, Callable] = {}
        self.filter_cache: Dict[str, Any] = {}
        
        # Register built-in content analyzers
        self._register_content_analyzers()
        
        logger.info("Initialized search filter manager")

    def _register_content_analyzers(self) -> None:
        """Register built-in content analysis functions."""
        self.registered_filters.update({
            "has_images": self._analyze_images,
            "has_tables": self._analyze_tables,
            "has_links": self._analyze_links,
            "has_code_blocks": self._analyze_code_blocks,
            "has_lists": self._analyze_lists,
            "has_attachments": self._analyze_attachments,
            "content_type": self._analyze_content_type
        })

    async def apply_filter(self, 
                          pages: List[CachedPage], 
                          search_filter: SearchFilter) -> List[CachedPage]:
        """
        Apply comprehensive filter to list of pages.

        Args:
            pages: List of cached pages to filter
            search_filter: Filter configuration to apply

        Returns:
            Filtered list of pages
        """
        try:
            logger.debug(f"Applying filters to {len(pages)} pages")
            
            filtered_pages = []
            for page in pages:
                if await self._evaluate_page(page, search_filter):
                    filtered_pages.append(page)
            
            logger.info(f"Filter applied: {len(pages)} -> {len(filtered_pages)} pages")
            return filtered_pages
            
        except Exception as e:
            logger.error(f"Filter application failed: {e}")
            return pages  # Return unfiltered on error

    async def _evaluate_page(self, 
                            page: CachedPage, 
                            search_filter: SearchFilter) -> bool:
        """Evaluate if a page matches the filter criteria."""
        try:
            # Check date filters
            if not await self._check_date_filters(page, search_filter):
                return False
            
            # Check location filters
            if not await self._check_location_filters(page, search_filter):
                return False
            
            # Check content type filters
            if not await self._check_content_type_filters(page, search_filter):
                return False
            
            # Check size filters
            if not await self._check_size_filters(page, search_filter):
                return False
            
            # Check quality filters
            if not await self._check_quality_filters(page, search_filter):
                return False
            
            # Check custom conditions
            if not await self._check_conditions(page, search_filter):
                return False
            
            # Check custom filters
            if not await self._check_custom_filters(page, search_filter):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Page evaluation failed for {page.page_id}: {e}")
            return False

    async def _check_date_filters(self, 
                                page: CachedPage, 
                                search_filter: SearchFilter) -> bool:
        """Check date range filters."""
        try:
            # Check created date
            if search_filter.created_date:
                start, end = search_filter.created_date.get_date_range()
                if start and page.created_date_time < start:
                    return False
                if end and page.created_date_time >= end:
                    return False
            
            # Check modified date
            if search_filter.modified_date:
                start, end = search_filter.modified_date.get_date_range()
                if start and page.last_modified_date_time < start:
                    return False
                if end and page.last_modified_date_time >= end:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Date filter check failed: {e}")
            return True

    async def _check_location_filters(self, 
                                    page: CachedPage, 
                                    search_filter: SearchFilter) -> bool:
        """Check location-based filters."""
        try:
            # Check notebook filters
            if search_filter.notebook_ids:
                if page.notebook_id not in search_filter.notebook_ids:
                    return False
            
            if search_filter.notebook_names:
                if page.notebook_name not in search_filter.notebook_names:
                    return False
            
            # Check section filters
            if search_filter.section_ids:
                if page.section_id not in search_filter.section_ids:
                    return False
            
            if search_filter.section_names:
                if page.section_name not in search_filter.section_names:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Location filter check failed: {e}")
            return True

    async def _check_content_type_filters(self, 
                                        page: CachedPage, 
                                        search_filter: SearchFilter) -> bool:
        """Check content type filters."""
        try:
            page_content_types = await self._get_page_content_types(page)
            
            # Check include filters
            if search_filter.content_types:
                if not any(ct in page_content_types for ct in search_filter.content_types):
                    return False
            
            # Check exclude filters
            if search_filter.exclude_content_types:
                if any(ct in page_content_types for ct in search_filter.exclude_content_types):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Content type filter check failed: {e}")
            return True

    async def _check_size_filters(self, 
                                page: CachedPage, 
                                search_filter: SearchFilter) -> bool:
        """Check content size filters."""
        try:
            content_length = len(page.content or "")
            
            if search_filter.min_content_length:
                if content_length < search_filter.min_content_length:
                    return False
            
            if search_filter.max_content_length:
                if content_length > search_filter.max_content_length:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Size filter check failed: {e}")
            return True

    async def _check_quality_filters(self, 
                                   page: CachedPage, 
                                   search_filter: SearchFilter) -> bool:
        """Check quality-based filters."""
        try:
            if search_filter.has_images is not None:
                has_images = await self._analyze_images(page)
                if has_images != search_filter.has_images:
                    return False
            
            if search_filter.has_tables is not None:
                has_tables = await self._analyze_tables(page)
                if has_tables != search_filter.has_tables:
                    return False
            
            if search_filter.has_links is not None:
                has_links = await self._analyze_links(page)
                if has_links != search_filter.has_links:
                    return False
            
            if search_filter.has_attachments is not None:
                has_attachments = await self._analyze_attachments(page)
                if has_attachments != search_filter.has_attachments:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Quality filter check failed: {e}")
            return True

    async def _check_conditions(self, 
                              page: CachedPage, 
                              search_filter: SearchFilter) -> bool:
        """Check custom filter conditions."""
        try:
            if not search_filter.conditions:
                return True
            
            results = []
            for condition in search_filter.conditions:
                result = await self._evaluate_condition(page, condition)
                results.append(result)
            
            # Combine results based on logic
            if search_filter.combine_conditions_with_and:
                return all(results)
            else:
                return any(results)
            
        except Exception as e:
            logger.error(f"Conditions check failed: {e}")
            return True

    async def _check_custom_filters(self, 
                                  page: CachedPage, 
                                  search_filter: SearchFilter) -> bool:
        """Check custom filter functions."""
        try:
            for name, filter_func in search_filter.custom_filters.items():
                try:
                    if not filter_func(page):
                        return False
                except Exception as e:
                    logger.error(f"Custom filter '{name}' failed: {e}")
                    # Continue with other filters
            
            return True
            
        except Exception as e:
            logger.error(f"Custom filters check failed: {e}")
            return True

    async def _evaluate_condition(self, 
                                page: CachedPage, 
                                condition: FilterCondition) -> bool:
        """Evaluate a single filter condition."""
        try:
            # Get field value from page
            field_value = getattr(page, condition.field, None)
            
            # Handle null checks
            if condition.operator == FilterOperator.IS_NULL:
                return field_value is None
            elif condition.operator == FilterOperator.IS_NOT_NULL:
                return field_value is not None
            
            # Skip if field is None for other operations
            if field_value is None:
                return False
            
            # Convert to string for text operations if needed
            if not condition.case_sensitive and isinstance(field_value, str):
                field_value = field_value.lower()
                if isinstance(condition.value, str):
                    condition.value = condition.value.lower()
            
            # Apply operator
            if condition.operator == FilterOperator.EQUALS:
                return field_value == condition.value
            elif condition.operator == FilterOperator.NOT_EQUALS:
                return field_value != condition.value
            elif condition.operator == FilterOperator.CONTAINS:
                return condition.value in str(field_value)
            elif condition.operator == FilterOperator.NOT_CONTAINS:
                return condition.value not in str(field_value)
            elif condition.operator == FilterOperator.STARTS_WITH:
                return str(field_value).startswith(str(condition.value))
            elif condition.operator == FilterOperator.ENDS_WITH:
                return str(field_value).endswith(str(condition.value))
            elif condition.operator == FilterOperator.IN:
                return field_value in condition.value
            elif condition.operator == FilterOperator.NOT_IN:
                return field_value not in condition.value
            elif condition.operator == FilterOperator.GREATER_THAN:
                return field_value > condition.value
            elif condition.operator == FilterOperator.LESS_THAN:
                return field_value < condition.value
            elif condition.operator == FilterOperator.GREATER_EQUAL:
                return field_value >= condition.value
            elif condition.operator == FilterOperator.LESS_EQUAL:
                return field_value <= condition.value
            elif condition.operator == FilterOperator.REGEX:
                import re
                pattern = re.compile(condition.value, re.IGNORECASE if not condition.case_sensitive else 0)
                return bool(pattern.search(str(field_value)))
            
            return False
            
        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            return False

    async def _get_page_content_types(self, page: CachedPage) -> Set[ContentType]:
        """Analyze page content to determine content types."""
        content_types = set()
        
        try:
            content = page.content or ""
            
            if await self._analyze_images(page):
                content_types.add(ContentType.IMAGES)
            if await self._analyze_tables(page):
                content_types.add(ContentType.TABLES)
            if await self._analyze_lists(page):
                content_types.add(ContentType.LISTS)
            if await self._analyze_code_blocks(page):
                content_types.add(ContentType.CODE_BLOCKS)
            if await self._analyze_links(page):
                content_types.add(ContentType.LINKS)
            if await self._analyze_attachments(page):
                content_types.add(ContentType.ATTACHMENTS)
            
            # Default to text if content exists
            if content.strip():
                content_types.add(ContentType.TEXT)
                
        except Exception as e:
            logger.error(f"Content type analysis failed: {e}")
        
        return content_types

    # Content analyzers
    async def _analyze_images(self, page: CachedPage) -> bool:
        """Check if page contains images."""
        try:
            content = page.content or ""
            # Look for image tags, references, or embedded images
            return any(tag in content.lower() for tag in ['<img', '![', '.png', '.jpg', '.jpeg', '.gif', '.bmp'])
        except:
            return False

    async def _analyze_tables(self, page: CachedPage) -> bool:
        """Check if page contains tables."""
        try:
            content = page.content or ""
            return '<table' in content.lower() or '|' in content  # Basic table detection
        except:
            return False

    async def _analyze_lists(self, page: CachedPage) -> bool:
        """Check if page contains lists."""
        try:
            content = page.content or ""
            return any(tag in content for tag in ['<ul', '<ol', '<li', '- ', '* ', '1.', '2.'])
        except:
            return False

    async def _analyze_code_blocks(self, page: CachedPage) -> bool:
        """Check if page contains code blocks."""
        try:
            content = page.content or ""
            return any(tag in content for tag in ['<code', '```', '`', '<pre'])
        except:
            return False

    async def _analyze_links(self, page: CachedPage) -> bool:
        """Check if page contains links."""
        try:
            content = page.content or ""
            return any(tag in content for tag in ['<a ', 'href=', 'http://', 'https://'])
        except:
            return False

    async def _analyze_attachments(self, page: CachedPage) -> bool:
        """Check if page contains attachments."""
        try:
            content = page.content or ""
            # Look for attachment indicators
            return any(tag in content.lower() for tag in ['attachment', 'file:', '.pdf', '.docx', '.xlsx'])
        except:
            return False

    async def _analyze_content_type(self, page: CachedPage) -> ContentType:
        """Determine primary content type of page."""
        try:
            if await self._analyze_code_blocks(page):
                return ContentType.CODE_BLOCKS
            elif await self._analyze_tables(page):
                return ContentType.TABLES
            elif await self._analyze_images(page):
                return ContentType.IMAGES
            elif await self._analyze_lists(page):
                return ContentType.LISTS
            else:
                return ContentType.TEXT
        except:
            return ContentType.TEXT

    def register_filter(self, name: str, filter_func: Callable[[CachedPage], bool]) -> None:
        """
        Register a custom filter function.

        Args:
            name: Filter name
            filter_func: Function that takes a CachedPage and returns bool
        """
        self.registered_filters[name] = filter_func
        logger.debug(f"Registered custom filter: {name}")

    def create_notebook_filter(self, notebook_names: List[str]) -> SearchFilter:
        """Create a filter for specific notebooks."""
        return SearchFilter(notebook_names=notebook_names)

    def create_date_filter(self, days_back: Optional[int] = None,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> SearchFilter:
        """Create a date-based filter."""
        date_filter = DateRangeFilter(
            start_date=start_date,
            end_date=end_date,
            days_back=days_back
        )
        return SearchFilter(modified_date=date_filter)

    def create_content_type_filter(self, content_types: List[ContentType]) -> SearchFilter:
        """Create a content type filter."""
        return SearchFilter(content_types=content_types)

    def create_size_filter(self, min_length: Optional[int] = None,
                          max_length: Optional[int] = None) -> SearchFilter:
        """Create a content size filter."""
        return SearchFilter(
            min_content_length=min_length,
            max_content_length=max_length
        )

    def combine_filters(self, *filters: SearchFilter, use_and: bool = True) -> SearchFilter:
        """
        Combine multiple filters into a single filter.

        Args:
            *filters: Filters to combine
            use_and: Whether to use AND logic (True) or OR logic (False)

        Returns:
            Combined filter
        """
        combined = SearchFilter()
        combined.combine_conditions_with_and = use_and
        
        for filter_obj in filters:
            # Combine conditions
            combined.conditions.extend(filter_obj.conditions)
            
            # Merge other properties (taking first non-None value)
            for attr in ['created_date', 'modified_date', 'notebook_ids', 'notebook_names',
                        'section_ids', 'section_names', 'content_types', 'exclude_content_types',
                        'min_content_length', 'max_content_length', 'has_images', 'has_tables',
                        'has_links', 'has_attachments']:
                current_value = getattr(combined, attr)
                filter_value = getattr(filter_obj, attr)
                if current_value is None and filter_value is not None:
                    setattr(combined, attr, filter_value)
            
            # Merge custom filters
            combined.custom_filters.update(filter_obj.custom_filters)
        
        return combined

    async def get_filter_suggestions(self, 
                                   pages: List[CachedPage]) -> Dict[str, List[Any]]:
        """
        Get filter suggestions based on page content analysis.

        Args:
            pages: Pages to analyze for suggestions

        Returns:
            Dictionary of suggested filter values
        """
        try:
            suggestions = {
                "notebooks": set(),
                "sections": set(),
                "content_types": set(),
                "date_ranges": [],
                "size_ranges": []
            }
            
            content_lengths = []
            
            for page in pages:
                # Collect notebooks and sections
                suggestions["notebooks"].add(page.notebook_name)
                suggestions["sections"].add(page.section_name)
                
                # Analyze content types
                page_types = await self._get_page_content_types(page)
                suggestions["content_types"].update(page_types)
                
                # Collect content lengths
                content_lengths.append(len(page.content or ""))
            
            # Convert sets to sorted lists
            suggestions["notebooks"] = sorted(list(suggestions["notebooks"]))
            suggestions["sections"] = sorted(list(suggestions["sections"]))
            suggestions["content_types"] = [ct.value for ct in suggestions["content_types"]]
            
            # Generate date range suggestions
            suggestions["date_ranges"] = [
                "today", "yesterday", "this_week", "last_week",
                "this_month", "last_month", "last_7_days", "last_30_days"
            ]
            
            # Generate size range suggestions based on content
            if content_lengths:
                min_length = min(content_lengths)
                max_length = max(content_lengths)
                avg_length = sum(content_lengths) // len(content_lengths)
                
                suggestions["size_ranges"] = [
                    f"small (< {avg_length // 2})",
                    f"medium ({avg_length // 2} - {avg_length * 2})",
                    f"large (> {avg_length * 2})"
                ]
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Filter suggestions generation failed: {e}")
            return {}
