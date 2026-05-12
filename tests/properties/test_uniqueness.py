# Feature: sbms-api-endpoints, Property 2: Uniqueness Constraint Enforcement
"""
Property-based tests for uniqueness constraint enforcement.

Tests validate that:
For any entity with a unique field (grade level name, subject name, user email,
book ISBN, book copy QR code, AI model name+version), if a record already exists
with that unique value, then a subsequent create attempting to use the same value
SHALL raise ConflictError (409).

**Validates: Requirements 2.13, 5.5, 9.10, 13.8, 14.8**
"""

import pytest
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.exceptions import ConflictError
from app.services import crud_service
from app.models.database import (
    GradeLevel,
    Subject,
    User,
    Book,
    BookCopy,
    AIModelVersion,
)


# ---------------------------------------------------------------------------
# Strategies: generate random unique field values for each entity type
# ---------------------------------------------------------------------------

# Grade level names: non-empty strings up to 100 chars
grade_level_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Subject names: non-empty strings up to 100 chars
subject_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# User emails: valid-looking email strings
user_emails = st.from_regex(
    r"[a-z][a-z0-9]{1,20}@[a-z]{2,10}\.[a-z]{2,5}", fullmatch=True
)

# Book ISBNs: non-empty strings up to 50 chars (ISBN-like)
book_isbns = st.from_regex(r"[0-9]{10,13}", fullmatch=True)

# Book copy QR codes: non-empty strings up to 255 chars
qr_codes = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# AI model names and versions
ai_model_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

ai_model_versions = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# Helper: create a mock DB session that simulates an existing record
# ---------------------------------------------------------------------------

def _mock_db_with_existing_record():
    """Create a mock DB session where query().filter().first() returns a truthy value."""
    mock_db = MagicMock()
    # Chain: db.query(model).filter(...).filter(...).first() returns an existing record
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_filter.first.return_value = MagicMock()  # Simulates existing record found
    mock_filter.filter.return_value = mock_filter  # For chained .filter() calls
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query
    return mock_db


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestUniquenessConstraintEnforcement:
    """
    Property 2: For any entity with a unique field, if a record already exists
    with that unique value, then a subsequent create attempting to use the same
    value SHALL raise ConflictError (409).
    """

    @given(name=grade_level_names)
    @settings(max_examples=100, deadline=None)
    def test_grade_level_duplicate_name_raises_conflict(self, name: str):
        """
        Creating a grade level with a name that already exists SHALL raise ConflictError.

        **Validates: Requirements 2.13**
        """
        mock_db = _mock_db_with_existing_record()

        with pytest.raises(ConflictError) as exc_info:
            crud_service.create(
                db=mock_db,
                model_class=GradeLevel,
                data={"name": name},
                unique_fields=["name"],
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"

    @given(name=subject_names)
    @settings(max_examples=100, deadline=None)
    def test_subject_duplicate_name_raises_conflict(self, name: str):
        """
        Creating a subject with a name that already exists SHALL raise ConflictError.

        **Validates: Requirements 2.13**
        """
        mock_db = _mock_db_with_existing_record()

        with pytest.raises(ConflictError) as exc_info:
            crud_service.create(
                db=mock_db,
                model_class=Subject,
                data={"name": name},
                unique_fields=["name"],
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"

    @given(email=user_emails)
    @settings(max_examples=100, deadline=None)
    def test_user_duplicate_email_raises_conflict(self, email: str):
        """
        Creating a user with an email that already exists SHALL raise ConflictError.

        **Validates: Requirements 5.5**
        """
        mock_db = _mock_db_with_existing_record()

        with pytest.raises(ConflictError) as exc_info:
            crud_service.create(
                db=mock_db,
                model_class=User,
                data={
                    "email": email,
                    "password_hash": "hashed_pw",
                    "full_name": "Test User",
                },
                unique_fields=["email"],
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"

    @given(isbn=book_isbns)
    @settings(max_examples=100, deadline=None)
    def test_book_duplicate_isbn_raises_conflict(self, isbn: str):
        """
        Creating a book with an ISBN that already exists SHALL raise ConflictError.

        **Validates: Requirements 9.10**
        """
        mock_db = _mock_db_with_existing_record()

        with pytest.raises(ConflictError) as exc_info:
            crud_service.create(
                db=mock_db,
                model_class=Book,
                data={
                    "title": "Test Book",
                    "subject_id": 1,
                    "grade_level_id": 1,
                    "isbn": isbn,
                },
                unique_fields=["isbn"],
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"

    @given(qr_code=qr_codes)
    @settings(max_examples=100, deadline=None)
    def test_book_copy_duplicate_qr_code_raises_conflict(self, qr_code: str):
        """
        Creating a book copy with a QR code that already exists SHALL raise ConflictError.

        **Validates: Requirements 13.8**
        """
        mock_db = _mock_db_with_existing_record()

        with pytest.raises(ConflictError) as exc_info:
            crud_service.create(
                db=mock_db,
                model_class=BookCopy,
                data={
                    "book_id": 1,
                    "school_id": 1,
                    "qr_code": qr_code,
                },
                unique_fields=["qr_code"],
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"

    @given(model_name=ai_model_names, model_version=ai_model_versions)
    @settings(max_examples=100, deadline=None)
    def test_ai_model_duplicate_name_version_raises_conflict(
        self, model_name: str, model_version: str
    ):
        """
        Creating an AI model with a name+version combination that already exists
        SHALL raise ConflictError.

        **Validates: Requirements 14.8**
        """
        mock_db = _mock_db_with_existing_record()

        with pytest.raises(ConflictError) as exc_info:
            crud_service.create(
                db=mock_db,
                model_class=AIModelVersion,
                data={
                    "model_name": model_name,
                    "model_version": model_version,
                    "model_type": "condition_scanner",
                },
                unique_fields=["model_name", "model_version"],
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"
