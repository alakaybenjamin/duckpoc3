"""
Search provider implementation for scientific papers.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import logging
import sys
import os
import asyncio  # Add asyncio import for create_task

# Add the parent directory to sys.path to allow imports from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from services.search.service import SearchService
from pydantic import BaseModel, Field, validator
from routes.auth import  csrf_protect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from routes.history import save_search, HistoryEntryBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

# Authentication scheme
security = HTTPBearer(auto_error=False)

# Authentication dependency
async def get_authenticated_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """Get authenticated user from token or session"""
    print(f"SEARCH AUTH DEBUG - Starting get_authenticated_user")
    print(f"SEARCH AUTH DEBUG - Request session: {request.session}")
    print(f"SEARCH AUTH DEBUG - Request cookies: {request.cookies}")
    print(f"SEARCH AUTH DEBUG - Headers: {request.headers}")
    
    token = None
    
    # First try from Authorization header
    if credentials:
        token = credentials.credentials
        print(f"SEARCH AUTH DEBUG - Token found in Authorization header")
        logger.debug("Token found in Authorization header")
    
    # If no token in header, check cookies
    if not token and "token" in request.cookies:
        token = request.cookies.get("token")
        print(f"SEARCH AUTH DEBUG - Token found in cookies")
        logger.debug("Token found in cookies")
    
    # If still no token, check session
    if not token and request.session.get("authenticated"):
        print(f"SEARCH AUTH DEBUG - Session indicates user is authenticated")
        logger.debug("Session indicates user is authenticated")
        # Session auth doesn't have a token but is still valid
        
    # Try to get user info
    user_info = None
    
    # If token exists, verify it
    if token:
        try:
            from security import decode_access_token
            
            print(f"SEARCH AUTH DEBUG - Attempting to decode token")
            payload = decode_access_token(token)
            print(f"SEARCH AUTH DEBUG - Token payload: {payload}")
            
            user_email = payload.get("sub")
            if user_email:
                from models.database_models import User
                
                print(f"SEARCH AUTH DEBUG - Looking up user by email: {user_email}")
                user = db.query(User).filter(User.email == user_email).first()
                if user:
                    user_info = {
                        "id": user.id,
                        "email": user.email,
                        "is_authenticated": True
                    }
                    print(f"SEARCH AUTH DEBUG - Found user from token: {user_info}")
                else:
                    print(f"SEARCH AUTH DEBUG - No user found with email: {user_email}")
            else:
                print(f"SEARCH AUTH DEBUG - No email found in token")
        except Exception as e:
            print(f"SEARCH AUTH DEBUG - Error verifying token: {str(e)}")
            logger.error(f"Error verifying token: {str(e)}")
    
    # If no token or token verification failed, try session
    if not user_info and "user_id" in request.session:
        try:
            from models.database_models import User
            print(f"SEARCH AUTH DEBUG - Looking up user from session, user_id: {request.session['user_id']}")
            user = db.query(User).filter(User.id == request.session["user_id"]).first()
            if user:
                user_info = {
                    "id": user.id,
                    "email": user.email,
                    "is_authenticated": True
                }
                print(f"SEARCH AUTH DEBUG - Found user from session: {user_info}")
            else:
                print(f"SEARCH AUTH DEBUG - No user found with ID: {request.session['user_id']}")
        except Exception as e:
            print(f"SEARCH AUTH DEBUG - Error getting user from session: {str(e)}")
            logger.error(f"Error getting user from session: {str(e)}")
    
    # If we couldn't get user info, return a minimal context
    if not user_info:
        print(f"SEARCH AUTH DEBUG - No user authentication found, using minimal context")
        logger.debug("No user authentication found, using minimal context")
        user_info = {
            "is_authenticated": False
        }
    
    print(f"SEARCH AUTH DEBUG - Final user_info: {user_info}")
    return user_info

class SearchRequest(BaseModel):
    query: str = Field(
        ..., 
        min_length=2, 
        description="Search query string",
        example="cancer"
    )
    collection_type: str = Field(
        default="clinical_study",
        description="Type of collection to search",
        example="clinical_study"
    )
    schema_type: str = Field(
        default="default",
        description="Response schema type",
        example="default"
    )
    page: int = Field(
        default=1, 
        ge=1, 
        description="Page number",
        example=1
    )
    per_page: int = Field(
        default=10, 
        ge=1, 
        le=100, 
        description="Items per page",
        example=10
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="""
        Optional filters for the search:
        - journal: Filter by specific journal (e.g., "Nature Medicine", "Science")
        - date_range: Filter by publication date ("last_week", "last_month", "last_year")
        - citations: Filter by citation count ("0-10", "11-50", "51-100", "100+")
        """,
        example={
            "status": ["Recruiting"],
            "phase": ["Phase I"]
        }
    )

    @validator('collection_type')
    def validate_collection_type(cls, v):
        allowed_types = ['clinical_study', 'scientific_paper', 'data_domain']
        if v not in allowed_types:
            raise ValueError(f"Collection type must be one of: {', '.join(allowed_types)}")
        return v

    @validator('schema_type')
    def validate_schema_type(cls, v):
        allowed_types = ['default', 'compact', 'detailed', 'scientific_paper', 'data_domain', 'clinical_study_custom']
        if v not in allowed_types:
            raise ValueError(f"Schema type must be one of: {', '.join(allowed_types)}")
        return v

@router.post("/search", 
    # Don't use a fixed response_model to allow custom formats
    # response_model=SearchResponse,
    summary="Search across collections",
    description="""
    Execute a search across clinical studies with configurable output schema and filters.

    Supports searching in clinical studies by:
    - Study title and description
    - Study status (e.g. Recruiting, Completed)
    - Study phase (e.g. Phase 1, Phase 2)
    - Study type (e.g. Interventional, Observational)
    - Conditions and interventions
    - Location and facilities

    For clinical studies, you can filter by:
    - Study status
    - Study phase
    - Start and completion dates
    - Study type
    - Location/facility
    - Number of enrolled participants

    The response includes pagination information and can be formatted according to different schema types.
    
    ## Authentication
    This endpoint requires authentication. You can provide authentication in one of these ways:
    
    1. **Bearer Token** - Include an Authorization header with a JWT token:
       `Authorization: Bearer your_token_here`
       
       When using Swagger UI, enter your Bearer token in the token field at the top of the page.
       
    2. **Cookie Authentication** - If you're logged in through the browser interface, 
       the session cookie will be used automatically.
       
    ## CSRF Protection
    When using cookie-based authentication, a CSRF token must be provided in the X-CSRF-Token header.
    This is not required when using Bearer token authentication.
    
    ## Example Request
    ```
    curl -X 'POST' \\
      'http://localhost:8001/api/search' \\
      -H 'accept: application/json' \\
      -H 'Content-Type: application/json' \\
      -H 'X-CSRF-Token: 47ec88c12d16ccb7bee99a9287ec6a0d' \\
      -H 'Authorization: Bearer aasddf' \\
      -d '{
      "query": "cancer",
      "collection_type": "clinical_study",
      "schema_type": "default",
      "page": 1,
      "per_page": 10
    }'
    ```
    """
)
async def search(
    request: Request,
    search_request: SearchRequest,
    user_info: Dict = Depends(get_authenticated_user),
    csrf_check: bool = Depends(csrf_protect),
    db: Session = Depends(get_db)
):
    """
    Search across collections with configurable output schema and filters.
    Authentication is required.
    """
    try:
        logger.debug(f"Search request received: {search_request}")
        logger.debug(f"User info: {user_info}")
        logger.debug(f"Schema type requested: {search_request.schema_type!r}")
        logger.debug(f"Collection type: {search_request.collection_type!r}")

        # Create search service
        search_service = SearchService(db)

        # Apply user context for filtering if available
        filters = search_request.filters.copy()
        if user_info:
            # Apply user-specific filters here based on roles
            user_role = user_info.get("role", "user")
            if user_role != "admin" and "restricted_content" in filters:
                # Non-admins can't access restricted content
                filters.pop("restricted_content")

        # Execute search with user context if available
        terms = []
        if search_request.query:
            terms = search_request.query.split(' OR ')
            # Remove empty terms
            terms = [term.strip() for term in terms if term.strip()]
        
        logger.debug(f"Search terms after processing: {terms}")
        logger.debug(f"Final schema_type being used: {search_request.schema_type!r}")
        
        results = search_service.search(
            collection_type=search_request.collection_type,
            terms=terms,
            filters=filters,
            page=search_request.page,
            per_page=search_request.per_page,
            schema_type=search_request.schema_type,
            user_context=user_info  # Pass user context to search service if needed
        )
        
        # Log the search to the user's search history if user is authenticated
        if user_info and user_info.get("is_authenticated", False):
            try:
                print(f"SEARCH DEBUG - Attempting to log search to history using async task")
                print(f"SEARCH DEBUG - User info: {user_info}")
                
                # Count the total results to save in history
                results_count = 0
                if isinstance(results, dict) and 'pagination' in results:
                    results_count = results['pagination'].get('total', 0)
                
                # Create history entry data
                search_data = HistoryEntryBase(
                    query=" ".join(terms) if terms else "",
                    category=search_request.collection_type,
                    filters=search_request.filters,
                    results_count=results_count  # Add results_count to the search_data object
                )
                
                # Create a task-specific database session factory function
                async def get_task_db():
                    from database import SessionLocal
                    task_db = SessionLocal()
                    try:
                        yield task_db
                    finally:
                        task_db.close()
                
                # Define a wrapper function that will execute in the background task
                async def save_search_wrapper():
                    try:
                        # Create a fresh database session for this task
                        from database import SessionLocal
                        task_db = SessionLocal()
                        search_history_id = None
                        try:
                            # Call save_search with the fresh session
                            response = await save_search(
                                request=request,
                                search_data=search_data,
                                db=task_db
                            )
                            # Get the search history ID from the response
                            if response and isinstance(response, dict) and "id" in response:
                                search_history_id = response.get("id")
                                logger.debug(f"Retrieved search history ID: {search_history_id}")
                                # Add the search history ID to the results
                                if isinstance(results, dict):
                                    results["search_history_id"] = search_history_id
                        finally:
                            # Make sure to close the session when done
                            task_db.close()
                        return search_history_id
                    except Exception as e:
                        logger.error(f"Background search history save failed: {str(e)}", exc_info=True)
                        return None
                
                # Create an async task to save the search history and wait for it to complete
                # We need to wait for it to get the ID
                search_history_task = asyncio.create_task(save_search_wrapper())
                search_history_id = await search_history_task
                
                # Add the search history ID to the results if it's not already there
                if search_history_id and isinstance(results, dict) and "search_history_id" not in results:
                    results["search_history_id"] = search_history_id
                
                print(f"SEARCH DEBUG - Created search history with ID: {search_history_id}")
                logger.debug(f"Created search history with ID: {search_history_id}")
                
            except Exception as e:
                # If logging history fails, just log the error but don't interrupt the search
                print(f"SEARCH DEBUG - Error creating search history task: {str(e)}")
                logger.error(f"Failed to create search history task: {str(e)}", exc_info=True)
        else:
            print(f"SEARCH DEBUG - Not logging search history - user not authenticated")
            print(f"SEARCH DEBUG - User info: {user_info}")
        
        if isinstance(results, dict):
            logger.debug(f"Result keys: {list(results.keys())}")
            if 'results' in results and results['results']:
                logger.debug(f"First result keys: {list(results['results'][0].keys())}")
        
        return results

    except ValueError as e:
        logger.error(f"Validation error in search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        logger.error(f"Search operation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search operation failed: {str(e)}"
        )

@router.get("/filters", response_model=Dict[str, Any])
async def get_filters(
    collection_type: str = Query("scientific_paper", description="Type of collection"),
    db: Session = Depends(get_db)
):
    """
    Get available filters for a collection type
    """
    try:
        search_service = SearchService(db)
        provider = search_service.get_provider(collection_type)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported collection type: {collection_type}"
            )
        
        filters = provider.get_available_filters()
        return filters
    except Exception as e:
        logger.error(f"Error getting filters: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching filters"
        )

@router.get("/suggest",
    summary="Get search suggestions",
    description="""
    Get search suggestions based on partial input
    
    ## Authentication
    This endpoint requires authentication. You can provide authentication in one of these ways:
    
    1. **Bearer Token** - Include an Authorization header with a JWT token
    2. **Cookie Authentication** - If you're logged in through the browser interface
    """
)
async def get_suggestions(
    q: str = Query(
        ..., 
        min_length=2,
        description="Search query for suggestions",
        example="cancer"
    ),
    collection_type: str = Query(
        'clinical_study', 
        description="Type of collection for suggestions"
    ),
    user_info: Dict = Depends(get_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Get search suggestions based on partial input
    """
    try:
        logger.debug(f"Suggestion request received for query: {q}, collection: {collection_type}")

        # Create search service
        search_service = SearchService(db)

        # Execute search with compact schema for suggestions
        results = search_service.search(
            collection_type=collection_type,
            terms=[q],
            filters={},
            per_page=5,
            schema_type='compact'
        )
        
        logger.debug(f"Suggestion results type: {type(results)}")
        
        # Handle different result formats
        suggestions = []
        if isinstance(results, dict) and 'results' in results:
            # Format from transformer
            for r in results['results']:
                try:
                    suggestions.append({
                        "text": r.get('title', 'Untitled'),
                        "type": r.get('type', collection_type)
                    })
                except Exception as err:
                    logger.error(f"Error processing suggestion result: {str(err)}")
        elif isinstance(results, list):
            # Direct results list
            for r in results:
                try:
                    if hasattr(r, 'title') and hasattr(r, 'type'):
                        suggestions.append({
                            "text": r.title,
                            "type": r.type
                        })
                    elif isinstance(r, dict):
                        suggestions.append({
                            "text": r.get('title', 'Untitled'),
                            "type": r.get('type', collection_type)
                        })
                except Exception as err:
                    logger.error(f"Error processing suggestion result: {str(err)}")

        return {"suggestions": suggestions}

    except Exception as e:
        logger.error(f"Failed to get suggestions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get suggestions: {str(e)}"
        )

@router.get("/debug/transformers", include_in_schema=False)
async def debug_transformers():
    """Debug endpoint to see registered transformers"""
    from services.search.base import SchemaRegistry
    import importlib
    
    # Try to import the initialization module again
    try:
        importlib.reload(importlib.import_module('services.search.init_registry'))
        logger.debug("Reloaded initialization module")
    except Exception as e:
        logger.error(f"Error reloading initialization module: {str(e)}")
    
    # Check if transformers are registered
    transformers = list(SchemaRegistry._transformers.keys())
    logger.debug(f"Found transformers: {transformers}")
    
    # Register them manually for this request if needed
    if not transformers:
        from services.search.transformers import (
            DefaultSchemaTransformer,
            CompactSchemaTransformer,
            DetailedSchemaTransformer,
            ScientificPaperSchemaTransformer,
            DataDomainSchemaTransformer,
            ClinicalStudyCustomTransformer
        )
        
        SchemaRegistry._transformers = {
            'default': DefaultSchemaTransformer,
            'compact': CompactSchemaTransformer,
            'detailed': DetailedSchemaTransformer, 
            'scientific_paper': ScientificPaperSchemaTransformer,
            'data_domain': DataDomainSchemaTransformer,
            'clinical_study_custom': ClinicalStudyCustomTransformer
        }
        
        transformers = list(SchemaRegistry._transformers.keys())
        logger.debug(f"Registered transformers manually: {transformers}")
    
    return {
        "transformers": transformers,
        "manually_registered": not transformers
    }