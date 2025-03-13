from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import uvicorn
import logging
import os
from starlette.middleware.sessions import SessionMiddleware
from routes.auth import generate_csrf_token, csrf_protect
from sqlalchemy.orm import Session
from database import get_db, init_db
import secrets

# Configure logging first thing
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Custom OpenAPI to add security schemes
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    # Generate OpenAPI schema
    openapi_schema = get_openapi(
        title="Devsearch API",
        version="1.0.0",
        description="""
        A search service API providing advanced multi-index search capabilities 
        with robust collection management and search management.

        ***  Search across ***:
        - Clinical Studies (status, phase, categories)
        - Scientific Papers
        - Data Domains
        
        ## Authentication
        This API supports two authentication methods:
        
        1. **Bearer Token** - For programmatic API access:
           ```
           Authorization: Bearer your_token_here
           ```
           
        2. **OAuth2** - For web-based authentication flows
        """,
        routes=app.routes,
    )
    
    # Remove static files path from paths
    if "/static" in openapi_schema.get("paths", {}):
        del openapi_schema["paths"]["/static"]
    
    # Initialize components if it doesn't exist
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "/auth/login",
                    "tokenUrl": "/api/auth/token",
                    "scopes": {
                        "openid": "OpenID Connect",
                        "profile": "User profile",
                        "email": "User email"
                    }
                }
            }
        },
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    # Make sure schemas are included in components
    if "schemas" not in openapi_schema["components"]:
        openapi_schema["components"]["schemas"] = {}
    
    # Define tag ordering and descriptions
    openapi_schema["tags"] = [
        {
            "name": "Search",
            "description": "Endpoints for searching across different medical data collections"
        },
        {
            "name": "History",
            "description": "Endpoints for managing search history"
        },
        {
            "name": "Saved Searches",
            "description": "Endpoints for managing saved searches"
        },
        {
            "name": "Collections",
            "description": "Endpoints for managing collections of items"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Import router modules
from routes.search import router as search_router
from routes.auth import router as auth_router

try:
    from routes.history import router as history_router
except Exception as e:
    logger.error(f"Failed to import history_router: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")
    history_router = None

try:
    from routes.saved_searches import router as saved_searches_router
except Exception as e:
    logger.error(f"Failed to import saved_searches_router: {e}")
    saved_searches_router = None

app = FastAPI(
    title="Devsearch API",
    description="""
    A search service API providing advanced multi-index search capabilities 
    with robust collection management and search management.

    ## Features
    *Search across:
      - Clinical Studies (status, phase, categories)
      - Scientific Papers
      - Data Domains
    """,
    docs_url=None,  # Disable default docs URL
    redoc_url=None,  # Disable default redoc URL
    openapi_url="/api/openapi.json"  # Specify the OpenAPI schema URL
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup session middleware with a strong secret key
session_secret = os.environ.get("SESSION_SECRET", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=session_secret, max_age=3600)

# Register routers
app.include_router(search_router, prefix="/api", tags=["Search"])
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

if history_router:
    app.include_router(history_router, prefix="/api", tags=["History"])

if saved_searches_router:
    app.include_router(saved_searches_router, prefix="/api", tags=["Saved Searches"])

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Custom OpenAPI schema
app.openapi = custom_openapi

# Custom handlers for root, login page, and API docs
@app.get("/", include_in_schema=False)
async def redirect_to_login():
    return RedirectResponse(url="/api/auth/login")

@app.get("/api/auth/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    # Generate CSRF token and store in session
    csrf_token = generate_csrf_token(request)
    
    return templates.TemplateResponse(
        "auth/login.html", 
        {
            "request": request, 
            "csrf_token": csrf_token,
            "current_year": datetime.now().year
        }
    )

@app.get("/api/docs", response_class=HTMLResponse, include_in_schema=False)
async def custom_swagger_ui_html(request: Request):
    """Custom Swagger UI implementation"""
    csrf_token = generate_csrf_token(request)
    
    # Check for authenticated user and get token
    jwt_token = None
    is_authenticated = False
    
    # Get token from cookie if present
    if "token" in request.cookies:
        jwt_token = request.cookies.get("token")
        logger.debug("Found JWT token in cookie")
        is_authenticated = True
    
    # If no cookie token, check for user in session
    if not is_authenticated:
        try:
            from routes.auth import get_current_user_for_template
            current_user = await get_current_user_for_template(request)
            if current_user and current_user.is_authenticated:
                is_authenticated = True
                # If user is authenticated but we don't have a token, try to get it
                if not jwt_token and "token" in request.cookies:
                    jwt_token = request.cookies.get("token")
            else:
                # Not authenticated - redirect to login
                logger.debug("User not authenticated, redirecting to login")
                return RedirectResponse(url="/api/auth/login?next=/api/docs")
        except Exception as e:
            logger.error(f"Error checking authentication: {e}")
            # Redirect to login on error
            return RedirectResponse(url="/api/auth/login?next=/api/docs")
    
    return templates.TemplateResponse(
        "swagger.html", 
        {
            "request": request,
            "openapi_url": app.openapi_url,
            "title": app.title,
            "swagger_js_url": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            "swagger_css_url": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            "csrf_token": csrf_token,
            "jwt_token": jwt_token
        }
    )

@app.get("/api/redoc", response_class=HTMLResponse, include_in_schema=False)
async def redoc_html(request: Request):
    """Custom ReDoc implementation"""
    csrf_token = generate_csrf_token(request)

    # Check for authenticated user and get token
    jwt_token = None
    is_authenticated = False
    
    # Get token from cookie if present
    if "token" in request.cookies:
        jwt_token = request.cookies.get("token")
        logger.debug("Found JWT token in cookie")
        is_authenticated = True
    
    # If no cookie token, check for user in session
    if not is_authenticated:
        try:
            from routes.auth import get_current_user_for_template
            current_user = await get_current_user_for_template(request)
            if current_user and current_user.is_authenticated:
                is_authenticated = True
                # If user is authenticated but we don't have a token, try to get it
                if not jwt_token and "token" in request.cookies:
                    jwt_token = request.cookies.get("token")
            else:
                # Not authenticated - redirect to login
                logger.debug("User not authenticated, redirecting to login")
                return RedirectResponse(url="/api/auth/login?next=/api/redoc")
        except Exception as e:
            logger.error(f"Error checking authentication: {e}")
            # Redirect to login on error
            return RedirectResponse(url="/api/auth/login?next=/api/redoc")
    
    return templates.TemplateResponse(
        "redoc.html", 
        {
            "request": request,
            "openapi_url": app.openapi_url,
            "title": app.title,
            "redoc_js_url": "https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
            "csrf_token": csrf_token,
            "jwt_token": jwt_token
        }
    )

@app.get("/api/health", include_in_schema=False)
async def health_check():
    """Simple health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    try:
        # Initialize database
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

@app.get("/api/debug/routes", include_in_schema=False)
async def debug_routes():
    """Debug endpoint to list all routes"""
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "name": route.name,
            "methods": route.methods if hasattr(route, "methods") else None,
            "endpoint": route.endpoint.__name__ if hasattr(route, "endpoint") else None
        })
    return {"routes": routes}

if __name__ == "__main__":
    # Run the application with uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)