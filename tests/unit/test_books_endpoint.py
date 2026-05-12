"""Unit tests for app.api.v1.endpoints.books module.

Tests the books catalog endpoint handlers with mocked DB sessions,
validating requirements 9.1–9.11.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams
from app.models.database import Book, BookCopy, GradeLevel, Subject
from app.api.v1.endpoints.books import (
    _validate_subject_exists,
    _validate_grade_level_exists,
    create_book,
    list_books,
    get_book,
    update_book,
    delete_book,
)
from app.schemas.books import BookCreate, BookUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book(**overrides):
    """Create a fake Book instance with default values."""
    defaults = {
        "id": 1,
        "title": "Test Book",
        "subject_id": 10,
        "grade_level_id": 20,
        "isbn": "978-0-123456-78-9",
        "publisher": "Test Publisher",
        "author": "Test Author",
        "edition": "1st",
        "created_at": datetime(2024, 1, 1, 12, 0, 0),
        "updated_at": datetime(2024, 1, 1, 12, 0, 0),
    }
    defaults.update(overrides)
    book = MagicMock(spec=Book)
    for key, value in defaults.items():
        setattr(book, key, value)
    return book


# ---------------------------------------------------------------------------
# FK Validation Tests
# ---------------------------------------------------------------------------


class TestValidateSubjectExists:
    """Tests for _validate_subject_exists helper."""

    def test_subject_exists_no_error(self):
        """No error raised when subject exists."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        # Should not raise
        _validate_subject_exists(db, 10)

    def test_subject_not_exists_raises_validation_error(self):
        """Raises ValidationError (422) when subject does not exist.

        Validates: Requirement 9.11
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValidationError) as exc_info:
            _validate_subject_exists(db, 999)

        assert "subject" in exc_info.value.detail.lower()


class TestValidateGradeLevelExists:
    """Tests for _validate_grade_level_exists helper."""

    def test_grade_level_exists_no_error(self):
        """No error raised when grade level exists."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        # Should not raise
        _validate_grade_level_exists(db, 20)

    def test_grade_level_not_exists_raises_validation_error(self):
        """Raises ValidationError (422) when grade level does not exist.

        Validates: Requirement 9.11
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValidationError) as exc_info:
            _validate_grade_level_exists(db, 999)

        assert "grade level" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Create Book Tests
# ---------------------------------------------------------------------------


class TestCreateBook:
    """Tests for create_book endpoint handler."""

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_create_book_success(self, mock_crud):
        """Creates a book when all validations pass.

        Validates: Requirement 9.1
        """
        db = MagicMock()
        # Subject exists
        subject_query = MagicMock()
        subject_query.filter.return_value.first.return_value = MagicMock()
        # Grade level exists
        grade_query = MagicMock()
        grade_query.filter.return_value.first.return_value = MagicMock()

        db.query.side_effect = [subject_query, grade_query]

        expected_book = _make_book()
        mock_crud.create.return_value = expected_book

        payload = BookCreate(
            title="Test Book",
            subject_id=10,
            grade_level_id=20,
            isbn="978-0-123456-78-9",
        )

        result = create_book(payload, db)

        assert result == expected_book
        mock_crud.create.assert_called_once_with(
            db, Book, payload.model_dump(), unique_fields=["isbn"]
        )

    def test_create_book_invalid_subject(self):
        """Returns 422 when subject_id does not exist.

        Validates: Requirement 9.11
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        payload = BookCreate(
            title="Test Book",
            subject_id=999,
            grade_level_id=20,
        )

        with pytest.raises(ValidationError) as exc_info:
            create_book(payload, db)

        assert "subject" in exc_info.value.detail.lower()

    def test_create_book_invalid_grade_level(self):
        """Returns 422 when grade_level_id does not exist.

        Validates: Requirement 9.11
        """
        db = MagicMock()
        # Subject exists
        subject_query = MagicMock()
        subject_query.filter.return_value.first.return_value = MagicMock()
        # Grade level does not exist
        grade_query = MagicMock()
        grade_query.filter.return_value.first.return_value = None

        db.query.side_effect = [subject_query, grade_query]

        payload = BookCreate(
            title="Test Book",
            subject_id=10,
            grade_level_id=999,
        )

        with pytest.raises(ValidationError) as exc_info:
            create_book(payload, db)

        assert "grade level" in exc_info.value.detail.lower()

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_create_book_duplicate_isbn(self, mock_crud):
        """Returns 409 when ISBN already exists.

        Validates: Requirement 9.10
        """
        db = MagicMock()
        # Both FKs exist
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        mock_crud.create.side_effect = ConflictError(
            "A record with this isbn already exists"
        )

        payload = BookCreate(
            title="Test Book",
            subject_id=10,
            grade_level_id=20,
            isbn="DUPLICATE-ISBN",
        )

        with pytest.raises(ConflictError) as exc_info:
            create_book(payload, db)

        assert "isbn" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# List Books Tests
# ---------------------------------------------------------------------------


class TestListBooks:
    """Tests for list_books endpoint handler."""

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_list_books_no_filters(self, mock_crud):
        """Returns paginated list of all books.

        Validates: Requirement 9.2
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        expected = PaginatedResponse(
            items=[_make_book()], total=1, page=1, page_size=20
        )
        mock_crud.get_all.return_value = expected

        result = list_books(subject_id=None, grade_level_id=None, params=params, db=db)

        assert result == expected
        mock_crud.get_all.assert_called_once_with(
            db, Book, params, filters={"subject_id": None, "grade_level_id": None}
        )

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_list_books_filter_by_subject(self, mock_crud):
        """Filters books by subject_id.

        Validates: Requirement 9.3
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        expected = PaginatedResponse(
            items=[_make_book()], total=1, page=1, page_size=20
        )
        mock_crud.get_all.return_value = expected

        result = list_books(subject_id=10, grade_level_id=None, params=params, db=db)

        mock_crud.get_all.assert_called_once_with(
            db, Book, params, filters={"subject_id": 10, "grade_level_id": None}
        )

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_list_books_filter_by_grade_level(self, mock_crud):
        """Filters books by grade_level_id.

        Validates: Requirement 9.4
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        expected = PaginatedResponse(
            items=[_make_book()], total=1, page=1, page_size=20
        )
        mock_crud.get_all.return_value = expected

        result = list_books(subject_id=None, grade_level_id=20, params=params, db=db)

        mock_crud.get_all.assert_called_once_with(
            db, Book, params, filters={"subject_id": None, "grade_level_id": 20}
        )

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_list_books_filter_by_both(self, mock_crud):
        """Filters books by both subject_id and grade_level_id.

        Validates: Requirement 9.5
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        expected = PaginatedResponse(
            items=[_make_book()], total=1, page=1, page_size=20
        )
        mock_crud.get_all.return_value = expected

        result = list_books(subject_id=10, grade_level_id=20, params=params, db=db)

        mock_crud.get_all.assert_called_once_with(
            db, Book, params, filters={"subject_id": 10, "grade_level_id": 20}
        )


# ---------------------------------------------------------------------------
# Get Book Tests
# ---------------------------------------------------------------------------


class TestGetBook:
    """Tests for get_book endpoint handler."""

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_get_book_found(self, mock_crud):
        """Returns the book when it exists.

        Validates: Requirement 9.6
        """
        expected_book = _make_book()
        mock_crud.get_by_id.return_value = expected_book
        db = MagicMock()

        result = get_book(1, db)

        assert result == expected_book
        mock_crud.get_by_id.assert_called_once_with(db, Book, 1)

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_get_book_not_found(self, mock_crud):
        """Returns 404 when book does not exist.

        Validates: Requirement 9.9
        """
        mock_crud.get_by_id.side_effect = NotFoundError("Book with id 999 not found")
        db = MagicMock()

        with pytest.raises(NotFoundError) as exc_info:
            get_book(999, db)

        assert "999" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Update Book Tests
# ---------------------------------------------------------------------------


class TestUpdateBook:
    """Tests for update_book endpoint handler."""

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_update_book_success(self, mock_crud):
        """Updates a book when all validations pass.

        Validates: Requirement 9.7
        """
        db = MagicMock()
        # FK validations pass
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        updated_book = _make_book(title="Updated Title")
        mock_crud.update.return_value = updated_book

        payload = BookUpdate(title="Updated Title", subject_id=10, grade_level_id=20)

        result = update_book(1, payload, db)

        assert result == updated_book

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_update_book_not_found(self, mock_crud):
        """Returns 404 when book does not exist.

        Validates: Requirement 9.9
        """
        db = MagicMock()
        # No FK fields in payload, so no FK validation needed
        mock_crud.update.side_effect = NotFoundError("Book with id 999 not found")

        payload = BookUpdate(title="New Title")

        with pytest.raises(NotFoundError):
            update_book(999, payload, db)

    def test_update_book_invalid_subject(self):
        """Returns 422 when updated subject_id does not exist.

        Validates: Requirement 9.11
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        payload = BookUpdate(subject_id=999)

        with pytest.raises(ValidationError) as exc_info:
            update_book(1, payload, db)

        assert "subject" in exc_info.value.detail.lower()

    def test_update_book_invalid_grade_level(self):
        """Returns 422 when updated grade_level_id does not exist.

        Validates: Requirement 9.11
        """
        db = MagicMock()
        # Subject exists
        subject_query = MagicMock()
        subject_query.filter.return_value.first.return_value = MagicMock()
        # Grade level does not exist
        grade_query = MagicMock()
        grade_query.filter.return_value.first.return_value = None

        db.query.side_effect = [subject_query, grade_query]

        payload = BookUpdate(subject_id=10, grade_level_id=999)

        with pytest.raises(ValidationError) as exc_info:
            update_book(1, payload, db)

        assert "grade level" in exc_info.value.detail.lower()

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_update_book_duplicate_isbn(self, mock_crud):
        """Returns 409 when updated ISBN already exists.

        Validates: Requirement 9.10
        """
        db = MagicMock()
        # No FK fields in payload
        mock_crud.update.side_effect = ConflictError(
            "A record with this isbn already exists"
        )

        payload = BookUpdate(isbn="DUPLICATE-ISBN")

        with pytest.raises(ConflictError) as exc_info:
            update_book(1, payload, db)

        assert "isbn" in exc_info.value.detail.lower()

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_update_book_partial_no_fk_validation(self, mock_crud):
        """Skips FK validation when subject_id and grade_level_id are not in payload.

        Validates: Requirement 9.7 (partial update)
        """
        db = MagicMock()
        updated_book = _make_book(title="Only Title Changed")
        mock_crud.update.return_value = updated_book

        payload = BookUpdate(title="Only Title Changed")

        result = update_book(1, payload, db)

        assert result == updated_book
        # db.query should not be called for FK validation
        db.query.assert_not_called()


# ---------------------------------------------------------------------------
# Delete Book Tests
# ---------------------------------------------------------------------------


class TestDeleteBook:
    """Tests for delete_book endpoint handler."""

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_delete_book_success(self, mock_crud):
        """Deletes a book and returns None (204).

        Validates: Requirement 9.8
        """
        db = MagicMock()
        mock_crud.delete.return_value = None

        result = delete_book(1, db)

        assert result is None
        mock_crud.delete.assert_called_once_with(
            db, Book, 1, check_references=[(BookCopy, "book_id")]
        )

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_delete_book_not_found(self, mock_crud):
        """Returns 404 when book does not exist.

        Validates: Requirement 9.9
        """
        mock_crud.delete.side_effect = NotFoundError("Book with id 999 not found")
        db = MagicMock()

        with pytest.raises(NotFoundError):
            delete_book(999, db)

    @patch("app.api.v1.endpoints.books.crud_service")
    def test_delete_book_referenced(self, mock_crud):
        """Returns 409 when book is referenced by book_copies.

        Validates: Referential integrity (Property 15)
        """
        mock_crud.delete.side_effect = ConflictError(
            "Cannot delete Book because it is referenced by existing book_copies records"
        )
        db = MagicMock()

        with pytest.raises(ConflictError) as exc_info:
            delete_book(1, db)

        assert "referenced" in exc_info.value.detail.lower()
