from datetime import datetime, timedelta
from typing import Optional
import logging
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
import os
from database import get_db
from models.database_models import User

# Configure logging
logger = logging.getLogger(__name__)

# JWT configuration
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a new JWT access token"""
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        logger.debug(f"Creating access token with data: {to_encode}")
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating access token"
        )

async def get_current_user(token: str = Depends(None), db: Session = Depends(get_db)): #oauth2_scheme removed
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        logger.debug(f"Received token for verification: {token[:10]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.debug(f"Decoded token payload: {payload}")

        email: str = payload.get("sub")
        if email is None:
            logger.warning("Token payload missing 'sub' claim")
            raise credentials_exception

        logger.debug(f"Looking up user with email: {email}")
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            logger.warning(f"No user found for email: {email}")
            raise credentials_exception

        logger.debug(f"Successfully authenticated user: {user.username}")
        return user
    except JWTError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error validating user"
        )