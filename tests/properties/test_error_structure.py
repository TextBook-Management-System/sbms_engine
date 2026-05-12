# Feature: sbms-api-endpoints, Property 13: Error Response Structure Consistency
"""
Property-based tests for error response structure consistency.

Tests validate that:
1. For any error response (4xx or 5xx) from any endpoint, the response body
   contains exactly three fields: `detail` (string or list), `status_code`
   (integer matching the HTTP status code), and `error_type` (one of:
   "validation_error", "not_found", "conflict", "unauthorized", "forbidden",
   "server_error").
2. Server errors (500) do NOT expose stack traces, file paths, or SQL queries
   in the `detail` field.

**Validates: Requirements 21.1, 21.4, 21.5, 21.6**
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.exceptions import (
    APIError,
    NotFoundError,
    ConflictError,
    ValidationError,
    ForbiddenError,
    UnauthorizedError,
    register_exception_handlers,
)


# ---------------------------------------------------------------------------
# Valid error_type values per the specification
# ---------------------------------------------------------------------------

VALID_ERROR_TYPES = frozenset([
    "validation_error",
    "not_found",
    "conflict",
    "unauthorized",
    "forbidden",
    "server_error",
])

# Patterns that must NEVER appear in a 500 error detail
SENSITIVE_PATTERNS = [
    "Traceback",
    "traceback",
    "File \"",
    "File '",
    ".py",
    "line ",
    "SELECT ",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "FROM ",
    "WHERE ",
    "sqlalchemy",
    "SQLAlchemy",
    "SQLALCHEMY",
    "\\app\\",
    "/app/",
    "\\src\\",
    "/src/",
    "site-packages",
    "raise ",
    "Exception(",
    "Error(",
]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: generate random error messages that might contain sensitive info
sensitive_exception_messages = st.one_of(
    # Messages with stack trace patterns
    st.builds(
        lambda path, line: f"Error at File \"{path}\", line {line}",
        path=st.from_regex(r"/[a-z]+/[a-z]+\.py", fullmatch=True),
        line=st.integers(min_value=1, max_value=9999),
    ),
    # Messages with SQL queries
    st.builds(
        lambda table, col: f"SELECT * FROM {table} WHERE {col} = 1; IntegrityError",
        table=st.from_regex(r"[a-z_]{3,15}", fullmatch=True),
        col=st.from_regex(r"[a-z_]{2,10}", fullmatch=True),
    ),
    # Messages with file paths
    st.builds(
        lambda path: f"FileNotFoundError: {path}",
        path=st.from_regex(r"/[a-z]+/[a-z]+/[a-z]+\.(py|sql|cfg)", fullmatch=True),
    ),
    # Random text that could be an internal error
    st.text(min_size=1, max_size=200),
)

# Strategy: generate various HTTP error status codes
error_status_codes_4xx = st.sampled_from([400, 401, 403, 404, 405, 409, 422])
error_status_codes_5xx = st.sampled_from([500, 502, 503])

# Strategy: generate valid error types for custom APIError
valid_error_type_strategy = st.sampled_from(list(VALID_ERROR_TYPES))

# Strategy: generate random detail messages for custom errors
detail_messages = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=200,
)


# ---------------------------------------------------------------------------
# Test App Factory
# ---------------------------------------------------------------------------

def _create_error_test_app(
    error_message: str = "test error",
    status_code: int = 500,
    error_type: str = "server_error",
    use_raw_exception: bool = False,
) -> FastAPI:
    """Create a FastAPI app that triggers specific error scenarios."""
    app = FastAPI(debug=False)
    register_exception_handlers(app)

    class ItemCreate(BaseModel):
        name: str = Field(..., min_length=1, max_length=100)
        quantity: int = Field(..., ge=1)

    @app.get("/trigger-api-error")
    async def trigger_api_error():
        raise APIError(
            status_code=status_code,
            detail=error_message,
            error_type=error_type,
        )

    @app.get("/trigger-not-found")
    async def trigger_not_found():
        raise NotFoundError(error_message)

    @app.get("/trigger-conflict")
    async def trigger_conflict():
        raise ConflictError(error_message)

    @app.get("/trigger-validation-error")
    async def trigger_validation():
        raise ValidationError(error_message)

    @app.get("/trigger-forbidden")
    async def trigger_forbidden():
        raise ForbiddenError(error_message)

    @app.get("/trigger-unauthorized")
    async def trigger_unauthorized():
        raise UnauthorizedError(error_message)

    @app.get("/trigger-server-error")
    async def trigger_server_error():
        # Simulate an unhandled exception with potentially sensitive info
        raise RuntimeError(error_message)

    @app.post("/trigger-validation-body")
    async def trigger_validation_body(item: ItemCreate):
        return {"name": item.name}

    return app


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestErrorResponseStructureConsistency:
    """
    Property 13: For any error response (4xx or 5xx) from any endpoint,
    the response body SHALL contain exactly three fields: detail, status_code,
    and error_type.
    """

    @given(
        message=detail_messages,
        error_type=valid_error_type_strategy,
        status_code=st.sampled_from([400, 401, 403, 404, 405, 409, 422, 500, 502, 503]),
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_api_error_always_has_three_fields(
        self, message: str, error_type: str, status_code: int
    ):
        """Any APIError raised produces a response with exactly {detail, status_code, error_type}."""
        app = _create_error_test_app(
            error_message=message,
            status_code=status_code,
            error_type=error_type,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/trigger-api-error")

            assert resp.status_code == status_code
            body = resp.json()

            # Must have exactly three fields
            assert set(body.keys()) == {"detail", "status_code", "error_type"}, (
                f"Expected exactly {{detail, status_code, error_type}}, got {set(body.keys())}"
            )

            # status_code must be an integer matching the HTTP status
            assert body["status_code"] == status_code
            assert isinstance(body["status_code"], int)

            # error_type must be one of the valid values
            assert body["error_type"] in VALID_ERROR_TYPES, (
                f"error_type '{body['error_type']}' not in {VALID_ERROR_TYPES}"
            )

            # detail must be a string or list
            assert isinstance(body["detail"], (str, list)), (
                f"detail must be str or list, got {type(body['detail'])}"
            )

    @given(message=detail_messages)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_not_found_error_structure(self, message: str):
        """NotFoundError always produces correct 404 structure."""
        app = _create_error_test_app(error_message=message)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/trigger-not-found")

            assert resp.status_code == 404
            body = resp.json()
            assert set(body.keys()) == {"detail", "status_code", "error_type"}
            assert body["status_code"] == 404
            assert body["error_type"] == "not_found"
            assert isinstance(body["detail"], str)

    @given(message=detail_messages)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_conflict_error_structure(self, message: str):
        """ConflictError always produces correct 409 structure."""
        app = _create_error_test_app(error_message=message)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/trigger-conflict")

            assert resp.status_code == 409
            body = resp.json()
            assert set(body.keys()) == {"detail", "status_code", "error_type"}
            assert body["status_code"] == 409
            assert body["error_type"] == "conflict"
            assert isinstance(body["detail"], str)

    @given(message=detail_messages)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_forbidden_error_structure(self, message: str):
        """ForbiddenError always produces correct 403 structure."""
        app = _create_error_test_app(error_message=message)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/trigger-forbidden")

            assert resp.status_code == 403
            body = resp.json()
            assert set(body.keys()) == {"detail", "status_code", "error_type"}
            assert body["status_code"] == 403
            assert body["error_type"] == "forbidden"
            assert isinstance(body["detail"], str)

    @given(message=detail_messages)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_unauthorized_error_structure(self, message: str):
        """UnauthorizedError always produces correct 401 structure."""
        app = _create_error_test_app(error_message=message)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/trigger-unauthorized")

            assert resp.status_code == 401
            body = resp.json()
            assert set(body.keys()) == {"detail", "status_code", "error_type"}
            assert body["status_code"] == 401
            assert body["error_type"] == "unauthorized"
            assert isinstance(body["detail"], str)

    @given(message=detail_messages)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_validation_error_structure(self, message: str):
        """ValidationError always produces correct 422 structure."""
        app = _create_error_test_app(error_message=message)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/trigger-validation-error")

            assert resp.status_code == 422
            body = resp.json()
            assert set(body.keys()) == {"detail", "status_code", "error_type"}
            assert body["status_code"] == 422
            assert body["error_type"] == "validation_error"
            assert isinstance(body["detail"], str)


class TestRequestValidationErrorStructure:
    """
    Property 13 (validation_error variant): Pydantic validation errors
    also produce the standard three-field structure with detail as a list.
    """

    @given(
        name=st.text(min_size=0, max_size=0),  # empty string triggers min_length
        quantity=st.integers(max_value=0),       # <= 0 triggers ge=1
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_pydantic_validation_error_structure(self, name: str, quantity: int):
        """Pydantic validation errors produce {detail (list), status_code, error_type}."""
        app = _create_error_test_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/trigger-validation-body",
                json={"name": name, "quantity": quantity},
            )

            assert resp.status_code == 422
            body = resp.json()

            # Must have exactly three fields
            assert set(body.keys()) == {"detail", "status_code", "error_type"}, (
                f"Expected exactly {{detail, status_code, error_type}}, got {set(body.keys())}"
            )

            assert body["status_code"] == 422
            assert body["error_type"] == "validation_error"

            # detail must be a list of field-level errors
            assert isinstance(body["detail"], list)
            assert len(body["detail"]) >= 1

            # Each error entry must have field, location, message
            for error in body["detail"]:
                assert "field" in error
                assert "location" in error
                assert "message" in error


class TestServerErrorSanitization:
    """
    Property 13 (server_error sanitization): Server errors (500) SHALL NOT
    expose stack traces, file paths, or SQL queries in the detail field.
    """

    @given(message=sensitive_exception_messages)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_500_never_exposes_sensitive_info(self, message: str):
        """
        For any unhandled exception (regardless of its message content),
        the 500 response detail must NOT contain sensitive patterns.
        """
        app = _create_error_test_app(error_message=message)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/trigger-server-error")

            assert resp.status_code == 500
            body = resp.json()

            # Must have the standard three-field structure
            assert set(body.keys()) == {"detail", "status_code", "error_type"}
            assert body["status_code"] == 500
            assert body["error_type"] == "server_error"
            assert isinstance(body["detail"], str)

            # The detail must NOT contain any sensitive patterns
            detail = body["detail"]
            for pattern in SENSITIVE_PATTERNS:
                assert pattern not in detail, (
                    f"500 response detail exposed sensitive pattern '{pattern}': {detail!r}"
                )

    @given(message=sensitive_exception_messages)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_500_detail_is_generic_message(self, message: str):
        """
        For any unhandled exception, the 500 response detail should be a
        generic sanitized message, not the original exception message.
        """
        app = _create_error_test_app(error_message=message)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/trigger-server-error")

            assert resp.status_code == 500
            body = resp.json()

            # The detail should NOT be the raw exception message
            # (unless the message happens to be the generic sanitized message)
            if message != "An internal server error occurred":
                assert body["detail"] != message, (
                    f"500 response leaked the raw exception message: {message!r}"
                )
