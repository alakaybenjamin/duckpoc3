"""
Search provider implementation for scientific papers.
"""
from typing import List, Dict, Any
from sqlalchemy import or_, func, String, and_, case, cast
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta
from models.database_models import ScientificPaper
from services.search.base import SearchProvider, SearchQuery, SearchResult

logger = logging.getLogger(__name__)

class ScientificPaperSearchProvider(SearchProvider):
    def __init__(self, db: Session):
        self.db = db

    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute search against scientific papers collection"""
        try:
            logger.debug(f"Starting scientific papers search with query: {query.terms}")

            # Build base query
            base_query = self.db.query(ScientificPaper)
            logger.debug("Created base query")

            # Apply search terms
            if query.terms:
                search_conditions = []
                for term in query.terms:
                    term = term.strip().lower()
                    logger.debug(f"Processing search term: {term}")
                    term_conditions = [
                        ScientificPaper.title.ilike(f"%{term}%"),
                        ScientificPaper.abstract.ilike(f"%{term}%"),
                        ScientificPaper.journal.ilike(f"%{term}%"),
                        # Search in keywords JSON array with explicit cast
                        func.cast(ScientificPaper.keywords, String).ilike(f"%{term}%")
                    ]
                    search_conditions.append(or_(*term_conditions))

                # Combine all conditions with OR
                base_query = base_query.filter(or_(*search_conditions))
                logger.debug(f"Applied search conditions for terms: {query.terms}")

            # Apply user context based filters (authorization)
            if query.user_context:
                logger.debug(f"Applying authorization filters based on user context")
                
                # Example: Filter by access level
                user_role = query.user_context.get('role', 'user')
                
                # Check if user has restricted content access or is an admin
                has_restricted_access = user_role in ['admin', 'researcher', 'premium']
                
                # If the user doesn't have access to restricted content, filter it out
                if not has_restricted_access:
                    # Example: Filter out papers that require special access
                    base_query = base_query.filter(
                        or_(
                            ScientificPaper.is_restricted.is_(None),
                            ScientificPaper.is_restricted == False
                        )
                    )
                    logger.debug(f"Applied restriction filter for user role: {user_role}")
                    
                # You could also add organization-based filtering
                org_id = query.user_context.get('org_id')
                if org_id and user_role != 'admin':
                    # Example: Only show papers that belong to the user's organization
                    # This is just an example - adjust according to your actual data model
                    base_query = base_query.filter(
                        or_(
                            ScientificPaper.organization_id.is_(None),
                            ScientificPaper.organization_id == org_id
                        )
                    )
                    logger.debug(f"Applied organization filter for org_id: {org_id}")

            # Apply filters
            if query.filters:
                filter_conditions = []

                # Journal filter
                if journal := query.filters.get('journal'):
                    filter_conditions.append(ScientificPaper.journal == journal)

                # Publication date filter
                if date_range := query.filters.get('date_range'):
                    now = datetime.utcnow()
                    if date_range == 'last_week':
                        start_date = now - timedelta(weeks=1)
                    elif date_range == 'last_month':
                        start_date = now - timedelta(days=30)
                    elif date_range == 'last_year':
                        start_date = now - timedelta(days=365)

                    if date_range in ['last_week', 'last_month', 'last_year']:
                        filter_conditions.append(ScientificPaper.publication_date >= start_date)

                # Citations filter
                if citations := query.filters.get('citations'):
                    if citations == '0-10':
                        filter_conditions.append(and_(
                            ScientificPaper.citations_count >= 0,
                            ScientificPaper.citations_count <= 10
                        ))
                    elif citations == '11-50':
                        filter_conditions.append(and_(
                            ScientificPaper.citations_count >= 11,
                            ScientificPaper.citations_count <= 50
                        ))
                    elif citations == '51-100':
                        filter_conditions.append(and_(
                            ScientificPaper.citations_count >= 51,
                            ScientificPaper.citations_count <= 100
                        ))
                    elif citations == '100+':
                        filter_conditions.append(ScientificPaper.citations_count > 100)

                if filter_conditions:
                    base_query = base_query.filter(and_(*filter_conditions))
                    logger.debug(f"Applied filters: {query.filters}")

            # Apply pagination
            base_query = base_query.offset((query.page - 1) * query.per_page).limit(query.per_page)
            logger.debug(f"Applied pagination: page={query.page}, per_page={query.per_page}")

            # Execute query
            papers = base_query.all()
            logger.debug(f"Found {len(papers)} papers matching the query")

            # Transform to SearchResults
            results = []
            for paper in papers:
                try:
                    metadata = {
                        'authors': paper.authors if paper.authors else [],
                        'publication_date': paper.publication_date.isoformat() if paper.publication_date else None,
                        'journal': paper.journal,
                        'doi': paper.doi,
                        'keywords': paper.keywords if paper.keywords else [],
                        'citations_count': paper.citations_count,
                        'references': paper.reference_list if paper.reference_list else []
                    }

                    result = SearchResult(
                        id=str(paper.id),
                        type='scientific_paper',
                        title=paper.title,
                        description=paper.abstract,
                        data=metadata
                    )
                    results.append(result)
                    logger.debug(f"Transformed paper {paper.id} into search result")
                except Exception as e:
                    logger.error(f"Error transforming paper {paper.id}: {str(e)}")
                    continue

            logger.debug(f"Successfully transformed {len(results)} papers into search results")
            return results

        except Exception as e:
            logger.error(f"Error in scientific papers search: {str(e)}", exc_info=True)
            raise

    def get_available_filters(self) -> Dict[str, List[str]]:
        """Return available filters for scientific papers"""
        try:
            journals = [j[0] for j in self.db.query(ScientificPaper.journal).distinct().all() if j[0]]
            logger.debug(f"Found {len(journals)} distinct journals for filtering")
            return {
                'journal': journals,
                'date_range': ['last_week', 'last_month', 'last_year'],
                'citations': ['0-10', '11-50', '51-100', '100+']
            }
        except Exception as e:
            logger.error(f"Error getting filters: {str(e)}")
            return {}