from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging
from typing import Generator

logger = logging.getLogger(__name__)

# Use PostgreSQL local database
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/biomed_search")

# Create database engine with connection pooling
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    # Connection arguments for specific database types
    connect_args={} # Removed SQLite-specific args
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for declarative models
Base = declarative_base()

def get_db() -> Generator:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    try:
        logger.info("Starting database initialization...")
        logger.info(f"Using database URL: {SQLALCHEMY_DATABASE_URL.split('://')[0]}://*****")
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Log table names for verification
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        logger.info(f"Available tables: {table_names}")

    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        raise