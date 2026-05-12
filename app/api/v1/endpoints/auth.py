"""Authentication endpoints for the SBMS API.

Provides routes for user registration, login, token refresh, and logout.
"""

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_dependency
from app.core.exceptions import UnauthorizedError
from app.database.session import get_db
from app.models.database import User
from app.schemas.auth import (
    AccessTokenResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_bearer_token(
    authorization: str = Header(None, alias="Authorization"),
) -> str:
    """Extract the Bearer token string from the Authorization header.

    Used by the logout endpoint to get the raw token for blacklisting.
    """
    if not authorization:
        raise UnauthorizedError(detail="Authorization header is missing")

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError(detail="Invalid authorization header format")

    return parts[1]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account.

    Creates a new user with the provided email, password, and full name.
    Returns the user profile (excluding password hash) with HTTP 201.

    Raises:
        409 Conflict: If a user with the same email already exists.
        422 Validation Error: If required fields are missing or invalid.
    """
    user = auth_service.register(
        db=db,
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        role=request.role,
        department_id=request.department_id,
        school_id=request.school_id,
    )
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and obtain tokens",
)
def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user with email and password.

    Returns an access token (30-minute expiry) and a refresh token (7-day expiry).

    Raises:
        401 Unauthorized: If credentials are invalid (does not reveal which field).
    """
    token_data = auth_service.login(
        db=db,
        email=request.email,
        password=request.password,
    )
    return token_data


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Refresh access token",
)
def refresh(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token.

    Raises:
        401 Unauthorized: If the refresh token is invalid or expired.
    """
    new_access_token = auth_service.refresh_token(
        db=db,
        refresh_token_str=request.refresh_token,
    )
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout and invalidate token",
)
def logout(
    current_user: User = Depends(get_current_user_dependency),
    token: str = Depends(_extract_bearer_token),
):
    """Invalidate the current access token.

    After logout, subsequent requests using this token will receive HTTP 401.

    Requires a valid Bearer token in the Authorization header.
    """
    auth_service.logout(token)
    return {"message": "Successfully logged out"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def get_me(
    current_user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
):
    """Get the authenticated user's own profile.

    Any authenticated user can access this endpoint regardless of role.
    """
    from app.models.database import UserRole as UserRoleModel

    user_role = db.query(UserRoleModel).filter(UserRoleModel.user_id == current_user.id).first()
    current_user.role = user_role.role if user_role else "User"
    return current_user
