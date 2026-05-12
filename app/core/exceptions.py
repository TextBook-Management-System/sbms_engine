"""
Standardized error handling for the SBMS API.

Provides a custom exception hierarchy and global exception handlers
that ensure all error responses follow the format:
    {"detail": "...", "status_code": <int>, "error_type": "<type>"}

Error types: validation_error, not_found, conflict, unauthorized, forbidden, server_error
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import traceback

logger = logging.getLogger(__name__)


# --- Custom Exception Hierarchy ---


class APIError(Exception):
    """Base exception for all API errors."""

    def __init__(self, status_code: int, detail: str, error_type: str):
        self.status_code = status_code
        self.detail = detail
        self.error_type = error_type
        super().__init__(detail)


class NotFoundError(APIError):
    """Raised when a requested resource does not exist (404)."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=404, detail=detail, error_type="not_found")


class ConflictError(APIError):
    """Raised on unique constraint violations or invalid state transitions (409)."""

    def __init__(self, detail: str = "Conflict"):
        super().__init__(status_code=409, detail=detail, error_type="conflict")


class ValidationError(APIError):
    """Raised for business-level validation failures (422)."""

    def __init__(self, detail: str = "Validation error"):
        super().__init__(status_code=422, detail=detail, error_type="validation_error")


class ForbiddenError(APIError):
    """Raised when the user lacks permission for the action (403)."""

    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=403, detail=detail, error_type="forbidden")


class UnauthorizedError(APIError):
    """Raised when authentication is missing or invalid (401)."""

    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=401, detail=detail, error_type="unauthorized")


# --- Exception Handlers ---


async def _api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom APIError exceptions with structured JSON."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
            "error_type": exc.error_type,
        },
    )


async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic/FastAPI request validation errors with field-level details."""
    errors = []
    for error in exc.errors():
        field_location = error.get("loc", [])
        # loc is a tuple like ("body", "field_name") or ("query", "param")
        location = field_location[0] if len(field_location) > 0 else "unknown"
        field = ".".join(str(part) for part in field_location[1:]) if len(field_location) > 1 else "unknown"
        errors.append({
            "field": field,
            "location": location,
            "message": error.get("msg", "Invalid value"),
        })

    return JSONResponse(
        status_code=422,
        content={
            "detail": errors,
            "status_code": 422,
            "error_type": "validation_error",
        },
    )


async def _integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    """Handle SQLAlchemy IntegrityError as a 409 conflict."""
    logger.error(f"Database integrity error: {exc}")
    # Extract a safe message without exposing SQL internals
    detail = "A database constraint was violated"
    orig = getattr(exc, "orig", None)
    if orig:
        orig_str = str(orig)
        if "Duplicate entry" in orig_str or "UNIQUE constraint" in orig_str:
            detail = "A record with the given unique value already exists"
        elif "foreign key" in orig_str.lower() or "FOREIGN KEY" in orig_str:
            detail = "A referenced record does not exist or cannot be removed due to existing references"

    return JSONResponse(
        status_code=409,
        content={
            "detail": detail,
            "status_code": 409,
            "error_type": "conflict",
        },
    )


async def _generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with a sanitized 500 response."""
    # Log full details for debugging
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)

    # Return sanitized message — never expose stack traces, file paths, or SQL queries
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred",
            "status_code": 500,
            "error_type": "server_error",
        },
    )


# --- Catch-All Middleware ---


class CatchAllExceptionMiddleware(BaseHTTPMiddleware):
    """Middleware that catches any unhandled exception and returns a sanitized 500 response.

    This is needed because Starlette's ServerErrorMiddleware re-raises exceptions
    that propagate past the ExceptionMiddleware in newer versions.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Log full details for debugging
            logger.error(
                f"Unhandled exception on {request.method} {request.url}: {exc}",
                exc_info=True,
            )
            # Return sanitized message
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An internal server error occurred",
                    "status_code": 500,
                    "error_type": "server_error",
                },
            )


# --- Registration ---


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI application."""
    app.add_exception_handler(APIError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(IntegrityError, _integrity_error_handler)
    app.add_exception_handler(Exception, _generic_exception_handler)
    # Add catch-all middleware as a safety net for exceptions that bypass handlers
    app.add_middleware(CatchAllExceptionMiddleware)
