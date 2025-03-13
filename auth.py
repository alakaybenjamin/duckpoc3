import os
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.security import OAuth2AuthorizationCodeBearer
from starlette.middleware.sessions import SessionMiddleware
import requests
from oauthlib.oauth2 import WebApplicationClient
import logging
from database import get_db
from models.database_models import User
import functools
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

auth = APIRouter()

# OAuth 2.0 configuration
OAUTH_ISSUER = os.environ.get("OAUTH_ISSUER")
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET")
OAUTH_DISCOVERY_URL = f"{OAUTH_ISSUER}/.well-known/openid-configuration"

# Determine if we're running locally or in production
BASE_URL = "https://workspace.alexbenjamin198.repl.co"
CALLBACK_PATH = "/auth/callback"
REDIRECT_URI = f"{BASE_URL}{CALLBACK_PATH}"

logger.info(f"OAuth Configuration:")
logger.info(f"  OAUTH_ISSUER: {OAUTH_ISSUER}")
logger.info(f"  REDIRECT_URI: {REDIRECT_URI}")

def setup_oauth(app):
    """Setup OAuth client and discovery"""
    # Setup will be implemented here

async def get_current_user_for_template(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get current user for template rendering"""
    user_info = {
        "is_authenticated": False,
        "username": None,
        "email": None,
        "id": None
    }
    
    try:
        if "user_id" in request.session:
            user_id = request.session["user_id"]
            user = db.query(User).get(int(user_id))
            if user:
                user_info["is_authenticated"] = True
                user_info["username"] = user.username
                user_info["email"] = user.email
                user_info["id"] = user.id
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
    
    return user_info

def require_auth(func):
    """Decorator to require authentication for a route"""
    @functools.wraps(func)
    async def wrapper(request: Request, db: Session = Depends(get_db), *args, **kwargs):
        """Wrapper function to check authentication"""
        user_info = await get_current_user_for_template(request, db)
        
        if not user_info["is_authenticated"]:
            # If AJAX request, return 401
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                raise HTTPException(status_code=401, detail="Authentication required")
            
            # Otherwise redirect to login page
            return RedirectResponse(url="/auth/login")
        
        # Inject the user into kwargs
        kwargs["current_user"] = user_info
        return await func(request, *args, **kwargs)
    
    return wrapper

async def csrf_protect(request: Request):
    """CSRF protection middleware"""
    # Implementation follows
    return True

@auth.get("/login")
async def login(request: Request):
    """Login route"""
    # Implementation will go here
    pass

@auth.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    """OAuth callback handler"""
    try:
        # Get the authorization code from the callback
        code = request.query_params.get("code")
        if not code:
            logger.error("No code in callback params")
            raise HTTPException(status_code=400, detail="No authorization code received")
            
        # Exchange code for tokens using the client
        # More implementation will follow
        
        # For example, create or update user
        # Assuming you have user info from the token
        userinfo = {"email": "example@example.com"}  # Placeholder
        
        user = db.query(User).filter_by(email=userinfo["email"]).first()
        if not user:
            # Create new user
            user = User(
                email=userinfo["email"],
                username=userinfo.get("preferred_username", userinfo["email"].split("@")[0])
            )
            db.add(user)
            db.commit()
        
        # Set user in session
        request.session["user_id"] = user.id
        
        # Redirect to main page
        return RedirectResponse(url="/")
        
    except Exception as e:
        logger.error(f"Error in callback: {e}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

@auth.get("/logout")
async def logout(request: Request):
    """Logout route"""
    request.session.clear()
    return RedirectResponse(url="/")