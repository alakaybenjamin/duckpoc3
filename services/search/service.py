"""
Search service that coordinates providers and transformers.
"""
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from services.search.base import (
    SearchQuery, SearchProviderRegistry, SchemaRegistry
)
from services.search.providers.clinical_studies import ClinicalStudySearchProvider
from services.search.providers.scientific_papers import ScientificPaperSearchProvider
from services.search.providers.data_domain import DataDomainSearchProvider
from services.search.transformers import (
    DefaultSchemaTransformer,
    CompactSchemaTransformer,
    DetailedSchemaTransformer,
    ScientificPaperSchemaTransformer,
    DataDomainSchemaTransformer,
    ClinicalStudyCustomTransformer
)
import logging

class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self._register_defaults()

    def _register_defaults(self):
        """Register default providers and transformers"""
        logger = logging.getLogger(__name__)
        
        # Register providers
        SearchProviderRegistry._providers = {
            'clinical_study': ClinicalStudySearchProvider,
            'scientific_paper': ScientificPaperSearchProvider,
            'data_domain': DataDomainSearchProvider
        }

        # Register transformers
        SchemaRegistry._transformers = {
            'default': DefaultSchemaTransformer,
            'compact': CompactSchemaTransformer,
            'detailed': DetailedSchemaTransformer,
            'scientific_paper': ScientificPaperSchemaTransformer,
            'data_domain': DataDomainSchemaTransformer,
            'clinical_study_custom': ClinicalStudyCustomTransformer
        }
        
        logger.debug(f"Registered transformers: {list(SchemaRegistry._transformers.keys())}")

    def search(self, collection_type: str, terms: List[str], filters: Dict, page: int = 1, per_page: int = 10, schema_type: str = "default", user_context: Dict = None) -> List[Any]:
        """
        Execute search across specified collection with configurable output schema and filters
        
        Args:
            collection_type: Type of collection to search
            terms: List of search terms
            filters: Dictionary of filters to apply
            page: Page number (1-based)
            per_page: Items per page
            schema_type: Type of schema to use for results
            user_context: Optional user context from JWT token for authorization
            
        Returns:
            List of search results
        """
        # Add debug logging for the schema_type
        logger = logging.getLogger(__name__)
        logger.debug(f"Search service called with collection_type: {collection_type!r}, schema_type: {schema_type!r}")
        
        # Force clinical_study_custom schema for clinical studies
        if collection_type == 'clinical_study' and schema_type != 'clinical_study_custom':
            logger.debug(f"Forcing schema_type to 'clinical_study_custom' for clinical studies")
            schema_type = 'clinical_study_custom'
            
        logger.debug(f"Available transformers: {list(SchemaRegistry._transformers.keys())}")
        
        # Get the appropriate provider
        provider_class = SearchProviderRegistry._providers.get(collection_type)
        if not provider_class:
            raise ValueError(f"No provider registered for collection type: {collection_type}")

        # Create provider instance
        provider = provider_class(self.db)

        # Create search query
        query = SearchQuery(
            terms=terms,
            collection_type=collection_type,
            page=page,
            per_page=per_page,
            filters=filters,
            schema_type=schema_type
        )
        
        # Add user context to query if provided
        if user_context:
            query.user_context = user_context

        # Execute search
        results = provider.search(query)
        logger.debug(f"Search returned {len(results)} results")

        # Get the appropriate transformer with a fallback
        from services.search.transformers import (
            DefaultSchemaTransformer,
            CompactSchemaTransformer,
            DetailedSchemaTransformer,
            ScientificPaperSchemaTransformer,
            DataDomainSchemaTransformer,
            ClinicalStudyCustomTransformer
        )
        
        # Map schema_type to transformer class directly
        transformer_map = {
            'default': DefaultSchemaTransformer,
            'compact': CompactSchemaTransformer,
            'detailed': DetailedSchemaTransformer,
            'scientific_paper': ScientificPaperSchemaTransformer,
            'data_domain': DataDomainSchemaTransformer,
            'clinical_study_custom': ClinicalStudyCustomTransformer
        }
        
        transformer_class = transformer_map.get(schema_type) or DefaultSchemaTransformer
        logger.debug(f"Using transformer: {transformer_class.__name__} for schema_type: {schema_type!r}")
        
        # Special case for clinical studies - force the custom transformer
        if collection_type == 'clinical_study':
            logger.debug("Clinical study detected, checking if using correct transformer")
            if transformer_class != ClinicalStudyCustomTransformer:
                logger.debug(f"Wrong transformer! Using {transformer_class.__name__} instead of ClinicalStudyCustomTransformer")
                transformer_class = ClinicalStudyCustomTransformer
                logger.debug("Forced ClinicalStudyCustomTransformer")
        
        transformer = transformer_class()
        # Pass user context to transformer if needed
        if user_context and hasattr(transformer, 'set_user_context'):
            transformer.set_user_context(user_context)
        transformed_results = transformer.transform(results)
        logger.debug(f"Transformed results type: {type(transformed_results)}")
        logger.debug(f"Transformed results keys: {transformed_results.keys() if isinstance(transformed_results, dict) else 'Not a dict'}")
        return transformed_results

    def get_available_filters(self, collection_type: str) -> Dict[str, List[str]]:
        """Get available filters for a collection type"""
        if collection_type not in SearchProviderRegistry._providers:
            raise ValueError(f"No provider registered for collection type: {collection_type}")

        provider = SearchProviderRegistry._providers[collection_type](self.db)
        return provider.get_available_filters()
        
    def get_provider(self, collection_type: str):
        """Get a provider instance for a collection type"""
        provider_class = SearchProviderRegistry._providers.get(collection_type)
        if not provider_class:
            return None
            
        return provider_class(self.db)