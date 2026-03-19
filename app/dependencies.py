"""
FastAPI dependencies for PrimeHaul Office Manager.
Auth middleware, role hierarchy, company-scoped access.
"""

from typing import Optional
from fastapi import Depends, HTTPException, Cookie, status
from sqlalchemy.orm import Session
from jose import JWTError

from app.database import get_db
from app.auth import decode_access_token
from app.models import User, Company


# Role hierarchy: higher number = more permissions
ROLE_HIERARCHY = {
    "porter": 1,
    "driver": 2,
    "surveyor": 3,
    "office": 4,
    "admin": 5,
    "owner": 6,
}


def get_current_user(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> User:
    """Get the currently authenticated user from JWT cookie."""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_access_token(access_token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()

    return user


def get_optional_current_user(
    access_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Optionally get the current user. Returns None if not authenticated."""
    if not access_token:
        return None
    try:
        payload = decode_access_token(access_token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.id == user_id, User.is_active == True).first()
    except JWTError:
        return None


def require_role(required_role: str):
    """Dependency factory to require a minimum role level."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}",
            )
        return current_user

    return role_checker


def get_current_company(current_user: User = Depends(get_current_user)) -> Company:
    """Get the current user's company."""
    return current_user.company
