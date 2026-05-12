"""Unit tests for app.core.pagination module."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.pagination import PaginatedResponse, PaginationParams, paginate


class TestPaginationParams:
    """Tests for PaginationParams dependency."""

    def test_defaults(self):
        """Default page=1, page_size=20."""
        # When called directly (not via FastAPI DI), pass explicit defaults
        params = PaginationParams(page=1, page_size=20)
        assert params.page == 1
        assert params.page_size == 20

    def test_custom_values(self):
        """Accepts custom page and page_size."""
        params = PaginationParams(page=3, page_size=50)
        assert params.page == 3
        assert params.page_size == 50

    def test_page_size_capped_at_100(self):
        """page_size exceeding 100 is capped at 100."""
        params = PaginationParams(page=1, page_size=200)
        assert params.page_size == 100

    def test_page_size_exactly_100(self):
        """page_size of exactly 100 is allowed."""
        params = PaginationParams(page=1, page_size=100)
        assert params.page_size == 100

    def test_page_size_minimum(self):
        """page_size of 1 is valid."""
        params = PaginationParams(page=1, page_size=1)
        assert params.page_size == 1


class TestPaginatedResponse:
    """Tests for PaginatedResponse model."""

    def test_basic_construction(self):
        """Can construct a PaginatedResponse with valid data."""
        response = PaginatedResponse(
            items=["a", "b", "c"],
            total=10,
            page=1,
            page_size=3,
        )
        assert response.items == ["a", "b", "c"]
        assert response.total == 10
        assert response.page == 1
        assert response.page_size == 3

    def test_empty_items(self):
        """Can construct with empty items list."""
        response = PaginatedResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
        )
        assert response.items == []
        assert response.total == 0


class TestPaginate:
    """Tests for the paginate() utility function."""

    def _make_mock_query(self, items: list, total: int):
        """Create a mock SQLAlchemy query with count, offset, limit, all."""
        query = MagicMock()
        query.count.return_value = total
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = items
        return query

    def test_first_page(self):
        """Returns correct envelope for first page."""
        items = [{"id": 1}, {"id": 2}]
        query = self._make_mock_query(items, total=5)
        params = PaginationParams(page=1, page_size=2)

        result = paginate(query, params)

        assert result.items == items
        assert result.total == 5
        assert result.page == 1
        assert result.page_size == 2
        query.offset.assert_called_once_with(0)
        query.limit.assert_called_once_with(2)

    def test_second_page(self):
        """Offset is correctly calculated for page 2."""
        items = [{"id": 3}, {"id": 4}]
        query = self._make_mock_query(items, total=5)
        params = PaginationParams(page=2, page_size=2)

        result = paginate(query, params)

        assert result.items == items
        assert result.total == 5
        assert result.page == 2
        query.offset.assert_called_once_with(2)
        query.limit.assert_called_once_with(2)

    def test_page_beyond_total(self):
        """Returns empty items when page exceeds total pages."""
        query = self._make_mock_query([], total=5)
        params = PaginationParams(page=100, page_size=20)

        result = paginate(query, params)

        assert result.items == []
        assert result.total == 5
        assert result.page == 100

    def test_page_size_capped_in_query(self):
        """When page_size > 100, the capped value (100) is used in the query."""
        query = self._make_mock_query([], total=0)
        params = PaginationParams(page=1, page_size=500)

        result = paginate(query, params)

        # page_size should be capped at 100
        assert result.page_size == 100
        query.limit.assert_called_once_with(100)
