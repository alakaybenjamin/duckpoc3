"""
Search provider implementation for clinical studies collection.
"""
from typing import List, Dict, Any
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session, joinedload
from models.database_models import ClinicalStudy, DataProduct
from services.search.base import SearchProvider, SearchQuery, SearchResult

class ClinicalStudySearchProvider(SearchProvider):
    def __init__(self, db: Session):
        self.db = db

    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute search against clinical studies collection"""
        # Build base query - use joinedload to eagerly load data_products
        base_query = self.db.query(ClinicalStudy).options(joinedload(ClinicalStudy.data_products))

        # Apply search terms
        if query.terms:
            search_conditions = []
            for term in query.terms:
                term_conditions = [
                    ClinicalStudy.title.ilike(f"%{term}%"),
                    ClinicalStudy.description.ilike(f"%{term}%"),
                    ClinicalStudy.drug.ilike(f"%{term}%"),  # Added drug search
                ]
                search_conditions.extend(term_conditions)

            base_query = base_query.filter(or_(*search_conditions))

        # Apply filters
        for filter_name, filter_value in query.filters.items():
            if not hasattr(ClinicalStudy, filter_name):
                continue
                
            if isinstance(filter_value, dict):
                # Handle range filters
                if filter_name == 'duration':
                    min_val = filter_value.get('min')
                    max_val = filter_value.get('max')
                    if min_val and str(min_val).isdigit():
                        base_query = base_query.filter(getattr(ClinicalStudy, filter_name) >= int(min_val))
                    if max_val and str(max_val).isdigit():
                        base_query = base_query.filter(getattr(ClinicalStudy, filter_name) <= int(max_val))
            elif isinstance(filter_value, list):
                # Handle arrays of values (OR condition)
                if filter_value:  # Only apply filter if list is not empty
                    filter_conditions = [
                        getattr(ClinicalStudy, filter_name) == val 
                        for val in filter_value
                    ]
                    base_query = base_query.filter(or_(*filter_conditions))
            else:
                # Handle simple equality filters
                if filter_value:  # Only apply filter if value is not empty
                    base_query = base_query.filter(getattr(ClinicalStudy, filter_name) == filter_value)

        # Get total count before pagination
        total_count = base_query.count()

        # Apply pagination
        studies = base_query.offset((query.page - 1) * query.per_page).limit(query.per_page).all()

        # Transform to SearchResults
        results = []
        for study in studies:
            # Get associated data products (limited to 2)
            data_products = []
            for dp in study.data_products[:2]:  # Limit to 2 data products
                data_products.append({
                    'id': dp.id,
                    'title': dp.title,
                    'description': dp.description,
                    'type': dp.type,
                    'format': dp.format,
                    'size': dp.size,
                    'access_level': dp.access_level
                })
            
            result = SearchResult(
                id=str(study.id),
                type='clinical_study',
                title=study.title,
                description=study.description,
                relevance_score=study.relevance_score,
                # Store all clinical study specific fields in the data dictionary
                data={
                    'status': study.status,
                    'phase': study.phase,
                    'drug': study.drug,
                    'indication_category': study.indication_category,
                    'procedure_category': study.procedure_category,
                    'severity': study.severity,
                    'risk_level': study.risk_level,
                    'duration': study.duration,
                    'start_date': study.start_date,
                    'end_date': study.end_date,
                    'institution': study.institution,
                    'participant_count': study.participant_count
                },
                # Include data products directly in the result
                data_products=data_products
            )
            # Attach query and total count to result
            result._query = query
            result._total = total_count
            results.append(result)

        return results

    def get_available_filters(self) -> Dict[str, List[str]]:
        """Return available filters for clinical studies"""
        return {
            'status': ['Recruiting', 'Active', 'Completed', 'Not yet recruiting'],
            'phase': ['Phase I', 'Phase II', 'Phase III', 'Phase IV'],
            'drug': self._get_distinct_values('drug'),
            'indication_category': self._get_distinct_values('indication_category'),
            'procedure_category': self._get_distinct_values('procedure_category'),
            'severity': ['Mild', 'Moderate', 'Severe'],
            'risk_level': ['Low', 'Medium', 'High'],
            'duration': {'type': 'range', 'min': 0, 'max': None}
        }
        
    def _get_distinct_values(self, field_name: str) -> List[str]:
        """Get distinct values for a given field from the database"""
        if not hasattr(ClinicalStudy, field_name):
            return []
            
        values = self.db.query(getattr(ClinicalStudy, field_name)).distinct().all()
        return [value[0] for value in values if value[0] is not None]