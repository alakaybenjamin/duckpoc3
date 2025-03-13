"""
Base classes for the extensible search service architecture.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SearchQuery:
    """Represents a search query with filters"""
    terms: List[str]
    filters: Dict[str, Any]
    collection_type: str = "clinical_study"
    page: int = 1
    per_page: int = 10
    schema_type: str = "default"

@dataclass
class SearchResult:
    """
    Base class for search results
    
    This is a generic container for search results across all providers.
    Provider-specific fields should be stored in the `data` dictionary.
    """
    id: str                                # Unique identifier for the result
    type: str                              # The type of result (e.g., clinical_study, scientific_paper)
    title: str                             # Title of the result
    description: Optional[str] = None      # Brief description of the result
    relevance_score: Optional[float] = None  # Relevance score for ranking
    
    # Generic container for provider-specific data
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Associated data products
    data_products: List[Dict[str, Any]] = field(default_factory=list)
    
    # Internal properties for pagination and query reference (not part of returned data)
    _query: Any = None
    _total: int = 0

class SearchProvider(ABC):
    """Abstract base class for collection-specific search providers"""

    @abstractmethod
    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute search against the collection"""
        pass

    @abstractmethod
    def get_available_filters(self) -> Dict[str, List[str]]:
        """Return available filters for this collection"""
        pass

class SchemaTransformer(ABC):
    """Abstract base class for result schema transformers"""

    @abstractmethod
    def transform(self, results: List[SearchResult]) -> Dict[str, Any]:
        """Transform search results into the desired output format"""
        pass

class SearchProviderRegistry:
    """Registry for search providers"""
    _providers: Dict[str, Any] = {}

    @classmethod
    def register(cls, collection_type: str, provider: Any):
        """Register a provider for a collection type"""
        cls._providers[collection_type] = provider

    @classmethod
    def get_provider(cls, collection_type: str) -> SearchProvider:
        """Get the appropriate provider for a collection type"""
        if collection_type not in cls._providers:
            raise ValueError(f"No provider registered for collection type: {collection_type}")
        return cls._providers[collection_type]()

class SchemaRegistry:
    """Registry for output schema transformers"""
    _transformers: Dict[str, Any] = {}

    @classmethod
    def register(cls, schema_type: str, transformer: Any):
        """Register a transformer for a schema type"""
        cls._transformers[schema_type] = transformer

    @classmethod
    def get_transformer(cls, schema_type: str) -> SchemaTransformer:
        """Get a transformer for a schema type"""
        if schema_type not in cls._transformers:
            return None
        return cls._transformers[schema_type]()