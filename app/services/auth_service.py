"""
Authentication service for the SBMS API.

Handles user registration, login, token management (JWT), and logout
with token blacklisting. Uses bcrypt for password hashing and
python-jose for JWT encoding/decoding.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.models.database import User, UserRole


# --- Error Messages ---

_MSG_INVALID_CREDENTIALS = "Invalid credentials"
_MSG_INVALID_REFRESH_TOKEN = "Invalid or expired refresh token"

# --- Password Hashing ---


def _hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# --- Token Blacklist (in-memory) ---

_token_blacklist: set[str] = set()


def _is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted (logged out)."""
    return token in _token_blacklist


def _blacklist_token(token: str) -> None:
    """Add a token to the blacklist."""
    _token_blacklist.add(token)


# --- JWT Token Creation ---


def _create_access_token(user_id: int, role: str) -> str:
    """Create a JWT access token with user_id and role in payload.

    Token expires after ACCESS_TOKEN_EXPIRE_MINUTES (default 30 min).
    Payload: {sub: str(user_id), role: role_name, exp: timestamp}
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _create_refresh_token(user_id: int) -> str:
    """Create a JWT refresh token.

    Token expires after REFRESH_TOKEN_EXPIRE_DAYS (default 7 days).
    Payload: {sub: str(user_id), type: "refresh", exp: timestamp}
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# --- Service Methods ---


def register(
    db: Session,
    email: str,
    password: str,
    full_name: str,
    department_id: Optional[int] = None,
    school_id: Optional[int] = None,
) -> User:
    """Register a new user.

    - Checks for duplicate email (raises ConflictError if exists)
    - Hashes password with bcrypt
    - Creates user record in DB
    - Returns user object (password_hash excluded from API response via schema)
    """
    # Check for existing user with same email
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise ConflictError(detail="A user with this email is already registered")

    # Hash the password
    hashed = _hash_password(password)

    # Create user
    user = User(
        email=email,
        password_hash=hashed,
        full_name=full_name,
        is_active=True,
        department_id=department_id,
        school_id=school_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def login(db: Session, email: str, password: str) -> dict:
    """Authenticate a user and return a token pair.

    - Verifies email exists and password matches
    - Returns generic "Invalid credentials" on failure (doesn't reveal which field)
    - Returns dict with access_token and refresh_token on success
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise UnauthorizedError(detail=_MSG_INVALID_CREDENTIALS)

    if not _verify_password(password, user.password_hash):
        raise UnauthorizedError(detail=_MSG_INVALID_CREDENTIALS)

    if not user.is_active:
        raise UnauthorizedError(detail=_MSG_INVALID_CREDENTIALS)

    # Get user's primary role (first role assigned, or default)
    role = _get_user_role(db, user.id)

    access_token = _create_access_token(user.id, role)
    refresh_token = _create_refresh_token(user.id)

    # Attach role to user object for serialization
    user.role = role

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


def refresh_token(db: Session, refresh_token_str: str) -> str:
    """Validate a refresh token and return a new access token.

    - Decodes the refresh token
    - Verifies it's a refresh type token and not expired
    - Checks the user still exists and is active
    - Returns a new access token
    """
    try:
        payload = jwt.decode(
            refresh_token_str, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        raise UnauthorizedError(detail=_MSG_INVALID_REFRESH_TOKEN)

    # Verify it's a refresh token
    if payload.get("type") != "refresh":
        raise UnauthorizedError(detail=_MSG_INVALID_REFRESH_TOKEN)

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(detail=_MSG_INVALID_REFRESH_TOKEN)

    # Check if the refresh token is blacklisted
    if _is_token_blacklisted(refresh_token_str):
        raise UnauthorizedError(detail=_MSG_INVALID_REFRESH_TOKEN)

    # Verify user still exists and is active
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise UnauthorizedError(detail=_MSG_INVALID_REFRESH_TOKEN)

    # Get user's role
    role = _get_user_role(db, user.id)

    # Create new access token
    return _create_access_token(user.id, role)


def logout(token: str) -> None:
    """Invalidate a token by adding it to the blacklist.

    After logout, any request using this token will receive HTTP 401.
    """
    _blacklist_token(token)


def get_current_user(db: Session, token: str) -> User:
    """Decode a JWT access token and return the corresponding user.

    - Decodes the token
    - Checks if token is blacklisted
    - Verifies user exists and is active
    - Returns the User object
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        raise UnauthorizedError(detail="Invalid or expired token")

    # Check blacklist
    if _is_token_blacklisted(token):
        raise UnauthorizedError(detail="Token has been invalidated")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise UnauthorizedError(detail="User not found")

    if not user.is_active:
        raise UnauthorizedError(detail="User account is deactivated")

    return user


# --- Helper Functions ---


def _get_user_role(db: Session, user_id: int) -> str:
    """Get the primary role for a user.

    Returns the first assigned role, or 'User' if no roles are assigned.
    """
    user_role = db.query(UserRole).filter(UserRole.user_id == user_id).first()
    if user_role:
        return user_role.role
    return "User"
