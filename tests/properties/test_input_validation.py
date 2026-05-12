# Feature: sbms-api-endpoints, Property 14: Input Validation Rejection
"""
Property-based tests for input validation rejection.

For any endpoint that accepts a request body, if a required field violates its
constraints (string length outside bounds, missing required field, invalid enum
value, page_size < 1 or page < 1), the API SHALL return HTTP 422 with
`error_type` "validation_error" and field-level error details identifying the
failing field.

**Validates: Requirements 2.13, 3.7, 5.9, 5.11, 6.10, 13.11, 20.5, 21.2**
"""

import pytest
from fastapi import FastAPI, Depends, Query
from fastapi.testclient import TestClient
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.schemas.grade_levels import GradeLevelCreate
from app.schemas.subjects import SubjectCreate
from app.schemas.departments import DepartmentCreate
from app.schemas.auth import UserRegisterRequest
from app.schemas.book_copies import BookCopyConditionUpdate
from app.core.pagination import PaginationParams
from app.core.exceptions import register_exception_handlers


# ---------------------------------------------------------------------------
# Minimal test FastAPI app with representative endpoints
# ---------------------------------------------------------------------------


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with representative endpoints for validation testing."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/grade-levels", status_code=201)
    def create_grade_level(payload: GradeLevelCreate):
        return {"id": 1, "name": payload.name}

    @app.post("/subjects", status_code=201)
    def create_subject(payload: SubjectCreate):
        return {"id": 1, "name": payload.name}

    @app.post("/departments", status_code=201)
    def create_department(payload: DepartmentCreate):
        return {"id": 1, "name": payload.name}

    @app.post("/auth/register", status_code=201)
    def register_user(payload: UserRegisterRequest):
        return {"id": 1, "email": payload.email, "full_name": payload.full_name}

    @app.put("/book-copies/{copy_id}/condition")
    def update_condition(copy_id: int, payload: BookCopyConditionUpdate):
        return {"id": copy_id, "condition": payload.condition}

    @app.get("/items")
    def list_items(params: PaginationParams = Depends()):
        return {"page": params.page, "page_size": params.page_size, "items": []}

    return app


_app = _create_test_app()
_client = TestClient(_app)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strings that are empty (violate min_length=1)
empty_strings = st.just("")

# Strings exceeding 100 characters (violate max_length=100 for grade levels/subjects)
over_100_chars = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=101,
    max_size=200,
)

# Strings exceeding 200 characters (violate max_length=200 for departments)
over_200_chars = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=201,
    max_size=400,
)

# Passwords shorter than 8 characters (violate min_length=8)
short_passwords = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=7,
)

# Invalid enum values for book condition (not in the allowed set)
valid_conditions = {"excellent", "good", "fair", "poor", "unusable"}
invalid_conditions = st.text(
    alphabet=st.characters(whitelist_categories=("L",)),
    min_size=1,
    max_size=20,
).filter(lambda s: s.lower() not in valid_conditions)

# Invalid pagination values (page < 1 or page_size < 1)
invalid_page_numbers = st.integers(max_value=0)
invalid_page_sizes = st.integers(max_value=0)


# ---------------------------------------------------------------------------
# Helper assertions
# ---------------------------------------------------------------------------


def assert_422_validation_error(response, expected_field: str):
    """Assert response is 422 with validation_error type and identifies the field."""
    assert response.status_code == 422, (
        f"Expected 422, got {response.status_code}: {response.json()}"
    )
    body = response.json()
    assert body["status_code"] == 422
    assert body["error_type"] == "validation_error"
    # detail should contain field-level errors
    detail = body["detail"]
    assert isinstance(detail, list), f"Expected detail to be a list, got: {detail}"
    assert len(detail) > 0, "Expected at least one field error"
    # At least one error should reference the expected field
    fields_reported = [err.get("field", "") for err in detail]
    assert any(expected_field in f for f in fields_reported), (
        f"Expected field '{expected_field}' in error details, got fields: {fields_reported}"
    )


# ---------------------------------------------------------------------------
# Test Scenario 1: Grade level / subject name validation
# ---------------------------------------------------------------------------


class TestGradeLevelNameValidation:
    """Grade level name: empty string or > 100 chars → 422."""

    @given(name=empty_strings)
    @settings(max_examples=100, deadline=None)
    def test_empty_grade_level_name_rejected(self, name: str):
        """Empty grade level name must be rejected with 422."""
        response = _client.post("/grade-levels", json={"name": name})
        assert_422_validation_error(response, "name")

    @given(name=over_100_chars)
    @settings(max_examples=100, deadline=None)
    def test_too_long_grade_level_name_rejected(self, name: str):
        """Grade level name > 100 chars must be rejected with 422."""
        response = _client.post("/grade-levels", json={"name": name})
        assert_422_validation_error(response, "name")


class TestSubjectNameValidation:
    """Subject name: empty string or > 100 chars → 422."""

    @given(name=empty_strings)
    @settings(max_examples=100, deadline=None)
    def test_empty_subject_name_rejected(self, name: str):
        """Empty subject name must be rejected with 422."""
        response = _client.post("/subjects", json={"name": name})
        assert_422_validation_error(response, "name")

    @given(name=over_100_chars)
    @settings(max_examples=100, deadline=None)
    def test_too_long_subject_name_rejected(self, name: str):
        """Subject name > 100 chars must be rejected with 422."""
        response = _client.post("/subjects", json={"name": name})
        assert_422_validation_error(response, "name")


# ---------------------------------------------------------------------------
# Test Scenario 2: Department name validation
# ---------------------------------------------------------------------------


class TestDepartmentNameValidation:
    """Department name: empty string or > 200 chars → 422."""

    @given(name=empty_strings)
    @settings(max_examples=100, deadline=None)
    def test_empty_department_name_rejected(self, name: str):
        """Empty department name must be rejected with 422."""
        response = _client.post("/departments", json={"name": name})
        assert_422_validation_error(response, "name")

    @given(name=over_200_chars)
    @settings(max_examples=100, deadline=None)
    def test_too_long_department_name_rejected(self, name: str):
        """Department name > 200 chars must be rejected with 422."""
        response = _client.post("/departments", json={"name": name})
        assert_422_validation_error(response, "name")


# ---------------------------------------------------------------------------
# Test Scenario 3: Auth register validation
# ---------------------------------------------------------------------------


class TestAuthRegisterPasswordValidation:
    """Auth register: password < 8 chars → 422."""

    @given(password=short_passwords)
    @settings(max_examples=100, deadline=None)
    def test_short_password_rejected(self, password: str):
        """Password shorter than 8 characters must be rejected with 422."""
        response = _client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": password,
                "full_name": "Test User",
            },
        )
        assert_422_validation_error(response, "password")


class TestAuthRegisterMissingFields:
    """Auth register: missing email/password/full_name → 422."""

    @given(data=st.fixed_dictionaries({
        "full_name": st.just("Test User"),
        "password": st.just("validpass123"),
    }))
    @settings(max_examples=100, deadline=None)
    def test_missing_email_rejected(self, data: dict):
        """Missing email field must be rejected with 422."""
        response = _client.post("/auth/register", json=data)
        assert_422_validation_error(response, "email")

    @given(data=st.fixed_dictionaries({
        "email": st.just("test@example.com"),
        "full_name": st.just("Test User"),
    }))
    @settings(max_examples=100, deadline=None)
    def test_missing_password_rejected(self, data: dict):
        """Missing password field must be rejected with 422."""
        response = _client.post("/auth/register", json=data)
        assert_422_validation_error(response, "password")

    @given(data=st.fixed_dictionaries({
        "email": st.just("test@example.com"),
        "password": st.just("validpass123"),
    }))
    @settings(max_examples=100, deadline=None)
    def test_missing_full_name_rejected(self, data: dict):
        """Missing full_name field must be rejected with 422."""
        response = _client.post("/auth/register", json=data)
        assert_422_validation_error(response, "full_name")


# ---------------------------------------------------------------------------
# Test Scenario 4: Book copies condition — invalid enum value
# ---------------------------------------------------------------------------


class TestBookCopyConditionValidation:
    """Book copies condition: invalid enum value → 422."""

    @given(condition=invalid_conditions)
    @settings(max_examples=100, deadline=None)
    def test_invalid_condition_enum_rejected(self, condition: str):
        """Invalid book condition enum value must be rejected with 422."""
        response = _client.put(
            "/book-copies/1/condition",
            json={"condition": condition},
        )
        assert_422_validation_error(response, "condition")


# ---------------------------------------------------------------------------
# Test Scenario 5: Pagination — page < 1 or page_size < 1
# ---------------------------------------------------------------------------


class TestPaginationValidation:
    """Pagination: page < 1 or page_size < 1 → 422."""

    @given(page=invalid_page_numbers)
    @settings(max_examples=100, deadline=None)
    def test_page_less_than_one_rejected(self, page: int):
        """page < 1 must be rejected with 422."""
        response = _client.get("/items", params={"page": page})
        assert response.status_code == 422, (
            f"Expected 422 for page={page}, got {response.status_code}: {response.json()}"
        )
        body = response.json()
        assert body["status_code"] == 422
        assert body["error_type"] == "validation_error"
        detail = body["detail"]
        assert isinstance(detail, list)
        assert len(detail) > 0
        fields_reported = [err.get("field", "") for err in detail]
        assert any("page" in f for f in fields_reported), (
            f"Expected 'page' in error fields, got: {fields_reported}"
        )

    @given(page_size=invalid_page_sizes)
    @settings(max_examples=100, deadline=None)
    def test_page_size_less_than_one_rejected(self, page_size: int):
        """page_size < 1 must be rejected with 422."""
        response = _client.get("/items", params={"page_size": page_size})
        assert response.status_code == 422, (
            f"Expected 422 for page_size={page_size}, got {response.status_code}: {response.json()}"
        )
        body = response.json()
        assert body["status_code"] == 422
        assert body["error_type"] == "validation_error"
        detail = body["detail"]
        assert isinstance(detail, list)
        assert len(detail) > 0
        fields_reported = [err.get("field", "") for err in detail]
        assert any("page_size" in f for f in fields_reported), (
            f"Expected 'page_size' in error fields, got: {fields_reported}"
        )
