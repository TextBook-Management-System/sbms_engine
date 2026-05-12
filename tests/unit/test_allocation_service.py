"""Unit tests for app.services.allocation_service module.

Tests the allocation service functions with mocked DB sessions,
validating requirements 16.1–16.8.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginationParams
from app.models.database import BookAllocation, BookCopy, Learner
from app.services import allocation_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_book_copy(**overrides):
    """Create a fake BookCopy instance."""
    defaults = {
        "id": 1,
        "book_id": 10,
        "school_id": 5,
        "qr_code": "QR-001",
        "condition": "good",
        "created_at": datetime(2024, 1, 1),
    }
    defaults.update(overrides)
    obj = MagicMock(spec=BookCopy)
    for key, value in defaults.items():
        setattr(obj, key, value)
    return obj


def _make_learner(**overrides):
    """Create a fake Learner instance."""
    defaults = {
        "id": 1,
        "grade_id": 3,
        "first_name": "John",
        "last_name": "Doe",
        "created_at": datetime(2024, 1, 1),
    }
    defaults.update(overrides)
    obj = MagicMock(spec=Learner)
    for key, value in defaults.items():
        setattr(obj, key, value)
    return obj


def _make_allocation(**overrides):
    """Create a fake BookAllocation instance."""
    defaults = {
        "id": 1,
        "book_copy_id": 1,
        "learner_id": 1,
        "status": "active",
        "allocation_date": datetime(2024, 1, 15),
        "return_date": None,
    }
    defaults.update(overrides)
    obj = MagicMock(spec=BookAllocation)
    for key, value in defaults.items():
        setattr(obj, key, value)
    return obj


# ---------------------------------------------------------------------------
# allocate Tests
# ---------------------------------------------------------------------------


class TestAllocate:
    """Tests for allocation_service.allocate."""

    def test_allocate_success(self):
        """Creates an allocation with status 'active' when all validations pass.

        Validates: Requirement 16.1
        """
        db = MagicMock()
        book_copy = _make_book_copy(id=1)
        learner = _make_learner(id=2)

        # First query: book copy exists
        # Second query: learner exists
        # Third query: no active allocation
        db.query.return_value.filter.return_value.first.side_effect = [
            book_copy,
            learner,
            None,  # No active allocation
        ]

        result = allocation_service.allocate(db, book_copy_id=1, learner_id=2)

        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_allocate_book_copy_not_found(self):
        """Raises NotFoundError (404) when book_copy_id doesn't exist.

        Validates: Requirement 16.6
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            allocation_service.allocate(db, book_copy_id=999, learner_id=1)

        assert "book copy" in exc_info.value.detail.lower()
        assert "999" in exc_info.value.detail

    def test_allocate_learner_not_found(self):
        """Raises NotFoundError (404) when learner_id doesn't exist.

        Validates: Requirement 16.6
        """
        db = MagicMock()
        book_copy = _make_book_copy(id=1)

        # Book copy found, learner not found
        db.query.return_value.filter.return_value.first.side_effect = [
            book_copy,
            None,
        ]

        with pytest.raises(NotFoundError) as exc_info:
            allocation_service.allocate(db, book_copy_id=1, learner_id=999)

        assert "learner" in exc_info.value.detail.lower()
        assert "999" in exc_info.value.detail

    def test_allocate_already_active_conflict(self):
        """Raises ConflictError (409) when book copy already has an active allocation.

        Validates: Requirement 16.5
        """
        db = MagicMock()
        book_copy = _make_book_copy(id=1)
        learner = _make_learner(id=2)
        existing_allocation = _make_allocation(id=10, book_copy_id=1, status="active")

        # Book copy found, learner found, active allocation exists
        db.query.return_value.filter.return_value.first.side_effect = [
            book_copy,
            learner,
            existing_allocation,
        ]

        with pytest.raises(ConflictError) as exc_info:
            allocation_service.allocate(db, book_copy_id=1, learner_id=2)

        assert "currently allocated" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# return_allocation Tests
# ---------------------------------------------------------------------------


class TestReturnAllocation:
    """Tests for allocation_service.return_allocation."""

    def test_return_success(self):
        """Updates allocation to 'returned' with return_date set.

        Validates: Requirement 16.2
        """
        db = MagicMock()
        allocation = _make_allocation(id=1, status="active")
        db.query.return_value.filter.return_value.first.return_value = allocation

        result = allocation_service.return_allocation(db, allocation_id=1)

        assert allocation.status == "returned"
        assert allocation.return_date is not None
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(allocation)

    def test_return_not_found(self):
        """Raises NotFoundError (404) when allocation doesn't exist.

        Validates: Requirement 16.7
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            allocation_service.return_allocation(db, allocation_id=999)

        assert "999" in exc_info.value.detail

    def test_return_already_returned_conflict(self):
        """Raises ConflictError (409) when allocation is already returned.

        Validates: Requirement 16.8
        """
        db = MagicMock()
        allocation = _make_allocation(id=1, status="returned")
        db.query.return_value.filter.return_value.first.return_value = allocation

        with pytest.raises(ConflictError) as exc_info:
            allocation_service.return_allocation(db, allocation_id=1)

        assert "already been returned" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# get_by_id Tests
# ---------------------------------------------------------------------------


class TestGetById:
    """Tests for allocation_service.get_by_id."""

    def test_returns_allocation_when_found(self):
        """Returns the allocation record when it exists.

        Validates: Requirement 16.4
        """
        db = MagicMock()
        allocation = _make_allocation(id=1)
        db.query.return_value.filter.return_value.first.return_value = allocation

        result = allocation_service.get_by_id(db, 1)

        assert result == allocation

    def test_raises_not_found_when_missing(self):
        """Raises NotFoundError (404) when allocation doesn't exist.

        Validates: Requirement 16.7
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            allocation_service.get_by_id(db, 999)

        assert "999" in exc_info.value.detail


# ---------------------------------------------------------------------------
# list_allocations Tests
# ---------------------------------------------------------------------------


class TestListAllocations:
    """Tests for allocation_service.list_allocations."""

    def test_list_without_filters(self):
        """Returns paginated allocations without filters.

        Validates: Requirement 16.3
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)

        mock_query = MagicMock()
        mock_query.count.return_value = 2
        mock_query.offset.return_value.limit.return_value.all.return_value = [
            _make_allocation(id=1),
            _make_allocation(id=2),
        ]
        db.query.return_value = mock_query

        result = allocation_service.list_allocations(db, params)

        assert result.total == 2
        assert len(result.items) == 2

    def test_list_with_learner_filter(self):
        """Applies learner_id filter when provided.

        Validates: Requirement 16.3
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value.limit.return_value.all.return_value = [
            _make_allocation(id=1, learner_id=5),
        ]
        db.query.return_value = mock_query

        result = allocation_service.list_allocations(db, params, learner_id=5)

        assert result.total == 1

    def test_list_with_status_filter(self):
        """Applies status filter when provided.

        Validates: Requirement 16.3
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value.limit.return_value.all.return_value = [
            _make_allocation(id=1, status="active"),
        ]
        db.query.return_value = mock_query

        result = allocation_service.list_allocations(db, params, status="active")

        assert result.total == 1

    def test_list_with_book_copy_filter(self):
        """Applies book_copy_id filter when provided.

        Validates: Requirement 16.3
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value.limit.return_value.all.return_value = [
            _make_allocation(id=1, book_copy_id=7),
        ]
        db.query.return_value = mock_query

        result = allocation_service.list_allocations(db, params, book_copy_id=7)

        assert result.total == 1
