"""
FastAPI dependencies for authentication and authorization.

Provides `get_current_user_dependency` which extracts the JWT token
from the Authorization header and returns the authenticated user.
"""

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.database.session import get_db
from app.models.database import User
from app.services import auth_service


def _extract_token(authorization: str = Header(None, alias="Authorization")) -> str:
    """Extract the Bearer token from the Authorization header.

    Expects format: "Bearer <token>"
    Raises UnauthorizedError if header is missing or malformed.
    """
    if not authorization:
        raise UnauthorizedError(detail="Authorization header is missing")

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError(detail="Invalid authorization header format")

    return parts[1]


def get_current_user_dependency(
    token: str = Depends(_extract_token),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency that returns the current authenticated user.

    Extracts the JWT token from the Authorization header, validates it,
    checks the blacklist, and returns the corresponding User object.

    Usage in endpoint:
        @router.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user_dependency)):
            ...
    """
    return auth_service.get_current_user(db, token)
