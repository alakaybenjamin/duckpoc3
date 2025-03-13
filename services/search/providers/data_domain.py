"""
Search provider implementation for data domain metadata.
"""
from typing import List, Dict, Any
from sqlalchemy import or_
from sqlalchemy.orm import Session
from models.database_models import DataDomainMetadata
from services.search.base import SearchProvider, SearchQuery, SearchResult

class DataDomainSearchProvider(SearchProvider):
    def __init__(self, db: Session):
        self.db = db

    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute search against data domain metadata collection"""
        # Build base query
        base_query = self.db.query(DataDomainMetadata)

        # Apply search terms
        if query.terms:
            search_conditions = []
            for term in query.terms:
                term_conditions = [
                    DataDomainMetadata.domain_name.ilike(f"%{term}%"),
                    DataDomainMetadata.description.ilike(f"%{term}%"),
                    DataDomainMetadata.owner.ilike(f"%{term}%"),
                ]
                search_conditions.extend(term_conditions)

            base_query = base_query.filter(or_(*search_conditions))

        # Apply filters
        for filter_name, filter_value in query.filters.items():
            if hasattr(DataDomainMetadata, filter_name):
                base_query = base_query.filter(getattr(DataDomainMetadata, filter_name) == filter_value)

        # Apply pagination
        domains = base_query.offset((query.page - 1) * query.per_page).limit(query.per_page).all()

        # Transform to SearchResults
        results = []
        for domain in domains:
            results.append(SearchResult(
                id=str(domain.id),
                type='data_domain',
                title=domain.domain_name,
                description=domain.description,
                data={
                    'schema_definition': domain.schema_definition,
                    'validation_rules': domain.validation_rules,
                    'data_format': domain.data_format,
                    'sample_data': domain.sample_data,
                    'owner': domain.owner,
                    'created_at': domain.created_at.isoformat(),
                    'updated_at': domain.updated_at.isoformat()
                }
            ))

        return results

    def get_available_filters(self) -> Dict[str, List[str]]:
        """Return available filters for data domains"""
        return {
            'data_format': ['CSV', 'JSON', 'XML'],
            'owner': self.db.query(DataDomainMetadata.owner).distinct().all()
        }
