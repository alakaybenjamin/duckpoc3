"""
Collections routes module
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
import sys
import os
import logging

# Add the parent directory to sys.path to allow imports from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.get("/collections/list", include_in_schema=False)
async def get_user_collections():
    """Simple test endpoint for collections"""
    return JSONResponse(content={"message": "Collections endpoint working", "collections": []})

@router.post("/collections", include_in_schema=False)
async def create_collection():
    """Simple test endpoint for creating a collection"""
    return JSONResponse(content={"message": "Create collection endpoint working", "id": 1})

@router.post("/collections/{collection_id}/items", include_in_schema=False)
async def add_to_collection(collection_id: int):
    """Simple test endpoint for adding to a collection"""
    return JSONResponse(content={"message": f"Add to collection {collection_id} endpoint working"})