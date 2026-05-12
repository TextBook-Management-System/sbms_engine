"""Unit tests for app.services.inventory_service module.

Tests the read-only inventory service that provides access to the
school_books_inventory table (maintained by MySQL triggers).

Validates: Requirements 10.1–10.6
"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.core.pagination import PaginationParams
from app.services import inventory_service


class FakeSchool:
    """Fake School model for testing."""

    def __init__(self, id=1):
        self.id = id


class FakeBook:
    """Fake Book model for testing."""

    def __init__(self, id=1):
        self.id = id


class FakeInventoryRecord:
    """Fake SchoolBooksInventory record for testing."""

    def __init__(self, id=1, school_id=1, book_id=1, quantity=10):
        self.id = id
        self.school_id = school_id
        self.book_id = book_id
        self.quantity = quantity
        self.subject = "Mathematics"
        self.grade_level = "Grade 1"
        self.condition_notes = None
        self.last_updated = "2024-01-01T00:00:00"


class TestValidateSchoolExists:
    """Tests for inventory_service.validate_school_exists."""

    def test_school_exists_no_error(self):
        """No error raised when school exists."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = FakeSchool(id=1)

        # Should not raise
        inventory_service.validate_school_exists(db, 1)

    def test_school_not_found_raises_404(self):
        """Raises NotFoundError when school does not exist.

        Validates: Requirement 10.5
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            inventory_service.validate_school_exists(db, 999)

        assert "999" in str(exc_info.value.detail)
        assert "School" in str(exc_info.value.detail)


class TestValidateBookExists:
    """Tests for inventory_service.validate_book_exists."""

    def test_book_exists_no_error(self):
        """No error raised when book exists."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = FakeBook(id=1)

        # Should not raise
        inventory_service.validate_book_exists(db, 1)

    def test_book_not_found_raises_404(self):
        """Raises NotFoundError when book does not exist.

        Validates: Requirement 10.6
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            inventory_service.validate_book_exists(db, 999)

        assert "999" in str(exc_info.value.detail)
        assert "Book" in str(exc_info.value.detail)


class TestGetInventoryList:
    """Tests for inventory_service.get_inventory_list."""

    @patch("app.services.inventory_service.validate_school_exists")
    @patch("app.services.inventory_service.paginate")
    def test_returns_paginated_response(self, mock_paginate, mock_validate):
        """Returns paginated inventory records for a valid school.

        Validates: Requirement 10.1
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)

        mock_paginate.return_value = MagicMock(
            items=[FakeInventoryRecord()],
            total=1,
            page=1,
            page_size=20,
        )

        result = inventory_service.get_inventory_list(db, 1, params)

        mock_validate.assert_called_once_with(db, 1)
        assert result.total == 1
        assert len(result.items) == 1

    @patch("app.services.inventory_service.validate_school_exists")
    def test_raises_404_for_nonexistent_school(self, mock_validate):
        """Raises NotFoundError when school does not exist.

        Validates: Requirement 10.5
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        mock_validate.side_effect = NotFoundError(detail="School with id 999 not found")

        with pytest.raises(NotFoundError):
            inventory_service.get_inventory_list(db, 999, params)


class TestGetInventoryByBook:
    """Tests for inventory_service.get_inventory_by_book."""

    @patch("app.services.inventory_service.validate_book_exists")
    @patch("app.services.inventory_service.validate_school_exists")
    def test_returns_inventory_record(self, mock_validate_school, mock_validate_book):
        """Returns the inventory record for a valid school and book.

        Validates: Requirement 10.2
        """
        db = MagicMock()
        expected_record = FakeInventoryRecord(school_id=1, book_id=5)
        db.query.return_value.filter.return_value.first.return_value = expected_record

        result = inventory_service.get_inventory_by_book(db, 1, 5)

        assert result == expected_record
        mock_validate_school.assert_called_once_with(db, 1)
        mock_validate_book.assert_called_once_with(db, 5)

    @patch("app.services.inventory_service.validate_book_exists")
    @patch("app.services.inventory_service.validate_school_exists")
    def test_raises_404_when_no_inventory_record(
        self, mock_validate_school, mock_validate_book
    ):
        """Raises NotFoundError when no inventory record exists for the book at the school.

        Validates: Requirement 10.3
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            inventory_service.get_inventory_by_book(db, 1, 5)

        assert "inventory" in str(exc_info.value.detail).lower()
        assert "5" in str(exc_info.value.detail)

    @patch("app.services.inventory_service.validate_school_exists")
    def test_raises_404_for_nonexistent_school(self, mock_validate_school):
        """Raises NotFoundError when school does not exist.

        Validates: Requirement 10.5
        """
        db = MagicMock()
        mock_validate_school.side_effect = NotFoundError(
            detail="School with id 999 not found"
        )

        with pytest.raises(NotFoundError):
            inventory_service.get_inventory_by_book(db, 999, 1)

    @patch("app.services.inventory_service.validate_book_exists")
    @patch("app.services.inventory_service.validate_school_exists")
    def test_raises_404_for_nonexistent_book(
        self, mock_validate_school, mock_validate_book
    ):
        """Raises NotFoundError when book does not exist.

        Validates: Requirement 10.6
        """
        db = MagicMock()
        mock_validate_book.side_effect = NotFoundError(
            detail="Book with id 999 not found"
        )

        with pytest.raises(NotFoundError):
            inventory_service.get_inventory_by_book(db, 1, 999)
