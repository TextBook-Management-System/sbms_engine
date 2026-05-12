# Feature: sbms-api-endpoints, Property 10: Token Lifecycle Integrity
"""
Property-based tests for token lifecycle integrity.

Tests validate that:
1. For any user_id (positive int) and any valid role, _create_access_token
   produces a token that decodes to {sub: str(user_id), role: role, exp: ...}
2. For any user_id, _create_refresh_token produces a token with
   {sub: str(user_id), type: "refresh", exp: ...}
3. After logout(token), get_current_user raises UnauthorizedError for that token
4. Access tokens don't have "type" field, refresh tokens don't have "role" field

**Validates: Requirements 5.2, 5.7, 5.8**
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from jose import jwt
from unittest.mock import MagicMock, patch

from app.services.auth_service import (
    _create_access_token,
    _create_refresh_token,
    _token_blacklist,
    logout,
    get_current_user,
)
from app.config.settings import settings as app_settings
from app.core.exceptions import UnauthorizedError


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid roles as defined in the database model
valid_roles = st.sampled_from(["DeptAdmin", "SchoolAdmin", "Teacher", "Parent"])

# Positive integer user IDs (matching BIGINT UNSIGNED)
positive_user_ids = st.integers(min_value=1, max_value=2**63 - 1)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestAccessTokenPayload:
    """
    Property 10 (part 1): For any user_id (positive int) and any valid role,
    _create_access_token produces a token that decodes to
    {sub: str(user_id), role: role, exp: ...}.
    """

    @given(user_id=positive_user_ids, role=valid_roles)
    @settings(max_examples=100, deadline=None)
    def test_access_token_contains_user_id_and_role(self, user_id: int, role: str):
        """Access token payload always contains sub=str(user_id) and role=role."""
        token = _create_access_token(user_id, role)

        # Decode without verification of expiry to inspect payload
        payload = jwt.decode(
            token,
            app_settings.SECRET_KEY,
            algorithms=[app_settings.ALGORITHM],
            options={"verify_exp": False},
        )

        assert payload["sub"] == str(user_id), (
            f"Expected sub='{user_id}', got sub='{payload.get('sub')}'"
        )
        assert payload["role"] == role, (
            f"Expected role='{role}', got role='{payload.get('role')}'"
        )
        assert "exp" in payload, "Access token must contain 'exp' claim"

    @given(user_id=positive_user_ids, role=valid_roles)
    @settings(max_examples=100, deadline=None)
    def test_access_token_does_not_have_type_field(self, user_id: int, role: str):
        """Access tokens SHALL NOT have a 'type' field (distinguishes from refresh tokens)."""
        token = _create_access_token(user_id, role)

        payload = jwt.decode(
            token,
            app_settings.SECRET_KEY,
            algorithms=[app_settings.ALGORITHM],
            options={"verify_exp": False},
        )

        assert "type" not in payload, (
            f"Access token should not contain 'type' field, but got type='{payload.get('type')}'"
        )


class TestRefreshTokenPayload:
    """
    Property 10 (part 2): For any user_id, _create_refresh_token produces a
    token with {sub: str(user_id), type: "refresh", exp: ...}.
    """

    @given(user_id=positive_user_ids)
    @settings(max_examples=100, deadline=None)
    def test_refresh_token_contains_user_id_and_type(self, user_id: int):
        """Refresh token payload always contains sub=str(user_id) and type='refresh'."""
        token = _create_refresh_token(user_id)

        payload = jwt.decode(
            token,
            app_settings.SECRET_KEY,
            algorithms=[app_settings.ALGORITHM],
            options={"verify_exp": False},
        )

        assert payload["sub"] == str(user_id), (
            f"Expected sub='{user_id}', got sub='{payload.get('sub')}'"
        )
        assert payload["type"] == "refresh", (
            f"Expected type='refresh', got type='{payload.get('type')}'"
        )
        assert "exp" in payload, "Refresh token must contain 'exp' claim"

    @given(user_id=positive_user_ids)
    @settings(max_examples=100, deadline=None)
    def test_refresh_token_does_not_have_role_field(self, user_id: int):
        """Refresh tokens SHALL NOT have a 'role' field (distinguishes from access tokens)."""
        token = _create_refresh_token(user_id)

        payload = jwt.decode(
            token,
            app_settings.SECRET_KEY,
            algorithms=[app_settings.ALGORITHM],
            options={"verify_exp": False},
        )

        assert "role" not in payload, (
            f"Refresh token should not contain 'role' field, but got role='{payload.get('role')}'"
        )


class TestLogoutInvalidatesToken:
    """
    Property 10 (part 3): After logout(token), get_current_user raises
    UnauthorizedError for that token.
    """

    @given(user_id=positive_user_ids, role=valid_roles)
    @settings(max_examples=100, deadline=None)
    def test_logout_blacklists_token(self, user_id: int, role: str):
        """After logout, the token is in the blacklist and get_current_user raises UnauthorizedError."""
        token = _create_access_token(user_id, role)

        # Logout the token
        logout(token)

        try:
            # Mock the db session since get_current_user needs it but we only
            # care about the blacklist check which happens before DB access
            mock_db = MagicMock()

            with pytest.raises(UnauthorizedError):
                get_current_user(mock_db, token)
        finally:
            # Clean up the blacklist to avoid polluting other tests
            _token_blacklist.discard(token)
