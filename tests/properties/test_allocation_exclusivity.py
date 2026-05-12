# Feature: sbms-api-endpoints, Property 11: Allocation Mutual Exclusivity
"""
Property-based tests for allocation mutual exclusivity.

Tests validate that:
- For any book_copy_id that already has an active allocation, attempting to create
  a new allocation raises ConflictError (409).
- After returning the existing allocation (status → "returned"), a new allocation
  for the same book copy succeeds.
- Multiple book copies can each have their own active allocation simultaneously
  (no cross-copy interference).

**Validates: Requirements 16.1, 16.5**
"""

import pytest
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.exceptions import ConflictError, NotFoundError
from app.models.database import BookAllocation, BookCopy, Learner
from app.services import allocation_service


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid IDs (positive integers representing BIGINT UNSIGNED PKs)
valid_ids = st.integers(min_value=1, max_value=2**31 - 1)

# Number of distinct book copies to test cross-copy independence
num_book_copies = st.integers(min_value=2, max_value=10)

# Number of learners available for allocation
num_learners = st.integers(min_value=2, max_value=10)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db_with_active_allocation(book_copy_id: int):
    """Create a mock DB session that returns an active allocation for the given book_copy_id."""
    mock_db = MagicMock()

    # Mock book copy exists
    mock_book_copy = MagicMock(spec=BookCopy)
    mock_book_copy.id = book_copy_id

    # Mock learner exists
    mock_learner = MagicMock(spec=Learner)
    mock_learner.id = 1

    # Active allocation exists for this book copy
    active_allocation = MagicMock(spec=BookAllocation)
    active_allocation.id = 100
    active_allocation.book_copy_id = book_copy_id
    active_allocation.status = "active"

    # Set up query chain behavior
    def query_side_effect(model):
        mock_query = MagicMock()

        def filter_side_effect(*args, **kwargs):
            mock_filter = MagicMock()
            if model == BookCopy:
                mock_filter.first.return_value = mock_book_copy
            elif model == Learner:
                mock_filter.first.return_value = mock_learner
            elif model == BookAllocation:
                # Return active allocation when checking for active allocations
                mock_filter.first.return_value = active_allocation
            return mock_filter

        mock_query.filter.side_effect = filter_side_effect
        return mock_query

    mock_db.query.side_effect = query_side_effect
    return mock_db


def _make_mock_db_no_active_allocation(book_copy_id: int, learner_id: int):
    """Create a mock DB session with no active allocation for the given book_copy_id."""
    mock_db = MagicMock()

    # Mock book copy exists
    mock_book_copy = MagicMock(spec=BookCopy)
    mock_book_copy.id = book_copy_id

    # Mock learner exists
    mock_learner = MagicMock(spec=Learner)
    mock_learner.id = learner_id

    # Set up query chain behavior
    def query_side_effect(model):
        mock_query = MagicMock()

        def filter_side_effect(*args, **kwargs):
            mock_filter = MagicMock()
            if model == BookCopy:
                mock_filter.first.return_value = mock_book_copy
            elif model == Learner:
                mock_filter.first.return_value = mock_learner
            elif model == BookAllocation:
                # No active allocation exists
                mock_filter.first.return_value = None
            return mock_filter

        mock_query.filter.side_effect = filter_side_effect
        return mock_query

    mock_db.query.side_effect = query_side_effect

    # Mock the add/commit/refresh cycle
    def refresh_side_effect(obj):
        obj.id = 1
        obj.allocation_date = "2024-01-01T00:00:00"

    mock_db.refresh.side_effect = refresh_side_effect

    return mock_db


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestAllocationMutualExclusivity:
    """
    Property 11: For any book copy that currently has an active allocation,
    attempting to create a new allocation for that same book copy SHALL return
    HTTP 409. Only after the existing allocation is returned (status changed to
    "returned") SHALL a new allocation for that copy succeed.
    """

    @given(
        book_copy_id=valid_ids,
        learner_id=valid_ids,
    )
    @settings(max_examples=100, deadline=None)
    def test_allocating_already_active_book_copy_raises_conflict(
        self, book_copy_id: int, learner_id: int
    ):
        """
        For any book_copy_id that already has an active allocation, attempting
        to create a new allocation raises ConflictError (409).

        **Validates: Requirements 16.1, 16.5**
        """
        mock_db = _make_mock_db_with_active_allocation(book_copy_id)

        with pytest.raises(ConflictError) as exc_info:
            allocation_service.allocate(
                db=mock_db,
                book_copy_id=book_copy_id,
                learner_id=learner_id,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"

    @given(
        book_copy_id=valid_ids,
        first_learner_id=valid_ids,
        second_learner_id=valid_ids,
    )
    @settings(max_examples=100, deadline=None)
    def test_after_return_new_allocation_succeeds(
        self, book_copy_id: int, first_learner_id: int, second_learner_id: int
    ):
        """
        After returning the existing allocation (status → "returned"), a new
        allocation for the same book copy succeeds.

        This tests the full lifecycle: allocate → return → re-allocate.

        **Validates: Requirements 16.1, 16.5**
        """
        # Phase 1: First allocation succeeds (no active allocation exists)
        mock_db_phase1 = _make_mock_db_no_active_allocation(book_copy_id, first_learner_id)
        first_allocation = allocation_service.allocate(
            db=mock_db_phase1,
            book_copy_id=book_copy_id,
            learner_id=first_learner_id,
        )
        assert first_allocation.status == "active"

        # Phase 2: Return the first allocation
        mock_db_phase2 = MagicMock()
        returned_allocation = MagicMock(spec=BookAllocation)
        returned_allocation.id = 1
        returned_allocation.book_copy_id = book_copy_id
        returned_allocation.learner_id = first_learner_id
        returned_allocation.status = "active"

        def query_for_return(model):
            mock_query = MagicMock()

            def filter_side_effect(*args, **kwargs):
                mock_filter = MagicMock()
                mock_filter.first.return_value = returned_allocation
                return mock_filter

            mock_query.filter.side_effect = filter_side_effect
            return mock_query

        mock_db_phase2.query.side_effect = query_for_return

        result = allocation_service.return_allocation(db=mock_db_phase2, allocation_id=1)
        assert result.status == "returned"

        # Phase 3: New allocation succeeds after return (no active allocation)
        mock_db_phase3 = _make_mock_db_no_active_allocation(book_copy_id, second_learner_id)
        new_allocation = allocation_service.allocate(
            db=mock_db_phase3,
            book_copy_id=book_copy_id,
            learner_id=second_learner_id,
        )
        assert new_allocation.status == "active"

    @given(
        book_copy_ids=st.lists(valid_ids, min_size=2, max_size=10, unique=True),
        learner_ids=st.lists(valid_ids, min_size=2, max_size=10, unique=True),
    )
    @settings(max_examples=100, deadline=None)
    def test_multiple_book_copies_can_have_independent_active_allocations(
        self, book_copy_ids: list, learner_ids: list
    ):
        """
        Multiple book copies can each have their own active allocation
        simultaneously (no cross-copy interference).

        **Validates: Requirements 16.1, 16.5**
        """
        # Use the minimum of the two list lengths to pair them
        pair_count = min(len(book_copy_ids), len(learner_ids))

        allocations = []
        for i in range(pair_count):
            book_copy_id = book_copy_ids[i]
            learner_id = learner_ids[i]

            # Each book copy has no active allocation (independent)
            mock_db = _make_mock_db_no_active_allocation(book_copy_id, learner_id)
            alloc = allocation_service.allocate(
                db=mock_db,
                book_copy_id=book_copy_id,
                learner_id=learner_id,
            )
            allocations.append(alloc)

        # Property: all allocations were created successfully with "active" status
        assert len(allocations) == pair_count
        for alloc in allocations:
            assert alloc.status == "active"

    @given(
        book_copy_id=valid_ids,
        learner_id=valid_ids,
    )
    @settings(max_examples=100, deadline=None)
    def test_check_active_allocation_raises_conflict_when_active_exists(
        self, book_copy_id: int, learner_id: int
    ):
        """
        The _check_active_allocation helper directly raises ConflictError
        when an active allocation exists for the given book_copy_id.

        **Validates: Requirements 16.1, 16.5**
        """
        # Set up a mock DB that returns an active allocation
        mock_db = MagicMock()
        active_alloc = MagicMock(spec=BookAllocation)
        active_alloc.status = "active"
        active_alloc.book_copy_id = book_copy_id

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = active_alloc
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with pytest.raises(ConflictError) as exc_info:
            allocation_service._check_active_allocation(mock_db, book_copy_id)

        assert exc_info.value.status_code == 409
        assert "currently allocated" in exc_info.value.detail

    @given(
        book_copy_id=valid_ids,
    )
    @settings(max_examples=100, deadline=None)
    def test_check_active_allocation_passes_when_no_active_exists(
        self, book_copy_id: int
    ):
        """
        The _check_active_allocation helper does NOT raise when no active
        allocation exists for the given book_copy_id.

        **Validates: Requirements 16.1, 16.5**
        """
        # Set up a mock DB that returns None (no active allocation)
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Should not raise
        allocation_service._check_active_allocation(mock_db, book_copy_id)
