# Feature: sbms-api-endpoints, Property 6: Role-Based Access Denial
"""
Property-based tests for role-based access denial.

Tests validate that:
1. For any role NOT in the required set, require_role raises ForbiddenError
2. For any role IN the required set, require_role returns the user
3. A user with no roles always gets ForbiddenError
4. Test with all 4 roles against various role requirements

Additionally validates that requests without a valid JWT token to a protected
endpoint return HTTP 401.

**Validates: Requirements 6.6, 6.7, 7.5, 11.6, 17.5, 19.8**
"""

import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Depends
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.exceptions import ForbiddenError, register_exception_handlers
from app.core.rbac import (
    require_role,
    ALL_ROLES,
    ROLE_DEPT_ADMIN,
    ROLE_SCHOOL_ADMIN,
    ROLE_TEACHER,
    ROLE_PARENT,
)
from app.core.deps import get_current_user_dependency


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALL_ROLES_LIST = list(ALL_ROLES)  # ["DeptAdmin", "SchoolAdmin", "Teacher", "Parent"]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: generate a non-empty subset of roles as the "required roles" for an endpoint
required_roles_strategy = st.lists(
    st.sampled_from(ALL_ROLES_LIST),
    min_size=1,
    max_size=4,
    unique=True,
)

# Strategy: generate a single role for a user
single_role_strategy = st.sampled_from(ALL_ROLES_LIST)

# Strategy: generate a non-empty set of user roles (user can have multiple roles)
user_roles_strategy = st.lists(
    st.sampled_from(ALL_ROLES_LIST),
    min_size=1,
    max_size=4,
    unique=True,
)

# Strategy: generate ASCII-safe invalid tokens (letters and digits only)
ascii_token_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), max_codepoint=127),
    min_size=1,
    max_size=50,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user(roles: list[str]) -> MagicMock:
    """Create a mock User object with the specified roles."""
    user = MagicMock()
    user.id = 1
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.is_active = True
    user.department_id = 1
    user.school_id = 1

    # Create mock UserRole objects
    mock_roles = []
    for role_name in roles:
        mock_role = MagicMock()
        mock_role.role = role_name
        mock_roles.append(mock_role)

    user.roles = mock_roles
    return user


def _create_protected_app(required_roles: list[str], mock_user=None) -> FastAPI:
    """Create a FastAPI app with a protected endpoint requiring specific roles.

    If mock_user is provided, the auth dependency is overridden to return that user
    (simulating an authenticated request). If None, the real auth dependency is used
    (which will fail with 401 for missing/invalid tokens).
    """
    app = FastAPI()
    register_exception_handlers(app)

    role_dep = require_role(*required_roles)

    @app.get("/protected")
    async def protected_endpoint(current_user=Depends(role_dep)):
        return {"user_id": current_user.id, "message": "access granted"}

    if mock_user is not None:
        # Override the auth dependency to inject our mock user
        app.dependency_overrides[get_current_user_dependency] = lambda: mock_user

    return app


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestRoleBasedAccessDenial:
    """
    Property 6: For any protected endpoint and any authenticated user whose
    role is not in the endpoint's required roles set, the API SHALL return
    HTTP 403 with error_type "forbidden".
    """

    @given(
        required_roles=required_roles_strategy,
        user_role=single_role_strategy,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_unauthorized_role_gets_403(
        self, required_roles: list[str], user_role: str
    ):
        """For any role NOT in the required set, the API returns 403 forbidden."""
        # Only test when user's role is NOT in the required set
        assume(user_role not in required_roles)

        mock_user = _make_mock_user([user_role])
        app = _create_protected_app(required_roles, mock_user=mock_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/protected")

            assert resp.status_code == 403, (
                f"Expected 403 for user with role '{user_role}' "
                f"accessing endpoint requiring {required_roles}, got {resp.status_code}"
            )
            body = resp.json()
            assert body["error_type"] == "forbidden"
            assert body["status_code"] == 403

    @given(
        required_roles=required_roles_strategy,
        user_role=single_role_strategy,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_authorized_role_gets_access(
        self, required_roles: list[str], user_role: str
    ):
        """For any role IN the required set, the API grants access (returns user)."""
        # Only test when user's role IS in the required set
        assume(user_role in required_roles)

        mock_user = _make_mock_user([user_role])
        app = _create_protected_app(required_roles, mock_user=mock_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/protected")

            assert resp.status_code == 200, (
                f"Expected 200 for user with role '{user_role}' "
                f"accessing endpoint requiring {required_roles}, got {resp.status_code}"
            )
            body = resp.json()
            assert body["message"] == "access granted"

    @given(required_roles=required_roles_strategy)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_user_with_no_roles_always_gets_403(
        self, required_roles: list[str]
    ):
        """A user with no roles always gets ForbiddenError (403)."""
        mock_user = _make_mock_user([])  # No roles assigned
        app = _create_protected_app(required_roles, mock_user=mock_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/protected")

            assert resp.status_code == 403, (
                f"Expected 403 for user with no roles "
                f"accessing endpoint requiring {required_roles}, got {resp.status_code}"
            )
            body = resp.json()
            assert body["error_type"] == "forbidden"

    @given(
        required_roles=required_roles_strategy,
        user_roles=user_roles_strategy,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_multi_role_user_access_with_overlap(
        self, required_roles: list[str], user_roles: list[str]
    ):
        """A user with multiple roles gets access if ANY of their roles is in the required set."""
        has_overlap = any(r in required_roles for r in user_roles)

        mock_user = _make_mock_user(user_roles)
        app = _create_protected_app(required_roles, mock_user=mock_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/protected")

            if has_overlap:
                assert resp.status_code == 200, (
                    f"Expected 200 for user with roles {user_roles} "
                    f"accessing endpoint requiring {required_roles}, got {resp.status_code}"
                )
            else:
                assert resp.status_code == 403, (
                    f"Expected 403 for user with roles {user_roles} "
                    f"accessing endpoint requiring {required_roles}, got {resp.status_code}"
                )
                body = resp.json()
                assert body["error_type"] == "forbidden"


class TestMissingTokenReturns401:
    """
    Property 6 (401 variant): For any request without a valid JWT token
    to a protected endpoint, the API SHALL return HTTP 401.
    """

    @given(required_roles=required_roles_strategy)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_no_auth_header_returns_401(self, required_roles: list[str]):
        """A request without an Authorization header to a protected endpoint returns 401."""
        # No mock_user → real auth dependency is used → will fail with 401
        app = _create_protected_app(required_roles, mock_user=None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/protected")

            assert resp.status_code == 401, (
                f"Expected 401 for request without auth header, got {resp.status_code}"
            )
            body = resp.json()
            assert body["error_type"] == "unauthorized"
            assert body["status_code"] == 401

    @given(
        required_roles=required_roles_strategy,
        invalid_token=ascii_token_strategy,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(
        self, required_roles: list[str], invalid_token: str
    ):
        """A request with an invalid JWT token to a protected endpoint returns 401."""
        # No mock_user → real auth dependency validates the token → will fail with 401
        app = _create_protected_app(required_roles, mock_user=None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/protected",
                headers={"Authorization": f"Bearer {invalid_token}"},
            )

            assert resp.status_code == 401, (
                f"Expected 401 for invalid token, got {resp.status_code}"
            )
            body = resp.json()
            assert body["error_type"] == "unauthorized"
            assert body["status_code"] == 401

    @given(
        required_roles=required_roles_strategy,
        malformed_header=st.sampled_from([
            "Basic abc123",
            "Token xyz",
            "Bearer",
            "bearer",
            "BEARER token123",
            "NotBearer abc",
            "Bear token",
            "Bearertoken",
        ]),
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_malformed_auth_header_returns_401(
        self, required_roles: list[str], malformed_header: str
    ):
        """A request with a malformed Authorization header returns 401."""
        # No mock_user → real auth dependency → will fail with 401
        app = _create_protected_app(required_roles, mock_user=None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/protected",
                headers={"Authorization": malformed_header},
            )

            assert resp.status_code == 401, (
                f"Expected 401 for malformed auth header '{malformed_header}', "
                f"got {resp.status_code}"
            )
            body = resp.json()
            assert body["error_type"] == "unauthorized"
            assert body["status_code"] == 401
