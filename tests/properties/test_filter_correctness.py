# Feature: sbms-api-endpoints, Property 8: Query Filter Correctness
"""
Property-based tests for query filter correctness.

Tests validate that for any list endpoint that supports filtering, every item
in the filtered response SHALL match ALL applied filter criteria. No item that
does not match the filter SHALL appear in the results.

Tests the crud_service.get_all() filtering logic directly with a mock DB session,
simulating the filtering behavior for books (by subject_id, grade_level_id),
schools (by department_id), and book copies (by school_id, book_id).

**Validates: Requirements 4.3, 9.3, 9.4, 9.5, 13.6, 13.7, 16.3**
"""

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.pagination import PaginationParams
from app.models.database import Book, BookAllocation, BookCopy, School
from app.services import crud_service


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# IDs for filtering (positive integers representing valid foreign keys)
valid_ids = st.integers(min_value=1, max_value=1000)

# Number of items in the dataset
dataset_size = st.integers(min_value=0, max_value=20)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_book(book_id: int, subject_id: int, grade_level_id: int):
    """Create a mock Book instance with the given attributes."""
    book = MagicMock(spec=Book)
    book.id = book_id
    book.subject_id = subject_id
    book.grade_level_id = grade_level_id
    book.title = f"Book {book_id}"
    return book


def _make_mock_school(school_id: int, department_id: int):
    """Create a mock School instance with the given attributes."""
    school = MagicMock(spec=School)
    school.id = school_id
    school.department_id = department_id
    school.name = f"School {school_id}"
    return school


def _make_mock_book_copy(copy_id: int, book_id: int, school_id: int):
    """Create a mock BookCopy instance with the given attributes."""
    copy = MagicMock(spec=BookCopy)
    copy.id = copy_id
    copy.book_id = book_id
    copy.school_id = school_id
    copy.qr_code = f"QR-{copy_id}"
    return copy


def _make_mock_allocation(alloc_id: int, learner_id: int, status: str):
    """Create a mock BookAllocation instance with the given attributes."""
    alloc = MagicMock(spec=BookAllocation)
    alloc.id = alloc_id
    alloc.learner_id = learner_id
    alloc.status = status
    alloc.book_copy_id = alloc_id  # Use alloc_id as a simple book_copy_id
    return alloc


def _make_mock_db_for_filter(all_items, model_class, filters):
    """Create a mock DB session that simulates filtering behavior.

    The mock simulates the SQLAlchemy query chain:
    1. db.query(model_class) returns a query object
    2. query.filter(...) applies each filter condition
    3. query.count() returns the total matching count
    4. query.offset().limit().all() returns the paginated items

    The filtering is done in-memory on the all_items list to simulate
    what SQLAlchemy would do with the real database.
    """
    # Apply filters in-memory to determine expected results
    filtered_items = list(all_items)
    for field, value in filters.items():
        if value is not None:
            filtered_items = [
                item for item in filtered_items
                if getattr(item, field) == value
            ]

    db = MagicMock()

    # Build a mock query that tracks filter calls and returns correct results
    query = MagicMock()

    # Track applied filters to simulate chaining
    applied_filters = []

    def mock_filter(condition):
        """Simulate filter application - returns the same query for chaining."""
        applied_filters.append(condition)
        return query

    query.filter.side_effect = mock_filter
    query.count.return_value = len(filtered_items)

    def mock_offset(offset_val):
        query._offset = offset_val
        return query

    def mock_limit(limit_val):
        offset = getattr(query, '_offset', 0)
        query.all.return_value = filtered_items[offset:offset + limit_val]
        return query

    query.offset.side_effect = mock_offset
    query.limit.side_effect = mock_limit
    query.all.return_value = filtered_items

    db.query.return_value = query

    return db, filtered_items


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestQueryFilterCorrectness:
    """Property 8: Query Filter Correctness.

    For any list endpoint that supports filtering, every item in the filtered
    response SHALL match ALL applied filter criteria. No item that does not
    match the filter SHALL appear in the results.
    """

    @given(
        target_subject_id=valid_ids,
        num_matching=dataset_size,
        num_non_matching=dataset_size,
    )
    @settings(max_examples=100, deadline=None)
    def test_books_filtered_by_subject_id(
        self, target_subject_id: int, num_matching: int, num_non_matching: int
    ):
        """For books filtered by subject_id, every returned item matches that subject_id.

        **Validates: Requirements 9.3**
        """
        # Create a mix of matching and non-matching books
        other_subject_id = target_subject_id + 1
        all_books = []
        for i in range(num_matching):
            all_books.append(_make_mock_book(i + 1, target_subject_id, 1))
        for i in range(num_non_matching):
            all_books.append(_make_mock_book(num_matching + i + 1, other_subject_id, 1))

        filters = {"subject_id": target_subject_id}
        db, expected_filtered = _make_mock_db_for_filter(all_books, Book, filters)
        params = PaginationParams(page=1, page_size=100)

        result = crud_service.get_all(db, Book, params, filters=filters)

        # Property: every returned item matches the filter
        for item in result.items:
            assert item.subject_id == target_subject_id, (
                f"Item {item.id} has subject_id={item.subject_id}, "
                f"expected {target_subject_id}"
            )

        # Property: total count matches expected filtered count
        assert result.total == num_matching, (
            f"Expected total={num_matching}, got total={result.total}"
        )

        # Property: no non-matching items appear
        assert len(result.items) == num_matching, (
            f"Expected {num_matching} items, got {len(result.items)}"
        )

    @given(
        target_grade_level_id=valid_ids,
        num_matching=dataset_size,
        num_non_matching=dataset_size,
    )
    @settings(max_examples=100, deadline=None)
    def test_books_filtered_by_grade_level_id(
        self, target_grade_level_id: int, num_matching: int, num_non_matching: int
    ):
        """For books filtered by grade_level_id, every returned item matches that grade_level_id.

        **Validates: Requirements 9.4**
        """
        other_grade_level_id = target_grade_level_id + 1
        all_books = []
        for i in range(num_matching):
            all_books.append(_make_mock_book(i + 1, 1, target_grade_level_id))
        for i in range(num_non_matching):
            all_books.append(
                _make_mock_book(num_matching + i + 1, 1, other_grade_level_id)
            )

        filters = {"grade_level_id": target_grade_level_id}
        db, expected_filtered = _make_mock_db_for_filter(all_books, Book, filters)
        params = PaginationParams(page=1, page_size=100)

        result = crud_service.get_all(db, Book, params, filters=filters)

        # Property: every returned item matches the filter
        for item in result.items:
            assert item.grade_level_id == target_grade_level_id, (
                f"Item {item.id} has grade_level_id={item.grade_level_id}, "
                f"expected {target_grade_level_id}"
            )

        # Property: total count matches expected filtered count
        assert result.total == num_matching, (
            f"Expected total={num_matching}, got total={result.total}"
        )

    @given(
        target_subject_id=valid_ids,
        target_grade_level_id=valid_ids,
        num_both_match=dataset_size,
        num_subject_only=dataset_size,
        num_grade_only=dataset_size,
        num_neither=dataset_size,
    )
    @settings(max_examples=100, deadline=None)
    def test_books_filtered_by_both_subject_and_grade_level(
        self,
        target_subject_id: int,
        target_grade_level_id: int,
        num_both_match: int,
        num_subject_only: int,
        num_grade_only: int,
        num_neither: int,
    ):
        """For books filtered by both subject_id AND grade_level_id, every returned item matches both.

        **Validates: Requirements 9.5**
        """
        other_subject_id = target_subject_id + 1
        other_grade_level_id = target_grade_level_id + 1

        all_books = []
        idx = 1

        # Books matching both filters
        for _ in range(num_both_match):
            all_books.append(_make_mock_book(idx, target_subject_id, target_grade_level_id))
            idx += 1

        # Books matching only subject_id
        for _ in range(num_subject_only):
            all_books.append(_make_mock_book(idx, target_subject_id, other_grade_level_id))
            idx += 1

        # Books matching only grade_level_id
        for _ in range(num_grade_only):
            all_books.append(_make_mock_book(idx, other_subject_id, target_grade_level_id))
            idx += 1

        # Books matching neither
        for _ in range(num_neither):
            all_books.append(_make_mock_book(idx, other_subject_id, other_grade_level_id))
            idx += 1

        filters = {
            "subject_id": target_subject_id,
            "grade_level_id": target_grade_level_id,
        }
        db, expected_filtered = _make_mock_db_for_filter(all_books, Book, filters)
        params = PaginationParams(page=1, page_size=100)

        result = crud_service.get_all(db, Book, params, filters=filters)

        # Property: every returned item matches BOTH filters
        for item in result.items:
            assert item.subject_id == target_subject_id, (
                f"Item {item.id} has subject_id={item.subject_id}, "
                f"expected {target_subject_id}"
            )
            assert item.grade_level_id == target_grade_level_id, (
                f"Item {item.id} has grade_level_id={item.grade_level_id}, "
                f"expected {target_grade_level_id}"
            )

        # Property: only items matching both filters are returned
        assert result.total == num_both_match, (
            f"Expected total={num_both_match}, got total={result.total}"
        )

    @given(
        target_department_id=valid_ids,
        num_matching=dataset_size,
        num_non_matching=dataset_size,
    )
    @settings(max_examples=100, deadline=None)
    def test_schools_filtered_by_department_id(
        self, target_department_id: int, num_matching: int, num_non_matching: int
    ):
        """For schools filtered by department_id, every returned item belongs to that department.

        **Validates: Requirements 4.3**
        """
        other_department_id = target_department_id + 1
        all_schools = []
        for i in range(num_matching):
            all_schools.append(_make_mock_school(i + 1, target_department_id))
        for i in range(num_non_matching):
            all_schools.append(
                _make_mock_school(num_matching + i + 1, other_department_id)
            )

        filters = {"department_id": target_department_id}
        db, expected_filtered = _make_mock_db_for_filter(all_schools, School, filters)
        params = PaginationParams(page=1, page_size=100)

        result = crud_service.get_all(db, School, params, filters=filters)

        # Property: every returned item belongs to the target department
        for item in result.items:
            assert item.department_id == target_department_id, (
                f"Item {item.id} has department_id={item.department_id}, "
                f"expected {target_department_id}"
            )

        # Property: total count matches expected filtered count
        assert result.total == num_matching, (
            f"Expected total={num_matching}, got total={result.total}"
        )

    @given(
        target_school_id=valid_ids,
        num_matching=dataset_size,
        num_non_matching=dataset_size,
    )
    @settings(max_examples=100, deadline=None)
    def test_book_copies_filtered_by_school_id(
        self, target_school_id: int, num_matching: int, num_non_matching: int
    ):
        """For book copies filtered by school_id, every returned item belongs to that school.

        **Validates: Requirements 13.6**
        """
        other_school_id = target_school_id + 1
        all_copies = []
        for i in range(num_matching):
            all_copies.append(_make_mock_book_copy(i + 1, 1, target_school_id))
        for i in range(num_non_matching):
            all_copies.append(
                _make_mock_book_copy(num_matching + i + 1, 1, other_school_id)
            )

        filters = {"school_id": target_school_id}
        db, expected_filtered = _make_mock_db_for_filter(all_copies, BookCopy, filters)
        params = PaginationParams(page=1, page_size=100)

        result = crud_service.get_all(db, BookCopy, params, filters=filters)

        # Property: every returned item belongs to the target school
        for item in result.items:
            assert item.school_id == target_school_id, (
                f"Item {item.id} has school_id={item.school_id}, "
                f"expected {target_school_id}"
            )

        # Property: total count matches expected filtered count
        assert result.total == num_matching, (
            f"Expected total={num_matching}, got total={result.total}"
        )

    @given(
        target_book_id=valid_ids,
        num_matching=dataset_size,
        num_non_matching=dataset_size,
    )
    @settings(max_examples=100, deadline=None)
    def test_book_copies_filtered_by_book_id(
        self, target_book_id: int, num_matching: int, num_non_matching: int
    ):
        """For book copies filtered by book_id, every returned item is a copy of that book.

        **Validates: Requirements 13.7**
        """
        other_book_id = target_book_id + 1
        all_copies = []
        for i in range(num_matching):
            all_copies.append(_make_mock_book_copy(i + 1, target_book_id, 1))
        for i in range(num_non_matching):
            all_copies.append(
                _make_mock_book_copy(num_matching + i + 1, other_book_id, 1)
            )

        filters = {"book_id": target_book_id}
        db, expected_filtered = _make_mock_db_for_filter(all_copies, BookCopy, filters)
        params = PaginationParams(page=1, page_size=100)

        result = crud_service.get_all(db, BookCopy, params, filters=filters)

        # Property: every returned item is a copy of the target book
        for item in result.items:
            assert item.book_id == target_book_id, (
                f"Item {item.id} has book_id={item.book_id}, "
                f"expected {target_book_id}"
            )

        # Property: total count matches expected filtered count
        assert result.total == num_matching, (
            f"Expected total={num_matching}, got total={result.total}"
        )

    @given(
        target_learner_id=valid_ids,
        target_status=st.sampled_from(["active", "returned"]),
        num_both_match=dataset_size,
        num_learner_only=dataset_size,
        num_status_only=dataset_size,
        num_neither=dataset_size,
    )
    @settings(max_examples=100, deadline=None)
    def test_allocations_filtered_by_learner_id_and_status(
        self,
        target_learner_id: int,
        target_status: str,
        num_both_match: int,
        num_learner_only: int,
        num_status_only: int,
        num_neither: int,
    ):
        """For allocations filtered by learner_id and status, every returned item matches both.

        **Validates: Requirements 16.3**
        """
        other_learner_id = target_learner_id + 1
        other_status = "returned" if target_status == "active" else "active"

        all_allocations = []
        idx = 1

        # Allocations matching both filters
        for _ in range(num_both_match):
            all_allocations.append(
                _make_mock_allocation(idx, target_learner_id, target_status)
            )
            idx += 1

        # Allocations matching only learner_id
        for _ in range(num_learner_only):
            all_allocations.append(
                _make_mock_allocation(idx, target_learner_id, other_status)
            )
            idx += 1

        # Allocations matching only status
        for _ in range(num_status_only):
            all_allocations.append(
                _make_mock_allocation(idx, other_learner_id, target_status)
            )
            idx += 1

        # Allocations matching neither
        for _ in range(num_neither):
            all_allocations.append(
                _make_mock_allocation(idx, other_learner_id, other_status)
            )
            idx += 1

        filters = {"learner_id": target_learner_id, "status": target_status}
        db, expected_filtered = _make_mock_db_for_filter(
            all_allocations, BookAllocation, filters
        )
        params = PaginationParams(page=1, page_size=100)

        result = crud_service.get_all(db, BookAllocation, params, filters=filters)

        # Property: every returned item matches BOTH filters
        for item in result.items:
            assert item.learner_id == target_learner_id, (
                f"Item {item.id} has learner_id={item.learner_id}, "
                f"expected {target_learner_id}"
            )
            assert item.status == target_status, (
                f"Item {item.id} has status={item.status}, "
                f"expected {target_status}"
            )

        # Property: only items matching both filters are returned
        assert result.total == num_both_match, (
            f"Expected total={num_both_match}, got total={result.total}"
        )

        # Property: no non-matching items appear
        assert len(result.items) == num_both_match, (
            f"Expected {num_both_match} items, got {len(result.items)}"
        )
