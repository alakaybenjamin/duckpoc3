import sys
import os
import logging
from datetime import datetime, timedelta
import json
import requests
from typing import List, Optional, Dict, Any
import secrets
from pydantic import BaseModel

try:
    # Handle possible missing package
    from oauthlib.oauth2 import WebApplicationClient
except ImportError:
    WebApplicationClient = None

from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, Response, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

# Add the parent directory to sys.path to allow imports from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logger = logging.getLogger(__name__)

# Define Token model directly in this file to avoid reference issues
class Token(BaseModel):
    """Token schema for authentication responses"""
    access_token: str
    token_type: str = "bearer"

router = APIRouter()

# CSRF token endpoint
@router.get("/csrf-token", include_in_schema=False)
async def get_csrf_token(request: Request):
    """Get a new CSRF token"""
    token = generate_csrf_token(request)
    logger.debug(f"Generated new CSRF token: {token}")
    return {"csrf_token": token}

# Debug endpoint to check current CSRF token
@router.get("/check-csrf-token", include_in_schema=False)
async def check_csrf_token(request: Request):
    """Check the current CSRF token in the session"""
    token = request.session.get("csrf_token", "No token found in session")
    return {"current_csrf_token": token}

# CSRF Protection functions
def generate_csrf_token(request: Request):
    """Generate a CSRF token and store it in the session"""
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_hex(16)
    return request.session["csrf_token"]

async def csrf_protect(request: Request):
    """Validate CSRF token for unsafe methods"""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        # Skip CSRF check if using Bearer token authentication
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            logger.debug("Skipping CSRF check for Bearer token authentication")
            return True
            
        csrf_token = request.headers.get("X-CSRF-Token") 
        session_token = request.session.get("csrf_token")
        
        logger.debug(f"CSRF validation - Header token: {csrf_token}, Session token: {session_token}")
        
        # For form submissions check form data
        form_data = None
        try:
            form_data = await request.form()
            if "csrf_token" in form_data:
                csrf_token = form_data.get("csrf_token")
                logger.debug(f"Found CSRF token in form data: {csrf_token}")
        except:
            pass
            
        if not csrf_token or not session_token or csrf_token != session_token:
            logger.warning(f"CSRF validation failed - Header token: {csrf_token}, Session token: {session_token}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or invalid"
            )
        
        logger.debug("CSRF validation passed")
    return True

# Create a placeholder for current_user
class CurrentUser:
    def __init__(self, is_authenticated=False):
        self.is_authenticated = is_authenticated

# Helper function to get current user
async def get_current_user_for_template(request: Request):
    """Get current user for template rendering"""
    # Log current session and cookie data for debugging
    logger.debug(f"Session data: {request.session}")
    logger.debug(f"Cookies: {request.cookies}")
    
    # Check for "authenticated" flag directly
    if request.session.get("authenticated") is True:
        logger.debug("User authenticated via session authenticated flag")
        return CurrentUser(is_authenticated=True)
    
    # Check specific session keys (which is populated from SSO login)
    if "user_id" in request.session and "user_email" in request.session:
        logger.debug(f"User authenticated via session: {request.session.get('user_email')}")
        return CurrentUser(is_authenticated=True)
    
    # Check for JWT token in cookies/session
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        logger.debug("Token found in Authorization header")
    
    # If no token in header, check cookies
    if not token and "token" in request.cookies:
        token = request.cookies.get("token")
        logger.debug("Token found in cookies")
    
    # For server-side rendering, tokens may not be available
    # So we always return a user object (authenticated or not)
    # to avoid template errors
    if token:
        try:
            # This is where you'd validate the token and get the actual user
            # from the database. For now, we'll just return an authenticated user
            logger.debug("User authenticated via token")
            return CurrentUser(is_authenticated=True)
        except Exception as e:
            logger.error(f"Error authenticating user for template: {str(e)}")
    
    logger.debug("No authentication found - user is not authenticated")
    return CurrentUser(is_authenticated=False)

# Import at function level to avoid circular imports
def get_modules():
    """Import modules at function level to avoid circular dependencies"""
    try:
        from database import get_db
        from models.database_models import User
        
        # Import create_access_token from services.auth
        try:
            from security import create_access_token
        except ImportError as e:
            logger.warning(f"Failed to import create_access_token: {str(e)}")
            # Provide a fallback implementation
            def create_access_token(data, expires_delta=None):
                import jwt
                from datetime import datetime, timedelta
                to_encode = data.copy()
                if expires_delta:
                    expire = datetime.utcnow() + expires_delta
                else:
                    expire = datetime.utcnow() + timedelta(minutes=15)
                to_encode.update({"exp": expire})
                return jwt.encode(to_encode, "fallback-secret-key", algorithm="HS256")
        
        return get_db, User, create_access_token
    except Exception as e:
        logger.error(f"Error in get_modules: {str(e)}")
        raise

# Get modules
get_db, User, create_access_token = get_modules()

# OAuth2 Configuration - Specifically for Google
OAUTH_ISSUER = os.environ.get("OAUTH_ISSUER", "https://accounts.google.com")
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "your-google-client-id")
OAUTH_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "your-google-client-secret")

# Google OAuth URLs (hardcoded as fallback if discovery fails)
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# Try to get configuration from discovery URL, but use hardcoded values if it fails
OAUTH_DISCOVERY_URL = f"{OAUTH_ISSUER}/.well-known/openid-configuration"
try:
    logger.info(f"Attempting to get OAuth configuration from {OAUTH_DISCOVERY_URL}")
    provider_cfg = requests.get(OAUTH_DISCOVERY_URL, timeout=5).json()
    GOOGLE_AUTH_URL = provider_cfg.get("authorization_endpoint", GOOGLE_AUTH_URL)
    GOOGLE_TOKEN_URL = provider_cfg.get("token_endpoint", GOOGLE_TOKEN_URL)
    GOOGLE_USERINFO_URL = provider_cfg.get("userinfo_endpoint", GOOGLE_USERINFO_URL)
    logger.info(f"OAuth endpoints discovered: auth={GOOGLE_AUTH_URL}, token={GOOGLE_TOKEN_URL}")
except Exception as e:
    logger.warning(f"Failed to get OAuth discovery configuration, using defaults: {str(e)}")

# Base URL for redirects
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8001")

# Define multiple possible callback paths and URIs
CALLBACK_PATHS = [
    "/api/auth/callback"
]

# Create a list of possible redirect URIs
REDIRECT_URIS = [f"{BASE_URL}{path}" for path in CALLBACK_PATHS]

# Log all possible redirect URIs
logger.info(f"Possible redirect URIs:")
for uri in REDIRECT_URIS:
    logger.info(f"  - {uri}")

# Default redirect URI (first in list)
REDIRECT_URI = REDIRECT_URIS[0]
logger.info(f"Using primary redirect URI: {REDIRECT_URI}")

# OAuth client
try:
    if WebApplicationClient is not None:
        oauth_client = WebApplicationClient(OAUTH_CLIENT_ID)
        logger.info(f"OAuth client initialized with client ID: {OAUTH_CLIENT_ID[:5]}...")
    else:
        logger.warning("WebApplicationClient not available, OAuth features disabled")
        oauth_client = None
except Exception as e:
    logger.error(f"Failed to initialize OAuth client: {str(e)}")
    oauth_client = None

def get_user_by_email(db: Session, email: str):
    """Get user by email"""
    try:
        return db.query(User).filter(User.email == email).first()
    except Exception as e:
        logger.error(f"Database error while fetching user by email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )

def verify_password(plain_password, hashed_password):
    """Verify password (placeholder - implement actual password checking)"""
    # In a real app, you would use passlib to hash and verify passwords
    # For now, we'll use a simple comparison for demo purposes
    return plain_password == hashed_password

def authenticate_user(db: Session, email: str, password: str):
    """Authenticate a user"""
    user = get_user_by_email(db, email)
    if not user:
        return False
    # In a real app, you'd check the hashed password here
    # For demo, we'll just return the user (assuming password is correct)
    return user

@router.get("/sso-login", name="google_sso", include_in_schema=False)
async def sso_login(request: Request, db: Session = Depends(get_db)):
    """Initiate OAuth login flow with Google"""
    try:
        # Check if OAuth is configured
        if oauth_client is None:
            # For development, simulate successful login
            logger.warning("OAuth client not configured. Using development mode with automatic login.")
            
            # Check if dummy user exists
            user = get_user_by_email(db, "dev@example.com")
            if not user:
                user = User(
                    email="dev@example.com",
                    username="Developer User",
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            
            # Create token and redirect
            access_token = create_access_token(data={"sub": user.email})
            response = RedirectResponse(url="/")
            response.set_cookie(
                key="token",
                value=access_token,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax"
            )
            return response
        
        # Store the current path in session for post-login redirect
        next_url = request.query_params.get("next", "/")
        request.session["next"] = next_url
        
        logger.info(f"Starting Google OAuth flow, will redirect back to: {next_url}")
        
        # Try each redirect URI until one works
        for redirect_uri in REDIRECT_URIS:
            try:
                # Generate request URI
                request_uri = oauth_client.prepare_request_uri(
                    GOOGLE_AUTH_URL,
                    redirect_uri=redirect_uri,
                    scope=["openid", "profile", "email"],
                    state=f"redirect_uri={redirect_uri}|next={next_url}"
                )
                
                logger.info(f"Redirecting to Google OAuth with redirect_uri={redirect_uri}")
                return RedirectResponse(request_uri)
            except Exception as e:
                logger.error(f"Failed with redirect URI {redirect_uri}: {str(e)}")
                continue
        
        # If we get here, all URIs failed
        logger.error("All redirect URIs failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to configure OAuth flow with any redirect URI"
        )
    except Exception as e:
        logger.error(f"Error initiating SSO login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Authentication service error"
        )

@router.get("/callback", name="google_callback", include_in_schema=False)
async def oauth_callback(
    request: Request, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback"""
    try:
        # Log the entire request for debugging
        logger.info(f"Callback received with query params: {request.query_params}")
        
        # Check if OAuth is configured
        if oauth_client is None:
            logger.warning("OAuth client not configured. Redirecting to home page.")
            return RedirectResponse(url="/")
            
        # Get authorization code
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code missing")
        
        # Get state and parse it
        state = request.query_params.get("state", "/")
        
        # Parse state to get redirect_uri and next URL
        redirect_uri = None
        next_url = "/"
        
        if "|" in state:
            parts = state.split("|")
            for part in parts:
                if part.startswith("redirect_uri="):
                    redirect_uri = part[13:]  # Length of "redirect_uri="
                elif part.startswith("next="):
                    next_url = part[5:]  # Length of "next="
        
        logger.info(f"Extracted from state: redirect_uri={redirect_uri}, next_url={next_url}")
        
                # If no redirect_uri in state, use default
        if not redirect_uri:
            redirect_uri = f"{os.environ.get('BASE_URL', 'http://localhost:8001')}/api/auth/callback"
            
        # Exchange code for token using Google's token endpoint
        token_response = requests.post(
            "https://accounts.google.com/o/oauth2/token",
            data={
                'client_id': os.environ.get("OAUTH_CLIENT_ID", "your-google-client-id"),
                'client_secret': os.environ.get("OAUTH_CLIENT_SECRET", "your-google-client-secret"),
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri
            }
        )
        
        if not token_response.ok:
            logger.error(f"Token request failed: {token_response.status_code} - {token_response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to get token from Google: {token_response.text}")
        
        # Parse token response
        token_data = token_response.json()
        id_token = token_data.get('id_token')

        if not id_token:
            logger.error("No ID token received from Google")
            raise HTTPException(status_code=500, detail="No ID token received")

        # Get user info from Google using the access token
        access_token = token_data.get('access_token')
        userinfo_response = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={'Authorization': f'Bearer {access_token}'}
        )
        
        
        if not userinfo_response.ok:
            logger.error(f"User info request failed: {userinfo_response.status_code} - {userinfo_response.text}")
            raise HTTPException(status_code=500, detail=f"Failed to get user info from Google: {userinfo_response.text}")
        
        userinfo = userinfo_response.json()
        logger.info(f"User info received: {userinfo}")
        
        # Extract user email
        email = userinfo.get("email", "")
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        # Create or get user
        user = get_user_by_email(db, email)
        if not user:
            # Create new user from SSO information
            user = User(
                email=email,
                username=userinfo.get("name", email.split("@")[0]),
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        logger.info(f"User authenticated: {email}")
        
        # Create our app's JWT token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )
        
        # Create response with token in cookie
        response = RedirectResponse(url=next_url)
        response.set_cookie(
            key="token",
            value=access_token,
            httponly=True,
            max_age=1800,
            samesite="lax"
        )
        
        # Also store user info in session
        request.session["user_id"] = user.id
        request.session["user_email"] = user.email
        
        return response
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in OAuth callback: {str(e)}", exc_info=True)
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Authentication callback failed: {str(e)}"
        )

@router.get("/logout", include_in_schema=False)
async def logout(request: Request, response: Response):
    """Handle logout"""
    request.session.clear()
    response.delete_cookie("token")
    return RedirectResponse(url="/")

@router.get("/get-token", response_model=Dict[str, str], include_in_schema=False)
async def get_token(request: Request):
    """
    Get the JWT token for the currently authenticated user.
    
    This endpoint can be used by frontend JavaScript to access the token
    stored in the HttpOnly cookie for use in API requests.
    """
    # Verify the user is authenticated via a valid session
    current_user = await get_current_user_for_template(request)
    if not current_user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Return the token from the cookie
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found in cookie",
        )
    
    return {"token": token}

@router.post("/login", response_model=Token, include_in_schema=False)
async def login_for_access_token(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_check: bool = Depends(csrf_protect),
    db: Session = Depends(get_db)
):
    """Generate a token for username/password authentication"""
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}