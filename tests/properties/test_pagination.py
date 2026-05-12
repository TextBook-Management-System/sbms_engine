# Feature: sbms-api-endpoints, Property 7: Pagination Envelope Correctness
"""
Property-based tests for pagination envelope correctness.

Tests validate that the paginate() function in app/core/pagination.py
correctly computes the pagination envelope for any combination of
total records (N), page number, and page_size.

**Validates: Requirements 20.1, 20.2, 20.3, 20.4**
"""
import math
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.pagination import PaginatedResponse, PaginationParams, paginate


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Total number of matching records in the dataset
total_records = st.integers(min_value=0, max_value=500)

# Page number (valid: >= 1)
page_number = st.integers(min_value=1, max_value=50)

# Page size (1-200, to test capping behavior at 100)
page_size_strategy = st.integers(min_value=1, max_value=200)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_query(total: int, page: int, effective_page_size: int):
    """Create a mock SQLAlchemy query that returns the correct slice of items.

    Simulates a real query by computing the expected offset and returning
    the appropriate number of placeholder items.
    """
    offset = (page - 1) * effective_page_size
    # Number of items that would be returned for this page
    expected_item_count = min(effective_page_size, max(0, total - offset))
    items = [{"id": i} for i in range(expected_item_count)]

    query = MagicMock()
    query.count.return_value = total
    # Chain offset().limit().all() to return the computed items
    query.offset.return_value = query
    query.limit.return_value = query
    query.all.return_value = items
    return query, items


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestPaginationEnvelopeCorrectness:
    """Property 7: Pagination Envelope Correctness.

    For any dataset of N total matching records and any valid pagination
    parameters (page >= 1, 1 <= page_size <= 200), the paginate() function
    SHALL produce a correct envelope.
    """

    @given(
        n=total_records,
        page=page_number,
        requested_page_size=page_size_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_total_equals_n(self, n: int, page: int, requested_page_size: int):
        """Requirement 20.2: `total` equals N (the true count of all matching records).

        **Validates: Requirements 20.2**
        """
        effective_page_size = min(requested_page_size, 100)
        params = PaginationParams(page=page, page_size=requested_page_size)
        query, _ = _make_mock_query(n, page, effective_page_size)

        result = paginate(query, params)

        assert result.total == n, (
            f"Expected total={n}, got total={result.total} "
            f"(page={page}, page_size={requested_page_size})"
        )

    @given(
        n=total_records,
        page=page_number,
        requested_page_size=page_size_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_page_equals_requested_page(self, n: int, page: int, requested_page_size: int):
        """Requirement 20.1: `page` equals the requested page number.

        **Validates: Requirements 20.1**
        """
        effective_page_size = min(requested_page_size, 100)
        params = PaginationParams(page=page, page_size=requested_page_size)
        query, _ = _make_mock_query(n, page, effective_page_size)

        result = paginate(query, params)

        assert result.page == page, (
            f"Expected page={page}, got page={result.page}"
        )

    @given(
        n=total_records,
        page=page_number,
        requested_page_size=page_size_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_page_size_equals_min_requested_100(self, n: int, page: int, requested_page_size: int):
        """Requirement 20.4: `page_size` equals min(requested_page_size, 100).

        **Validates: Requirements 20.4**
        """
        effective_page_size = min(requested_page_size, 100)
        params = PaginationParams(page=page, page_size=requested_page_size)
        query, _ = _make_mock_query(n, page, effective_page_size)

        result = paginate(query, params)

        assert result.page_size == effective_page_size, (
            f"Expected page_size={effective_page_size}, got page_size={result.page_size} "
            f"(requested_page_size={requested_page_size})"
        )

    @given(
        n=total_records,
        page=page_number,
        requested_page_size=page_size_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_items_length_correct(self, n: int, page: int, requested_page_size: int):
        """Requirement 20.2: len(items) equals min(page_size, max(0, N - (page-1) * page_size)).

        **Validates: Requirements 20.2**
        """
        effective_page_size = min(requested_page_size, 100)
        params = PaginationParams(page=page, page_size=requested_page_size)
        query, _ = _make_mock_query(n, page, effective_page_size)

        result = paginate(query, params)

        expected_len = min(effective_page_size, max(0, n - (page - 1) * effective_page_size))
        assert len(result.items) == expected_len, (
            f"Expected len(items)={expected_len}, got {len(result.items)} "
            f"(N={n}, page={page}, effective_page_size={effective_page_size})"
        )

    @given(
        n=total_records,
        page=page_number,
        requested_page_size=page_size_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_page_beyond_total_returns_empty(self, n: int, page: int, requested_page_size: int):
        """Requirement 20.3: If page > ceil(N / page_size), then items is empty.

        **Validates: Requirements 20.3**
        """
        effective_page_size = min(requested_page_size, 100)
        # Calculate total pages
        if n == 0:
            total_pages = 0
        else:
            total_pages = math.ceil(n / effective_page_size)

        # Only test when page exceeds total pages
        if page <= total_pages:
            return  # Skip — this case is covered by test_items_length_correct

        params = PaginationParams(page=page, page_size=requested_page_size)
        query, _ = _make_mock_query(n, page, effective_page_size)

        result = paginate(query, params)

        assert result.items == [], (
            f"Expected empty items when page={page} > total_pages={total_pages} "
            f"(N={n}, effective_page_size={effective_page_size}), "
            f"but got {len(result.items)} items"
        )
