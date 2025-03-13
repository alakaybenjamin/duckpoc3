import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Body, BackgroundTasks, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys
import os
from pydantic import BaseModel, Field
import httpx
from sqlalchemy import func

# Add the parent directory to sys.path to allow imports from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models.database_models import SearchHistory
from services.auth import get_current_user
from routes.history import get_user_id_from_request, HistoryEntryBase

# Configure logging
logger = logging.getLogger(__name__)

# Define models
class SavedSearchResponse(BaseModel):
    id: int
    query: str
    category: str = None
    filters: Dict[str, Any] = None
    results_count: int = 0
    created_at: datetime
    is_saved: bool = True
    last_used: datetime
    use_count: int = 0
    name: Optional[str] = None
    
    class Config:
        from_attributes = True

class SearchActionResponse(BaseModel):
    success: bool
    message: str

class SaveSearchRequest(BaseModel):
    search_id: int
    name: Optional[str] = None

class PaginatedSavedSearchResponse(BaseModel):
    items: List[SavedSearchResponse]
    pagination: Dict[str, Any]

# Create router
router = APIRouter()

# Define endpoints
@router.get("/saved-searches", 
    response_model=PaginatedSavedSearchResponse,
    summary="Get saved searches",
    description="""
    Retrieve all saved searches for the authenticated user.
    
    ## Authentication
    This endpoint requires authentication. You can provide authentication using:
    
    1. **Bearer Token** - Include an Authorization header with a JWT token:
       `Authorization: Bearer your_token_here`
       
    2. **Cookie Authentication** - If you're logged in through the browser interface.
    
    ## Pagination
    - page: Page number (starts from 1)
    - per_page: Number of items per page (default: 10, max: 100)
    """
)
async def get_saved_searches(
    request: Request, 
    page: int = Query(1, ge=1, description="Page number"), 
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    try:
        # Get user ID from request
        user_id = await get_user_id_from_request(request, db)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Calculate offset for pagination
        offset = (page - 1) * per_page
        
        # Count total saved searches
        total_count = db.query(func.count(SearchHistory.id))\
            .filter(SearchHistory.user_id == user_id, SearchHistory.is_saved == True)\
            .scalar()
        
        # Query saved searches with pagination
        saved_searches = db.query(SearchHistory)\
            .filter(SearchHistory.user_id == user_id, SearchHistory.is_saved == True)\
            .order_by(SearchHistory.last_used.desc())\
            .offset(offset)\
            .limit(per_page)\
            .all()
        
        # Create pagination info
        pagination = {
            "page": page,
            "per_page": per_page,
            "total": total_count,
            "pages": (total_count + per_page - 1) // per_page if per_page > 0 else 0
        }
        
        return {
            "items": saved_searches,
            "pagination": pagination
        }
    
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        logger.error(f"Error retrieving saved searches: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving saved searches: {str(e)}")

@router.post("/saved-searches/{search_id}/execute", 
    response_model=Dict[str, Any],
    summary="Execute a saved search",
    description="""
    Execute a previously saved search by its ID and return the search results.
    
    ## Authentication
    This endpoint requires authentication via Bearer token or session cookie.
    """
)
async def execute_saved_search(search_id: int, request: Request, db: Session = Depends(get_db)):
    """Execute a saved search"""
    try:
        # Get user ID
        user_id = await get_user_id_from_request(request, db)
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication required - unable to determine user ID"
            )
        
        # Retrieve the saved search
        saved_search = db.query(SearchHistory).filter(
            SearchHistory.id == search_id,
            SearchHistory.user_id == user_id,
            SearchHistory.is_saved == True
        ).first()
        
        if not saved_search:
            raise HTTPException(
                status_code=404,
                detail="Saved search not found"
            )
        
        # Update the search usage counter and last_used timestamp
        saved_search.use_count += 1
        saved_search.last_used = datetime.utcnow()
        db.commit()
        
        # Prepare the search request to forward to the search endpoint
        search_params = {
            "query": saved_search.query,
            "collection_type": saved_search.category or "clinical_study",
            "schema_type": "default",
            "page": 1,
            "per_page": 10,
            "filters": saved_search.filters or {}
        }
        
        # Gather authentication information from the request
        headers = {}
        token = None
        
        # Check for authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            headers["Authorization"] = auth_header
        
        # Check for CSRF token if needed
        csrf_token = request.headers.get("X-CSRF-Token")
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token
        
        # For simplicity, we'll use the internal FastAPI app structure to call the search endpoint
        # In a real implementation, we would use dependency injection to get the search service
        # and call it directly
        
        # Construct the base URL
        base_url = str(request.base_url)
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        
        search_url = f"{base_url}/api/search"
        
        # Use httpx to make an internal request to the search endpoint
        try:
            async with httpx.AsyncClient() as client:
                # Forward the request with all the necessary authentication headers
                response = await client.post(
                    search_url,
                    json=search_params,
                    headers=headers,
                    cookies=request.cookies
                )
                
                # Check if the search was successful
                if response.status_code == 200:
                    search_results = response.json()
                    
                    # Update results count in the search history
                    if isinstance(search_results, dict) and 'pagination' in search_results:
                        saved_search.results_count = search_results['pagination'].get('total', 0)
                        db.commit()
                    
                    return search_results
                else:
                    # Return the error from the search endpoint
                    return JSONResponse(
                        status_code=response.status_code,
                        content=response.json()
                    )
        except Exception as e:
            logger.error(f"Error calling search endpoint: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error executing search: {str(e)}"
            )
    except Exception as e:
        logger.error(f"Failed to execute saved search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute saved search: {str(e)}"
        )

@router.post("/search-history/save", 
    response_model=SearchActionResponse,
    summary="Save a search from history with body parameters",
    description="""
    Save a search from the user's search history using search_id and name in the request body.
    
    ## Authentication
    This endpoint requires authentication via Bearer token or session cookie.
    
    """
)
async def save_search_with_body(
    request: Request,
    save_data: SaveSearchRequest = Body(
        ...,
        description="Search data to save",
        example={
            "search_id": 34,
            "name": "my cancer search"
        }
    ),
    db: Session = Depends(get_db)
):
    """Save a search from history using body parameters"""
    try:
        # Get user ID
        user_id = await get_user_id_from_request(request, db)
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication required - unable to determine user ID"
            )
        
        # Find the search in history
        search_entry = db.query(SearchHistory).filter(
            SearchHistory.id == save_data.search_id,
            SearchHistory.user_id == user_id
        ).first()
        
        if not search_entry:
            raise HTTPException(
                status_code=404,
                detail="Search history entry not found"
            )
        
        # Update the is_saved flag and name if provided
        search_entry.is_saved = True
        if save_data.name:
            search_entry.name = save_data.name
        db.commit()
        
        return {"success": True, "message": "Search saved successfully"}
    except Exception as e:
        logger.error(f"Failed to save search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save search: {str(e)}"
        )

@router.delete("/saved-searches/{search_id}", 
    response_model=SearchActionResponse,
    summary="Delete a saved search",
    description="""
    Delete a saved search by its ID.
    
    ## Authentication
    This endpoint requires authentication via Bearer token or session cookie.
    """
)
async def delete_saved_search(search_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a saved search"""
    try:
        # Get user ID
        user_id = await get_user_id_from_request(request, db)
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication required - unable to determine user ID"
            )
        
        # Find the saved search
        saved_search = db.query(SearchHistory).filter(
            SearchHistory.id == search_id,
            SearchHistory.user_id == user_id,
            SearchHistory.is_saved == True
        ).first()
        
        if not saved_search:
            raise HTTPException(
                status_code=404,
                detail="Saved search not found"
            )
        
        # Option 1: Set is_saved to False (keeps the search in history but not as saved)
        saved_search.is_saved = False
        db.commit()
        
        # Option 2: Completely delete the entry from the database
        # db.delete(saved_search)
        # db.commit()
        
        return {"success": True, "message": "Saved search deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete saved search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete saved search: {str(e)}"
        )