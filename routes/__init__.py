try:
    from .auth import router as auth_router
    from .search import router as search_router
    from .collections import router as collections_router
    from .saved_searches import router as saved_searches_router
    from .history import router as history_router

    __all__ = ['auth_router', 'search_router', 'collections_router', 'saved_searches_router', 'history_router']
except Exception as e:
    import logging
    logging.error(f"Error importing routers: {str(e)}")
    # Still expose the names but set them to None to avoid breaking imports
    auth_router = None
    search_router = None
    collections_router = None
    saved_searches_router = None
    history_router = None
    __all__ = ['auth_router', 'search_router', 'collections_router', 'saved_searches_router', 'history_router']