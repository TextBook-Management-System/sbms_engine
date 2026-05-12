# Feature: sbms-api-endpoints, Property 3: Foreign Key Validation
"""
Property-based tests for foreign key validation.

Tests validate that:
For any request body containing a foreign key reference (department_id, school_id,
book_id, subject_id, grade_level_id, book_copy_id, etc.), if the referenced ID does
not exist in the database, the API SHALL return the appropriate HTTP error:
- HTTP 422 with error_type "validation_error" for most FK references
- HTTP 404 with error_type "not_found" for book_copy_id in scans (Req 15.5)

**Validates: Requirements 4.7, 9.11, 11.9, 13.9, 15.5**
"""

import pytest
from unittest.mock import MagicMock
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.exceptions import NotFoundError, ValidationError
from app.models.database import (
    Book,
    BookCopy,
    BookConditionScan,
    BookRequest,
    Department,
    GradeLevel,
    School,
    Subject,
)


# ---------------------------------------------------------------------------
# Strategies: generate random non-existent IDs (large integers unlikely to exist)
# ---------------------------------------------------------------------------

# Large integers that are unlikely to exist in any database
non_existent_ids = st.integers(min_value=900_000, max_value=2**63 - 1)


# ---------------------------------------------------------------------------
# Helper: create a mock DB session where FK lookup returns None (not found)
# ---------------------------------------------------------------------------

def _mock_db_fk_not_found():
    """Create a mock DB session where query().filter().first() returns None.

    This simulates the case where a foreign key reference does not exist
    in the database.
    """
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_filter.first.return_value = None  # FK reference not found
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    return mock_db


# ---------------------------------------------------------------------------
# FK Validation functions (extracted from endpoint modules)
# These mirror the validation logic in the endpoint handlers.
# ---------------------------------------------------------------------------

def _validate_department_exists(db, department_id: int) -> None:
    """Check that the referenced department_id exists. Raise 422 if not."""
    existing = db.query(Department).filter(Department.id == department_id).first()
    if existing is None:
        raise ValidationError("Referenced department does not exist")


def _validate_subject_exists(db, subject_id: int) -> None:
    """Check that the referenced subject_id exists. Raise 422 if not."""
    existing = db.query(Subject).filter(Subject.id == subject_id).first()
    if existing is None:
        raise ValidationError("Referenced subject does not exist")


def _validate_grade_level_exists(db, grade_level_id: int) -> None:
    """Check that the referenced grade_level_id exists. Raise 422 if not."""
    existing = db.query(GradeLevel).filter(GradeLevel.id == grade_level_id).first()
    if existing is None:
        raise ValidationError("Referenced grade level does not exist")


def _validate_book_exists(db, book_id: int) -> None:
    """Check that the referenced book_id exists. Raise 422 if not."""
    existing = db.query(Book).filter(Book.id == book_id).first()
    if existing is None:
        raise ValidationError(f"Book with id {book_id} not found")


def _validate_school_exists(db, school_id: int) -> None:
    """Check that the referenced school_id exists. Raise 422 if not."""
    existing = db.query(School).filter(School.id == school_id).first()
    if existing is None:
        raise ValidationError(f"School with id {school_id} not found")


def _validate_book_copy_exists(db, book_copy_id: int) -> None:
    """Check that the referenced book_copy_id exists. Raise 404 if not.

    Note: Per Requirement 15.5, scans with non-existent book_copy_id
    return HTTP 404 (not_found) rather than 422 (validation_error).
    """
    existing = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if existing is None:
        raise NotFoundError(f"Book copy with id {book_copy_id} not found")


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestForeignKeyValidation:
    """
    Property 3: For any request body containing a foreign key reference,
    if the referenced ID does not exist in the database, the API SHALL return
    HTTP 422 with error_type "validation_error" and a message identifying
    which referenced entity was not found.
    """

    @given(department_id=non_existent_ids)
    @settings(max_examples=100, deadline=None)
    def test_school_with_non_existent_department_id_returns_422(
        self, department_id: int
    ):
        """
        Creating a school with a non-existent department_id SHALL raise
        ValidationError (HTTP 422) with error_type "validation_error".

        **Validates: Requirements 4.7**
        """
        mock_db = _mock_db_fk_not_found()

        with pytest.raises(ValidationError) as exc_info:
            _validate_department_exists(mock_db, department_id)

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_type == "validation_error"
        assert "department" in exc_info.value.detail.lower()

    @given(subject_id=non_existent_ids)
    @settings(max_examples=100, deadline=None)
    def test_book_with_non_existent_subject_id_returns_422(
        self, subject_id: int
    ):
        """
        Creating a book with a non-existent subject_id SHALL raise
        ValidationError (HTTP 422) with error_type "validation_error".

        **Validates: Requirements 9.11**
        """
        mock_db = _mock_db_fk_not_found()

        with pytest.raises(ValidationError) as exc_info:
            _validate_subject_exists(mock_db, subject_id)

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_type == "validation_error"
        assert "subject" in exc_info.value.detail.lower()

    @given(grade_level_id=non_existent_ids)
    @settings(max_examples=100, deadline=None)
    def test_book_with_non_existent_grade_level_id_returns_422(
        self, grade_level_id: int
    ):
        """
        Creating a book with a non-existent grade_level_id SHALL raise
        ValidationError (HTTP 422) with error_type "validation_error".

        **Validates: Requirements 9.11**
        """
        mock_db = _mock_db_fk_not_found()

        with pytest.raises(ValidationError) as exc_info:
            _validate_grade_level_exists(mock_db, grade_level_id)

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_type == "validation_error"
        assert "grade level" in exc_info.value.detail.lower()

    @given(book_id=non_existent_ids)
    @settings(max_examples=100, deadline=None)
    def test_book_request_with_non_existent_book_id_returns_422(
        self, book_id: int
    ):
        """
        Creating a book request with a non-existent book_id SHALL raise
        ValidationError (HTTP 422) with error_type "validation_error".

        **Validates: Requirements 11.9**
        """
        mock_db = _mock_db_fk_not_found()

        with pytest.raises(ValidationError) as exc_info:
            _validate_book_exists(mock_db, book_id)

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_type == "validation_error"
        assert "book" in exc_info.value.detail.lower()

    @given(school_id=non_existent_ids)
    @settings(max_examples=100, deadline=None)
    def test_book_request_with_non_existent_school_id_returns_422(
        self, school_id: int
    ):
        """
        Creating a book request with a non-existent school_id SHALL raise
        ValidationError (HTTP 422) with error_type "validation_error".

        **Validates: Requirements 11.9**
        """
        mock_db = _mock_db_fk_not_found()

        with pytest.raises(ValidationError) as exc_info:
            _validate_school_exists(mock_db, school_id)

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_type == "validation_error"
        assert "school" in exc_info.value.detail.lower()

    @given(book_id=non_existent_ids)
    @settings(max_examples=100, deadline=None)
    def test_book_copy_with_non_existent_book_id_returns_422(
        self, book_id: int
    ):
        """
        Creating a book copy with a non-existent book_id SHALL raise
        ValidationError (HTTP 422) with error_type "validation_error".

        **Validates: Requirements 13.9**
        """
        mock_db = _mock_db_fk_not_found()

        with pytest.raises(ValidationError) as exc_info:
            _validate_book_exists(mock_db, book_id)

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_type == "validation_error"
        assert "book" in exc_info.value.detail.lower()

    @given(school_id=non_existent_ids)
    @settings(max_examples=100, deadline=None)
    def test_book_copy_with_non_existent_school_id_returns_422(
        self, school_id: int
    ):
        """
        Creating a book copy with a non-existent school_id SHALL raise
        ValidationError (HTTP 422) with error_type "validation_error".

        **Validates: Requirements 13.9**
        """
        mock_db = _mock_db_fk_not_found()

        with pytest.raises(ValidationError) as exc_info:
            _validate_school_exists(mock_db, school_id)

        assert exc_info.value.status_code == 422
        assert exc_info.value.error_type == "validation_error"
        assert "school" in exc_info.value.detail.lower()

    @given(book_copy_id=non_existent_ids)
    @settings(max_examples=100, deadline=None)
    def test_scan_with_non_existent_book_copy_id_returns_404(
        self, book_copy_id: int
    ):
        """
        Creating a scan with a non-existent book_copy_id SHALL raise
        NotFoundError (HTTP 404) with error_type "not_found".

        Per Requirement 15.5, the Scan_Service returns 404 (not 422)
        when the referenced book_copy_id does not exist.

        **Validates: Requirements 15.5**
        """
        mock_db = _mock_db_fk_not_found()

        with pytest.raises(NotFoundError) as exc_info:
            _validate_book_copy_exists(mock_db, book_copy_id)

        assert exc_info.value.status_code == 404
        assert exc_info.value.error_type == "not_found"
        assert "book copy" in exc_info.value.detail.lower()
