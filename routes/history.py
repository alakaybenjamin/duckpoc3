import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import sys
import os
from datetime import datetime
from pydantic import BaseModel, Field
import jwt
from sqlalchemy import func

# Add the parent directory to sys.path to allow imports from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from routes import auth
from security import decode_access_token
from models.database_models import User, SearchHistory

# Configure logging
logger = logging.getLogger(__name__)

# Define models
class HistoryEntryBase(BaseModel):
    query: str
    category: str = None
    filters: Dict[str, Any] = None
    results_count: int = 0
    name: Optional[str] = None  # Optional name for saved searches
    
class HistoryEntry(HistoryEntryBase):
    id: int
    results_count: int = 0
    created_at: datetime
    is_saved: bool = False
    last_used: datetime
    use_count: int = 0
    
    class Config:
        from_attributes = True

class HistoryResponse(BaseModel):
    success: bool
    message: str
    id: Optional[int] = None  # Optional ID field for returning the search history ID

class PaginatedHistoryResponse(BaseModel):
    items: List[Dict[str, Any]]
    pagination: Dict[str, Any]

# Create router
router = APIRouter()

async def get_user_id_from_request(request: Request, db: Session):
    """
    Get the user ID from the request (either from session or token)
    """
    try:
        # First check for session-based authentication
        if "user_id" in request.session:
            logger.debug(f"Found user_id in session: {request.session['user_id']}")
            return request.session["user_id"]
        
        # Then check for token-based authentication
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            logger.debug(f"Found Bearer token in Authorization header")
            
            # Decode the token
            payload = decode_access_token(token)
            if payload and "sub" in payload:
                email = payload["sub"]
                logger.debug(f"Looking up user with email: {email}")
                user = db.query(User).filter(User.email == email).first()
                if user:
                    logger.debug(f"Found user with ID: {user.id}")
                    return user.id
        
        # If we get here, no valid authentication was found
        logger.warning("No valid authentication found in request")
        return None
    
    except Exception as e:
        logger.error(f"Error in get_user_id_from_request: {e}")
        return None

# Define endpoints
@router.get("/search-history", 
    response_model=PaginatedHistoryResponse,
    summary="Get search history",
    description="""
    Retrieve the search history for the authenticated user.
    
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
async def get_search_history(
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
        
        # Count total entries
        total_count = db.query(func.count(SearchHistory.id))\
            .filter(SearchHistory.user_id == user_id)\
            .scalar()
        
        # Query with pagination
        history_entries = db.query(SearchHistory)\
            .filter(SearchHistory.user_id == user_id)\
            .order_by(SearchHistory.created_at.desc())\
            .offset(offset)\
            .limit(per_page)\
            .all()
        
        # Convert to response format
        items = []
        for entry in history_entries:
            items.append({
                "id": entry.id,
                "query": entry.query,
                "category": entry.category,
                "filters": entry.filters,
                "results_count": entry.results_count,
                "created_at": entry.created_at.isoformat(),
                "is_saved": entry.is_saved,
                "last_used": entry.last_used.isoformat(),
                "use_count": entry.use_count,
                "name": entry.name
            })
        
        # Create pagination info
        pagination = {
            "page": page,
            "per_page": per_page,
            "total": total_count,
            "pages": (total_count + per_page - 1) // per_page if per_page > 0 else 0
        }
        
        return {
            "items": items,
            "pagination": pagination
        }
    
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        logger.error(f"Error retrieving search history: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving search history: {str(e)}")

@router.post("/search-history", 
    response_model=HistoryResponse,
    summary="Save search to history",
    description="""
    Save a search query to the user's search history.
    
    ## Authentication
    This endpoint requires authentication via Bearer token or session cookie.
    """
)
async def save_search(
    request: Request,
    search_data: HistoryEntryBase = Body(
        ...,
        description="Search data to save",
        example={
            "query": "cancer",
            "category": "clinical_study",
            "filters": {"status": "Recruiting"},
            "results_count": 42,  # Add this to the example
            "name": "My cancer research"  # Example of a search name
        }
    ),
    db: Session = Depends(get_db)
):
    """
    Save a search query to the user's search history.

    ## Authentication
    This endpoint requires authentication. You can provide authentication in one of these ways:
    
    1. **Bearer Token** - Include an Authorization header with a JWT token
    2. **Cookie Authentication** - If you're logged in through the browser interface
    """
    try:
        # Get current user authentication status
        current_user = await auth.get_current_user_for_template(request)
        
        if not current_user.is_authenticated:
            logger.warning("User not authenticated properly")
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        
        # Get user ID using our helper function
        user_id = await get_user_id_from_request(request, db)
        
        if not user_id:
            logger.warning("User ID not found in session or token")
            raise HTTPException(
                status_code=401,
                detail="Authentication required - unable to determine user ID"
            )
        
        # Create a new search history entry
        search_history = SearchHistory(
            user_id=user_id,
            query=search_data.query,
            category=search_data.category,
            filters=search_data.filters,
            results_count=search_data.results_count,  # Use the value from search_data
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            use_count=1,
            name=search_data.name  # Use the name if provided
        )
        
        # Add and commit to the database
        db.add(search_history)
        db.commit()
        
        return {"success": True, "message": "Search saved to history successfully", "id": search_history.id}
    except Exception as e:
        logger.error(f"Failed to save search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save search: {str(e)}"
        )

@router.post("/search-history/add-test-entry", 
    response_model=HistoryResponse,
    summary="Add a test search to history",
    description="For testing only: Adds a test search entry to the currently authenticated user's history",
    include_in_schema=False
)
async def add_test_entry(request: Request, db: Session = Depends(get_db)):
    """
    Add a test search history entry for the current user
    """
    try:
        # Get current user authentication status
        current_user = await auth.get_current_user_for_template(request)
        
        if not current_user.is_authenticated:
            logger.warning("User not authenticated properly")
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        
        # Get user ID using our helper function
        user_id = await get_user_id_from_request(request, db)
        
        if not user_id:
            logger.warning("User ID not found in session or token")
            raise HTTPException(
                status_code=401,
                detail="Authentication required - unable to determine user ID"
            )
        
        # Create a test search history entry
        test_entry = SearchHistory(
            user_id=user_id,
            query="test search query",
            category="clinical_study",
            filters={"status": "Active"},
            results_count=42,
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            use_count=1
        )
        
        # Add and commit to the database
        db.add(test_entry)
        db.commit()
        
        return {"success": True, "message": "Test search entry added to history successfully"}
    except Exception as e:
        logger.error(f"Failed to add test search entry: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add test search entry: {str(e)}"
        )