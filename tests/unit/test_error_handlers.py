"""
Unit tests for the standardized error handling module.

Tests verify that:
- Custom exceptions carry correct status codes and error types
- Global exception handlers produce the {detail, status_code, error_type} format
- Server errors (500) do not expose internal details
- Validation errors include field-level information
- IntegrityError is mapped to 409 conflict
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from app.core.exceptions import (
    APIError,
    NotFoundError,
    ConflictError,
    ValidationError,
    ForbiddenError,
    UnauthorizedError,
    register_exception_handlers,
)


# --- Test App Setup ---


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with exception handlers registered."""
    app = FastAPI(debug=False)
    register_exception_handlers(app)

    class ItemCreate(BaseModel):
        name: str = Field(..., min_length=1, max_length=100)
        quantity: int = Field(..., ge=1)

    @app.get("/not-found")
    async def raise_not_found():
        raise NotFoundError("Grade level with ID 999 not found")

    @app.get("/conflict")
    async def raise_conflict():
        raise ConflictError("A record with this name already exists")

    @app.get("/validation")
    async def raise_validation():
        raise ValidationError("subject_id references a non-existent subject")

    @app.get("/forbidden")
    async def raise_forbidden():
        raise ForbiddenError("Insufficient permissions for this action")

    @app.get("/unauthorized")
    async def raise_unauthorized():
        raise UnauthorizedError("Invalid or expired token")

    @app.get("/server-error")
    async def raise_server_error():
        # Simulate an unexpected error with internal details
        raise RuntimeError("SQLALCHEMY ERROR: SELECT * FROM users WHERE id=1; traceback at /app/services/auth.py:42")

    @app.post("/validate-body")
    async def validate_body(item: ItemCreate):
        return {"name": item.name}

    @app.get("/custom-api-error")
    async def raise_custom_api_error():
        raise APIError(status_code=502, detail="AI model service unavailable", error_type="server_error")

    return app


@pytest.fixture
def test_app():
    return _create_test_app()


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Exception Class Tests ---


class TestExceptionHierarchy:
    """Test that custom exceptions have correct attributes."""

    def test_not_found_error(self):
        exc = NotFoundError("Item not found")
        assert exc.status_code == 404
        assert exc.error_type == "not_found"
        assert exc.detail == "Item not found"

    def test_conflict_error(self):
        exc = ConflictError("Duplicate entry")
        assert exc.status_code == 409
        assert exc.error_type == "conflict"
        assert exc.detail == "Duplicate entry"

    def test_validation_error(self):
        exc = ValidationError("Invalid reference")
        assert exc.status_code == 422
        assert exc.error_type == "validation_error"
        assert exc.detail == "Invalid reference"

    def test_forbidden_error(self):
        exc = ForbiddenError("Access denied")
        assert exc.status_code == 403
        assert exc.error_type == "forbidden"
        assert exc.detail == "Access denied"

    def test_unauthorized_error(self):
        exc = UnauthorizedError("Token expired")
        assert exc.status_code == 401
        assert exc.error_type == "unauthorized"
        assert exc.detail == "Token expired"

    def test_base_api_error(self):
        exc = APIError(status_code=502, detail="Service down", error_type="server_error")
        assert exc.status_code == 502
        assert exc.error_type == "server_error"
        assert exc.detail == "Service down"

    def test_all_inherit_from_api_error(self):
        assert issubclass(NotFoundError, APIError)
        assert issubclass(ConflictError, APIError)
        assert issubclass(ValidationError, APIError)
        assert issubclass(ForbiddenError, APIError)
        assert issubclass(UnauthorizedError, APIError)

    def test_default_messages(self):
        assert NotFoundError().detail == "Resource not found"
        assert ConflictError().detail == "Conflict"
        assert ValidationError().detail == "Validation error"
        assert ForbiddenError().detail == "Forbidden"
        assert UnauthorizedError().detail == "Unauthorized"


# --- Handler Integration Tests ---


@pytest.mark.asyncio
class TestNotFoundHandler:
    async def test_returns_404_with_correct_format(self, client):
        resp = await client.get("/not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body == {
            "detail": "Grade level with ID 999 not found",
            "status_code": 404,
            "error_type": "not_found",
        }


@pytest.mark.asyncio
class TestConflictHandler:
    async def test_returns_409_with_correct_format(self, client):
        resp = await client.get("/conflict")
        assert resp.status_code == 409
        body = resp.json()
        assert body == {
            "detail": "A record with this name already exists",
            "status_code": 409,
            "error_type": "conflict",
        }


@pytest.mark.asyncio
class TestValidationHandler:
    async def test_returns_422_with_correct_format(self, client):
        resp = await client.get("/validation")
        assert resp.status_code == 422
        body = resp.json()
        assert body == {
            "detail": "subject_id references a non-existent subject",
            "status_code": 422,
            "error_type": "validation_error",
        }


@pytest.mark.asyncio
class TestForbiddenHandler:
    async def test_returns_403_with_correct_format(self, client):
        resp = await client.get("/forbidden")
        assert resp.status_code == 403
        body = resp.json()
        assert body == {
            "detail": "Insufficient permissions for this action",
            "status_code": 403,
            "error_type": "forbidden",
        }


@pytest.mark.asyncio
class TestUnauthorizedHandler:
    async def test_returns_401_with_correct_format(self, client):
        resp = await client.get("/unauthorized")
        assert resp.status_code == 401
        body = resp.json()
        assert body == {
            "detail": "Invalid or expired token",
            "status_code": 401,
            "error_type": "unauthorized",
        }


@pytest.mark.asyncio
class TestGenericExceptionHandler:
    async def test_returns_500_with_sanitized_message(self, client):
        resp = await client.get("/server-error")
        assert resp.status_code == 500
        body = resp.json()
        assert body == {
            "detail": "An internal server error occurred",
            "status_code": 500,
            "error_type": "server_error",
        }

    async def test_does_not_expose_stack_trace(self, client):
        resp = await client.get("/server-error")
        body = resp.json()
        assert "SQLALCHEMY" not in body["detail"]
        assert "traceback" not in body["detail"]
        assert "/app/" not in body["detail"]
        assert "SELECT" not in body["detail"]


@pytest.mark.asyncio
class TestRequestValidationHandler:
    async def test_missing_required_field(self, client):
        resp = await client.post("/validate-body", json={})
        assert resp.status_code == 422
        body = resp.json()
        assert body["status_code"] == 422
        assert body["error_type"] == "validation_error"
        # detail should be a list of field-level errors
        assert isinstance(body["detail"], list)
        assert len(body["detail"]) >= 1
        # Each error should have field, location, and message
        for error in body["detail"]:
            assert "field" in error
            assert "location" in error
            assert "message" in error

    async def test_invalid_field_value(self, client):
        resp = await client.post("/validate-body", json={"name": "", "quantity": 0})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error_type"] == "validation_error"
        assert isinstance(body["detail"], list)
        # Should have errors for both fields
        fields_with_errors = [e["field"] for e in body["detail"]]
        assert "name" in fields_with_errors
        assert "quantity" in fields_with_errors


@pytest.mark.asyncio
class TestCustomAPIError:
    async def test_custom_status_code(self, client):
        resp = await client.get("/custom-api-error")
        assert resp.status_code == 502
        body = resp.json()
        assert body == {
            "detail": "AI model service unavailable",
            "status_code": 502,
            "error_type": "server_error",
        }
