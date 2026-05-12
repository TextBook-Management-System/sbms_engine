"""Unit tests for app.services.auth_service module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from jose import jwt

from app.config.settings import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.services import auth_service
from app.services.auth_service import (
    _create_access_token,
    _create_refresh_token,
    _hash_password,
    _verify_password,
    _token_blacklist,
)


# --- Password Hashing Tests ---


class TestPasswordHashing:
    """Tests for bcrypt password hashing and verification."""

    def test_hash_password_returns_bcrypt_hash(self):
        """Hashed password starts with bcrypt prefix."""
        hashed = _hash_password("mysecretpassword")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_password_different_each_time(self):
        """Two hashes of the same password are different (due to salt)."""
        h1 = _hash_password("samepassword")
        h2 = _hash_password("samepassword")
        assert h1 != h2

    def test_verify_password_correct(self):
        """Correct password verifies against its hash."""
        password = "testpassword123"
        hashed = _hash_password(password)
        assert _verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Wrong password does not verify."""
        hashed = _hash_password("correctpassword")
        assert _verify_password("wrongpassword", hashed) is False


# --- Token Creation Tests ---


class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_access_token_contains_user_id_and_role(self):
        """Access token payload contains sub (user_id) and role."""
        token = _create_access_token(user_id=42, role="SchoolAdmin")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "42"
        assert payload["role"] == "SchoolAdmin"
        assert "exp" in payload

    def test_access_token_expires_in_30_minutes(self):
        """Access token expiration is approximately 30 minutes from now."""
        before = datetime.now(timezone.utc)
        token = _create_access_token(user_id=1, role="Teacher")
        after = datetime.now(timezone.utc)

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        # Allow 1 second tolerance due to integer timestamp rounding
        expected_min = before + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES) - timedelta(seconds=1)
        expected_max = after + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES) + timedelta(seconds=1)

        assert expected_min <= exp <= expected_max

    def test_refresh_token_contains_user_id_and_type(self):
        """Refresh token payload contains sub (user_id) and type='refresh'."""
        token = _create_refresh_token(user_id=99)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "99"
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_refresh_token_expires_in_7_days(self):
        """Refresh token expiration is approximately 7 days from now."""
        before = datetime.now(timezone.utc)
        token = _create_refresh_token(user_id=1)
        after = datetime.now(timezone.utc)

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        # Allow 1 second tolerance due to integer timestamp rounding
        expected_min = before + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS) - timedelta(seconds=1)
        expected_max = after + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS) + timedelta(seconds=1)

        assert expected_min <= exp <= expected_max

    def test_access_token_does_not_have_type_field(self):
        """Access token should not have a 'type' field (distinguishes from refresh)."""
        token = _create_access_token(user_id=1, role="Parent")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "type" not in payload

    def test_refresh_token_does_not_have_role_field(self):
        """Refresh token should not have a 'role' field."""
        token = _create_refresh_token(user_id=1)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "role" not in payload


# --- Register Tests ---


class TestRegister:
    """Tests for the register function."""

    def _make_mock_db(self, existing_user=None):
        """Create a mock DB session."""
        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.first.return_value = existing_user
        return db

    def test_register_success(self):
        """Successful registration creates user and returns it."""
        db = self._make_mock_db(existing_user=None)

        # Make db.refresh set the id on the user
        def mock_refresh(user):
            user.id = 1

        db.refresh.side_effect = mock_refresh

        user = auth_service.register(
            db=db,
            email="test@example.com",
            password="securepass123",
            full_name="Test User",
        )

        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.is_active is True
        # Password should be hashed, not plain
        assert user.password_hash != "securepass123"
        assert user.password_hash.startswith("$2b$") or user.password_hash.startswith("$2a$")
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_register_duplicate_email_raises_conflict(self):
        """Registration with existing email raises ConflictError."""
        existing = MagicMock()
        existing.email = "existing@example.com"
        db = self._make_mock_db(existing_user=existing)

        with pytest.raises(ConflictError) as exc_info:
            auth_service.register(
                db=db,
                email="existing@example.com",
                password="password123",
                full_name="Duplicate User",
            )

        assert "already registered" in exc_info.value.detail


# --- Login Tests ---


class TestLogin:
    """Tests for the login function."""

    def _make_mock_db_with_user(self, user=None, role=None):
        """Create a mock DB session that returns a user and optionally a role."""
        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        filter_mock = MagicMock()
        query.filter.return_value = filter_mock

        # First call returns user, second call returns role
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return user
            return role

        filter_mock.first.side_effect = side_effect
        return db

    def test_login_success(self):
        """Successful login returns token pair."""
        password = "correctpassword"
        hashed = _hash_password(password)

        user = MagicMock()
        user.id = 1
        user.email = "user@example.com"
        user.password_hash = hashed
        user.is_active = True

        role = MagicMock()
        role.role = "SchoolAdmin"

        db = self._make_mock_db_with_user(user=user, role=role)

        result = auth_service.login(db=db, email="user@example.com", password=password)

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    def test_login_wrong_email_raises_unauthorized(self):
        """Login with non-existent email raises UnauthorizedError."""
        db = self._make_mock_db_with_user(user=None)

        with pytest.raises(UnauthorizedError) as exc_info:
            auth_service.login(db=db, email="noone@example.com", password="anything")

        assert "Invalid credentials" in exc_info.value.detail

    def test_login_wrong_password_raises_unauthorized(self):
        """Login with wrong password raises UnauthorizedError."""
        user = MagicMock()
        user.id = 1
        user.email = "user@example.com"
        user.password_hash = _hash_password("correctpassword")
        user.is_active = True

        db = self._make_mock_db_with_user(user=user)

        with pytest.raises(UnauthorizedError) as exc_info:
            auth_service.login(db=db, email="user@example.com", password="wrongpassword")

        assert "Invalid credentials" in exc_info.value.detail

    def test_login_inactive_user_raises_unauthorized(self):
        """Login with inactive user raises UnauthorizedError."""
        password = "correctpassword"
        user = MagicMock()
        user.id = 1
        user.email = "user@example.com"
        user.password_hash = _hash_password(password)
        user.is_active = False

        db = self._make_mock_db_with_user(user=user)

        with pytest.raises(UnauthorizedError) as exc_info:
            auth_service.login(db=db, email="user@example.com", password=password)

        assert "Invalid credentials" in exc_info.value.detail


# --- Logout Tests ---


class TestLogout:
    """Tests for the logout function."""

    def setup_method(self):
        """Clear the blacklist before each test."""
        _token_blacklist.clear()

    def test_logout_blacklists_token(self):
        """After logout, the token is in the blacklist."""
        token = "some-jwt-token-string"
        auth_service.logout(token)
        assert token in _token_blacklist

    def test_logout_multiple_tokens(self):
        """Multiple tokens can be blacklisted."""
        auth_service.logout("token1")
        auth_service.logout("token2")
        assert "token1" in _token_blacklist
        assert "token2" in _token_blacklist


# --- Get Current User Tests ---


class TestGetCurrentUser:
    """Tests for the get_current_user function."""

    def setup_method(self):
        """Clear the blacklist before each test."""
        _token_blacklist.clear()

    def _make_mock_db_with_user(self, user=None):
        """Create a mock DB session that returns a user."""
        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.first.return_value = user
        return db

    def test_get_current_user_success(self):
        """Valid token returns the user."""
        token = _create_access_token(user_id=5, role="Teacher")

        user = MagicMock()
        user.id = 5
        user.is_active = True

        db = self._make_mock_db_with_user(user=user)

        result = auth_service.get_current_user(db=db, token=token)
        assert result == user

    def test_get_current_user_invalid_token(self):
        """Invalid token raises UnauthorizedError."""
        db = self._make_mock_db_with_user()

        with pytest.raises(UnauthorizedError):
            auth_service.get_current_user(db=db, token="invalid.token.here")

    def test_get_current_user_blacklisted_token(self):
        """Blacklisted token raises UnauthorizedError."""
        token = _create_access_token(user_id=5, role="Teacher")
        auth_service.logout(token)

        db = self._make_mock_db_with_user()

        with pytest.raises(UnauthorizedError) as exc_info:
            auth_service.get_current_user(db=db, token=token)

        assert "invalidated" in exc_info.value.detail

    def test_get_current_user_nonexistent_user(self):
        """Token for non-existent user raises UnauthorizedError."""
        token = _create_access_token(user_id=999, role="Parent")
        db = self._make_mock_db_with_user(user=None)

        with pytest.raises(UnauthorizedError) as exc_info:
            auth_service.get_current_user(db=db, token=token)

        assert "not found" in exc_info.value.detail

    def test_get_current_user_inactive_user(self):
        """Token for inactive user raises UnauthorizedError."""
        token = _create_access_token(user_id=5, role="Teacher")

        user = MagicMock()
        user.id = 5
        user.is_active = False

        db = self._make_mock_db_with_user(user=user)

        with pytest.raises(UnauthorizedError) as exc_info:
            auth_service.get_current_user(db=db, token=token)

        assert "deactivated" in exc_info.value.detail


# --- Refresh Token Tests ---


class TestRefreshToken:
    """Tests for the refresh_token function."""

    def setup_method(self):
        """Clear the blacklist before each test."""
        _token_blacklist.clear()

    def _make_mock_db_with_user(self, user=None, role=None):
        """Create a mock DB session."""
        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        filter_mock = MagicMock()
        query.filter.return_value = filter_mock

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return user
            return role

        filter_mock.first.side_effect = side_effect
        return db

    def test_refresh_token_success(self):
        """Valid refresh token returns a new access token."""
        refresh = _create_refresh_token(user_id=10)

        user = MagicMock()
        user.id = 10
        user.is_active = True

        role = MagicMock()
        role.role = "DeptAdmin"

        db = self._make_mock_db_with_user(user=user, role=role)

        new_access = auth_service.refresh_token(db=db, refresh_token_str=refresh)

        # Verify the new access token is valid
        payload = jwt.decode(new_access, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "10"
        assert payload["role"] == "DeptAdmin"

    def test_refresh_token_invalid_raises_unauthorized(self):
        """Invalid refresh token raises UnauthorizedError."""
        db = MagicMock()

        with pytest.raises(UnauthorizedError):
            auth_service.refresh_token(db=db, refresh_token_str="invalid.token")

    def test_refresh_token_access_token_rejected(self):
        """Using an access token as refresh token raises UnauthorizedError."""
        access = _create_access_token(user_id=1, role="Teacher")
        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.first.return_value = None

        with pytest.raises(UnauthorizedError):
            auth_service.refresh_token(db=db, refresh_token_str=access)

    def test_refresh_token_blacklisted_raises_unauthorized(self):
        """Blacklisted refresh token raises UnauthorizedError."""
        refresh = _create_refresh_token(user_id=10)
        auth_service.logout(refresh)

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.first.return_value = None

        with pytest.raises(UnauthorizedError):
            auth_service.refresh_token(db=db, refresh_token_str=refresh)
