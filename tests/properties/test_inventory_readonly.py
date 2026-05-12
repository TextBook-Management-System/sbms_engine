# Feature: sbms-api-endpoints, Property 16: Read-Only Inventory Enforcement
"""
Property-based tests for read-only inventory enforcement.

Tests validate that:
- For any HTTP method other than GET sent to `/api/v1/schools/{school_id}/inventory`,
  the API SHALL return HTTP 405, since inventory is maintained by MySQL triggers
  and is not directly writable through the API.
- GET requests to the same endpoint succeed (HTTP 200).

**Validates: Requirements 10.4**
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import patch, MagicMock

from app.api.v1.endpoints.inventory import router
from app.core.exceptions import register_exception_handlers
from app.core.pagination import PaginatedResponse


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: generate random school_ids (positive integers, BIGINT UNSIGNED range)
school_ids = st.integers(min_value=1, max_value=2**63 - 1)

# Strategy: generate random JSON request bodies for POST/PUT
request_bodies = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=20,
    ),
    values=st.one_of(
        st.text(min_size=0, max_size=50),
        st.integers(min_value=0, max_value=10000),
        st.booleans(),
        st.none(),
    ),
    min_size=0,
    max_size=5,
)


# ---------------------------------------------------------------------------
# Test App Factory
# ---------------------------------------------------------------------------

def _create_inventory_test_app() -> FastAPI:
    """Create a FastAPI app with the inventory router for testing."""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestReadOnlyInventoryEnforcement:
    """
    Property 16: For any HTTP method other than GET sent to
    /api/v1/schools/{school_id}/inventory, the API SHALL return HTTP 405,
    since inventory is maintained by MySQL triggers and is not directly
    writable through the API.
    """

    @given(
        school_id=school_ids,
        body=request_bodies,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_post_to_inventory_returns_405(
        self, school_id: int, body: dict
    ):
        """
        POST to /api/v1/schools/{school_id}/inventory SHALL return HTTP 405
        for any school_id and any request body.

        **Validates: Requirements 10.4**
        """
        app = _create_inventory_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/schools/{school_id}/inventory",
                json=body,
            )

            assert resp.status_code == 405, (
                f"Expected 405 for POST /api/v1/schools/{school_id}/inventory, "
                f"got {resp.status_code}"
            )

            response_body = resp.json()
            assert "detail" in response_body
            assert response_body["status_code"] == 405
            assert "read-only" in response_body["detail"].lower() or "trigger" in response_body["detail"].lower()

    @given(
        school_id=school_ids,
        body=request_bodies,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_put_to_inventory_returns_405(
        self, school_id: int, body: dict
    ):
        """
        PUT to /api/v1/schools/{school_id}/inventory SHALL return HTTP 405
        for any school_id and any request body.

        **Validates: Requirements 10.4**
        """
        app = _create_inventory_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/api/v1/schools/{school_id}/inventory",
                json=body,
            )

            assert resp.status_code == 405, (
                f"Expected 405 for PUT /api/v1/schools/{school_id}/inventory, "
                f"got {resp.status_code}"
            )

            response_body = resp.json()
            assert "detail" in response_body
            assert response_body["status_code"] == 405
            assert "read-only" in response_body["detail"].lower() or "trigger" in response_body["detail"].lower()

    @given(school_id=school_ids)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_delete_to_inventory_returns_405(self, school_id: int):
        """
        DELETE to /api/v1/schools/{school_id}/inventory SHALL return HTTP 405
        for any school_id.

        **Validates: Requirements 10.4**
        """
        app = _create_inventory_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.delete(
                f"/api/v1/schools/{school_id}/inventory",
            )

            assert resp.status_code == 405, (
                f"Expected 405 for DELETE /api/v1/schools/{school_id}/inventory, "
                f"got {resp.status_code}"
            )

            response_body = resp.json()
            assert "detail" in response_body
            assert response_body["status_code"] == 405
            assert "read-only" in response_body["detail"].lower() or "trigger" in response_body["detail"].lower()

    @given(school_id=school_ids)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_get_inventory_succeeds(self, school_id: int):
        """
        GET to /api/v1/schools/{school_id}/inventory SHALL succeed (HTTP 200)
        when the school exists and inventory records are available.

        **Validates: Requirements 10.4**
        """
        app = _create_inventory_test_app()
        transport = ASGITransport(app=app)

        # Mock the inventory service to return a valid paginated response
        mock_paginated = PaginatedResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
        )

        with patch(
            "app.api.v1.endpoints.inventory.inventory_service.get_inventory_list",
            return_value=mock_paginated,
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/schools/{school_id}/inventory",
                )

                assert resp.status_code == 200, (
                    f"Expected 200 for GET /api/v1/schools/{school_id}/inventory, "
                    f"got {resp.status_code}"
                )

                response_body = resp.json()
                assert "items" in response_body
                assert "total" in response_body
                assert "page" in response_body
                assert "page_size" in response_body

    @given(
        school_id=school_ids,
        body=request_bodies,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_405_response_has_correct_error_structure(
        self, school_id: int, body: dict
    ):
        """
        All 405 responses from inventory endpoints SHALL include the standard
        error response fields: detail, status_code, and error_type.

        **Validates: Requirements 10.4**
        """
        app = _create_inventory_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test all non-GET methods
            for method in ["post", "put", "delete"]:
                request_kwargs = {"json": body} if method != "delete" else {}
                resp = await getattr(client, method)(
                    f"/api/v1/schools/{school_id}/inventory",
                    **request_kwargs,
                )

                assert resp.status_code == 405

                response_body = resp.json()
                # Verify standard error structure
                assert "detail" in response_body, (
                    f"{method.upper()} response missing 'detail' field"
                )
                assert "status_code" in response_body, (
                    f"{method.upper()} response missing 'status_code' field"
                )
                assert "error_type" in response_body, (
                    f"{method.upper()} response missing 'error_type' field"
                )
                assert response_body["status_code"] == 405
                assert isinstance(response_body["detail"], str)
