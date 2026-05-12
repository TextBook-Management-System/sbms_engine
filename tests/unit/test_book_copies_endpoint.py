"""Unit tests for app.api.v1.endpoints.book_copies module.

Tests the book copies and QR tracking endpoint handlers with mocked DB sessions,
validating requirements 13.1–13.11.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams
from app.models.database import Book, BookCopy, School
from app.api.v1.endpoints.book_copies import (
    _validate_book_exists,
    _validate_school_exists,
    create_book_copy,
    list_book_copies,
    get_book_copy_by_qr,
    get_book_copy,
    update_book_copy_condition,
)
from app.schemas.book_copies import (
    BookCondition,
    BookCopyConditionUpdate,
    BookCopyCreate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book_copy(**overrides):
    """Create a fake BookCopy instance with default values."""
    defaults = {
        "id": 1,
        "book_id": 10,
        "school_id": 20,
        "qr_code": "QR-ABC-123",
        "condition": "good",
        "created_at": datetime(2024, 1, 1, 12, 0, 0),
    }
    defaults.update(overrides)
    copy = MagicMock(spec=BookCopy)
    for key, value in defaults.items():
        setattr(copy, key, value)
    return copy


# ---------------------------------------------------------------------------
# FK Validation Tests
# ---------------------------------------------------------------------------


class TestValidateBookExists:
    """Tests for _validate_book_exists helper."""

    def test_book_exists_no_error(self):
        """No error raised when book exists."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        # Should not raise
        _validate_book_exists(db, 10)

    def test_book_not_exists_raises_validation_error(self):
        """Raises ValidationError (422) when book does not exist.

        Validates: Requirement 13.9
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValidationError) as exc_info:
            _validate_book_exists(db, 999)

        assert "book" in exc_info.value.detail.lower()


class TestValidateSchoolExists:
    """Tests for _validate_school_exists helper."""

    def test_school_exists_no_error(self):
        """No error raised when school exists."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        # Should not raise
        _validate_school_exists(db, 20)

    def test_school_not_exists_raises_validation_error(self):
        """Raises ValidationError (422) when school does not exist.

        Validates: Requirement 13.9
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValidationError) as exc_info:
            _validate_school_exists(db, 999)

        assert "school" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Create Book Copy Tests
# ---------------------------------------------------------------------------


class TestCreateBookCopy:
    """Tests for create_book_copy endpoint handler."""

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_create_book_copy_success(self, mock_crud):
        """Creates a book copy with default condition 'good'.

        Validates: Requirement 13.1
        """
        db = MagicMock()
        # Both FKs exist
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        expected_copy = _make_book_copy()
        mock_crud.create.return_value = expected_copy

        payload = BookCopyCreate(book_id=10, school_id=20, qr_code="QR-ABC-123")

        result = create_book_copy(payload, db)

        assert result == expected_copy
        # Verify condition defaults to "good"
        call_args = mock_crud.create.call_args
        data_arg = call_args[0][2]  # Third positional arg is data dict
        assert data_arg["condition"] == "good"
        assert call_args[1]["unique_fields"] == ["qr_code"]

    def test_create_book_copy_invalid_book_id(self):
        """Returns 422 when book_id does not exist.

        Validates: Requirement 13.9
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        payload = BookCopyCreate(book_id=999, school_id=20, qr_code="QR-XYZ")

        with pytest.raises(ValidationError) as exc_info:
            create_book_copy(payload, db)

        assert "book" in exc_info.value.detail.lower()

    def test_create_book_copy_invalid_school_id(self):
        """Returns 422 when school_id does not exist.

        Validates: Requirement 13.9
        """
        db = MagicMock()
        # Book exists
        book_query = MagicMock()
        book_query.filter.return_value.first.return_value = MagicMock()
        # School does not exist
        school_query = MagicMock()
        school_query.filter.return_value.first.return_value = None

        db.query.side_effect = [book_query, school_query]

        payload = BookCopyCreate(book_id=10, school_id=999, qr_code="QR-XYZ")

        with pytest.raises(ValidationError) as exc_info:
            create_book_copy(payload, db)

        assert "school" in exc_info.value.detail.lower()

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_create_book_copy_duplicate_qr_code(self, mock_crud):
        """Returns 409 when QR code already exists.

        Validates: Requirement 13.8
        """
        db = MagicMock()
        # Both FKs exist
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        mock_crud.create.side_effect = ConflictError(
            "A record with this qr code already exists"
        )

        payload = BookCopyCreate(book_id=10, school_id=20, qr_code="DUPLICATE-QR")

        with pytest.raises(ConflictError) as exc_info:
            create_book_copy(payload, db)

        assert "qr code" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# List Book Copies Tests
# ---------------------------------------------------------------------------


class TestListBookCopies:
    """Tests for list_book_copies endpoint handler."""

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_list_no_filters(self, mock_crud):
        """Returns paginated list of all book copies.

        Validates: Requirement 13.6, 13.7
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        expected = PaginatedResponse(
            items=[_make_book_copy()], total=1, page=1, page_size=20
        )
        mock_crud.get_all.return_value = expected

        result = list_book_copies(school_id=None, book_id=None, params=params, db=db)

        assert result == expected
        mock_crud.get_all.assert_called_once_with(
            db, BookCopy, params, filters={"school_id": None, "book_id": None}
        )

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_list_filter_by_school_id(self, mock_crud):
        """Filters book copies by school_id.

        Validates: Requirement 13.6
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        expected = PaginatedResponse(
            items=[_make_book_copy()], total=1, page=1, page_size=20
        )
        mock_crud.get_all.return_value = expected

        result = list_book_copies(school_id=20, book_id=None, params=params, db=db)

        mock_crud.get_all.assert_called_once_with(
            db, BookCopy, params, filters={"school_id": 20, "book_id": None}
        )

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_list_filter_by_book_id(self, mock_crud):
        """Filters book copies by book_id.

        Validates: Requirement 13.7
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        expected = PaginatedResponse(
            items=[_make_book_copy()], total=1, page=1, page_size=20
        )
        mock_crud.get_all.return_value = expected

        result = list_book_copies(school_id=None, book_id=10, params=params, db=db)

        mock_crud.get_all.assert_called_once_with(
            db, BookCopy, params, filters={"school_id": None, "book_id": 10}
        )

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_list_filter_by_both(self, mock_crud):
        """Filters book copies by both school_id and book_id.

        Validates: Requirement 13.6, 13.7
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        expected = PaginatedResponse(
            items=[_make_book_copy()], total=1, page=1, page_size=20
        )
        mock_crud.get_all.return_value = expected

        result = list_book_copies(school_id=20, book_id=10, params=params, db=db)

        mock_crud.get_all.assert_called_once_with(
            db, BookCopy, params, filters={"school_id": 20, "book_id": 10}
        )


# ---------------------------------------------------------------------------
# Get Book Copy by QR Code Tests
# ---------------------------------------------------------------------------


class TestGetBookCopyByQR:
    """Tests for get_book_copy_by_qr endpoint handler."""

    def test_get_by_qr_found(self):
        """Returns the book copy when QR code matches.

        Validates: Requirement 13.3
        """
        db = MagicMock()
        expected_copy = _make_book_copy(qr_code="QR-FOUND")
        db.query.return_value.filter.return_value.first.return_value = expected_copy

        result = get_book_copy_by_qr("QR-FOUND", db)

        assert result == expected_copy

    def test_get_by_qr_not_found(self):
        """Returns 404 when no book copy matches the QR code.

        Validates: Requirement 13.4
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            get_book_copy_by_qr("QR-MISSING", db)

        assert "QR-MISSING" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Get Book Copy by ID Tests
# ---------------------------------------------------------------------------


class TestGetBookCopy:
    """Tests for get_book_copy endpoint handler."""

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_get_by_id_found(self, mock_crud):
        """Returns the book copy when it exists.

        Validates: Requirement 13.2
        """
        expected_copy = _make_book_copy()
        mock_crud.get_by_id.return_value = expected_copy
        db = MagicMock()

        result = get_book_copy(1, db)

        assert result == expected_copy
        mock_crud.get_by_id.assert_called_once_with(db, BookCopy, 1)

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_get_by_id_not_found(self, mock_crud):
        """Returns 404 when book copy does not exist.

        Validates: Requirement 13.10
        """
        mock_crud.get_by_id.side_effect = NotFoundError(
            "BookCopy with id 999 not found"
        )
        db = MagicMock()

        with pytest.raises(NotFoundError) as exc_info:
            get_book_copy(999, db)

        assert "999" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Update Book Copy Condition Tests
# ---------------------------------------------------------------------------


class TestUpdateBookCopyCondition:
    """Tests for update_book_copy_condition endpoint handler."""

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_update_condition_success(self, mock_crud):
        """Updates the condition of a book copy.

        Validates: Requirement 13.5
        """
        db = MagicMock()
        updated_copy = _make_book_copy(condition="excellent")
        mock_crud.update.return_value = updated_copy

        payload = BookCopyConditionUpdate(condition=BookCondition.EXCELLENT)

        result = update_book_copy_condition(1, payload, db)

        assert result == updated_copy
        mock_crud.update.assert_called_once_with(
            db, BookCopy, 1, {"condition": "excellent"}
        )

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_update_condition_not_found(self, mock_crud):
        """Returns 404 when book copy does not exist.

        Validates: Requirement 13.10
        """
        db = MagicMock()
        mock_crud.update.side_effect = NotFoundError(
            "BookCopy with id 999 not found"
        )

        payload = BookCopyConditionUpdate(condition=BookCondition.POOR)

        with pytest.raises(NotFoundError):
            update_book_copy_condition(999, payload, db)

    def test_update_condition_invalid_value(self):
        """Returns 422 when condition value is not in allowed set.

        Validates: Requirement 13.11
        Note: Pydantic enum validation handles this at the schema level.
        """
        with pytest.raises(ValueError):
            BookCopyConditionUpdate(condition="invalid_condition")

    @patch("app.api.v1.endpoints.book_copies.crud_service")
    def test_update_condition_all_valid_values(self, mock_crud):
        """All valid condition values are accepted.

        Validates: Requirement 13.5
        """
        db = MagicMock()
        mock_crud.update.return_value = _make_book_copy()

        for condition in BookCondition:
            payload = BookCopyConditionUpdate(condition=condition)
            update_book_copy_condition(1, payload, db)

        # Should have been called once for each valid condition
        assert mock_crud.update.call_count == len(BookCondition)
