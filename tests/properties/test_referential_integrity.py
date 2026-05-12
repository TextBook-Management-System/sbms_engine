# Feature: sbms-api-endpoints, Property 15: Referential Integrity on Delete
"""
Property-based tests for referential integrity on delete.

Tests validate that:
- For any entity that is referenced by other records (grade level referenced
  by books, department referenced by schools, book referenced by book copies),
  a DELETE request SHALL raise ConflictError (409) rather than deleting the record.

**Validates: Requirements 2.14, 3.8**
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.exceptions import ConflictError
from app.services import crud_service
from app.models.database import (
    GradeLevel,
    Subject,
    Department,
    School,
    Book,
    BookCopy,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy: generate positive entity IDs (BIGINT UNSIGNED range)
entity_ids = st.integers(min_value=1, max_value=2**63 - 1)

# Strategy: generate positive reference counts (> 0 means references exist)
positive_ref_counts = st.integers(min_value=1, max_value=10000)


# ---------------------------------------------------------------------------
# Helper: create a mock DB session for delete with reference checks
# ---------------------------------------------------------------------------

def _create_mock_db_for_delete(model_class, entity_id, ref_count):
    """Create a mock DB session that simulates:
    1. get_by_id succeeds (record exists)
    2. Reference count query returns ref_count > 0

    Args:
        model_class: The SQLAlchemy model class being deleted.
        entity_id: The ID of the entity to delete.
        ref_count: The number of referencing records (> 0 triggers ConflictError).

    Returns:
        A mock DB session configured for the delete scenario.
    """
    db = MagicMock()

    # Mock instance returned by get_by_id (db.query(model_class).filter(...).first())
    mock_instance = MagicMock()
    mock_instance.id = entity_id

    # Set up the query chain for get_by_id
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_filter.first.return_value = mock_instance

    # Set up the query chain for reference count check
    mock_ref_query = MagicMock()
    mock_ref_filter = MagicMock()
    mock_ref_filter.scalar.return_value = ref_count

    # db.query() needs to handle both the model query and the count query
    # First call: get_by_id query (db.query(model_class))
    # Second call: reference count query (db.query(func.count(...)))
    call_count = {"value": 0}

    def query_side_effect(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 1:
            # get_by_id query
            return mock_query
        else:
            # reference count query
            return mock_ref_query

    db.query.side_effect = query_side_effect
    mock_query.filter.return_value = mock_filter
    mock_ref_query.filter.return_value = mock_ref_filter

    return db


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestReferentialIntegrityOnDelete:
    """
    Property 15: For any entity that is referenced by other records,
    a DELETE request SHALL raise ConflictError (409) rather than deleting
    the record and violating referential integrity.
    """

    @given(
        entity_id=entity_ids,
        ref_count=positive_ref_counts,
    )
    @settings(max_examples=100, deadline=None)
    def test_grade_level_delete_blocked_when_referenced_by_books(
        self, entity_id: int, ref_count: int
    ):
        """
        Deleting a grade level that is referenced by books SHALL raise
        ConflictError with 'Cannot delete' in the message.

        **Validates: Requirements 2.14**
        """
        db = _create_mock_db_for_delete(GradeLevel, entity_id, ref_count)

        with pytest.raises(ConflictError) as exc_info:
            crud_service.delete(
                db,
                GradeLevel,
                entity_id,
                check_references=[(Book, "grade_level_id")],
            )

        assert "Cannot delete" in exc_info.value.detail
        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"
        # Verify the record was NOT deleted
        db.delete.assert_not_called()
        db.commit.assert_not_called()

    @given(
        entity_id=entity_ids,
        ref_count=positive_ref_counts,
    )
    @settings(max_examples=100, deadline=None)
    def test_subject_delete_blocked_when_referenced_by_books(
        self, entity_id: int, ref_count: int
    ):
        """
        Deleting a subject that is referenced by books SHALL raise
        ConflictError with 'Cannot delete' in the message.

        **Validates: Requirements 2.14**
        """
        db = _create_mock_db_for_delete(Subject, entity_id, ref_count)

        with pytest.raises(ConflictError) as exc_info:
            crud_service.delete(
                db,
                Subject,
                entity_id,
                check_references=[(Book, "subject_id")],
            )

        assert "Cannot delete" in exc_info.value.detail
        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"
        db.delete.assert_not_called()
        db.commit.assert_not_called()

    @given(
        entity_id=entity_ids,
        ref_count=positive_ref_counts,
    )
    @settings(max_examples=100, deadline=None)
    def test_department_delete_blocked_when_referenced_by_schools(
        self, entity_id: int, ref_count: int
    ):
        """
        Deleting a department that is referenced by schools SHALL raise
        ConflictError with 'Cannot delete' in the message.

        **Validates: Requirements 3.8**
        """
        db = _create_mock_db_for_delete(Department, entity_id, ref_count)

        with pytest.raises(ConflictError) as exc_info:
            crud_service.delete(
                db,
                Department,
                entity_id,
                check_references=[(School, "department_id")],
            )

        assert "Cannot delete" in exc_info.value.detail
        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"
        db.delete.assert_not_called()
        db.commit.assert_not_called()

    @given(
        entity_id=entity_ids,
        ref_count=positive_ref_counts,
    )
    @settings(max_examples=100, deadline=None)
    def test_book_delete_blocked_when_referenced_by_book_copies(
        self, entity_id: int, ref_count: int
    ):
        """
        Deleting a book that is referenced by book copies SHALL raise
        ConflictError with 'Cannot delete' in the message.

        **Validates: Requirements 2.14**
        """
        db = _create_mock_db_for_delete(Book, entity_id, ref_count)

        with pytest.raises(ConflictError) as exc_info:
            crud_service.delete(
                db,
                Book,
                entity_id,
                check_references=[(BookCopy, "book_id")],
            )

        assert "Cannot delete" in exc_info.value.detail
        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"
        db.delete.assert_not_called()
        db.commit.assert_not_called()

    @given(
        entity_id=entity_ids,
        ref_count=positive_ref_counts,
    )
    @settings(max_examples=100, deadline=None)
    def test_conflict_error_message_includes_related_table_name(
        self, entity_id: int, ref_count: int
    ):
        """
        The ConflictError detail message SHALL include the related table name
        to help identify which references are blocking the delete.

        **Validates: Requirements 2.14, 3.8**
        """
        # Test with Department -> Schools relationship
        db = _create_mock_db_for_delete(Department, entity_id, ref_count)

        with pytest.raises(ConflictError) as exc_info:
            crud_service.delete(
                db,
                Department,
                entity_id,
                check_references=[(School, "department_id")],
            )

        # The error message should mention the related table
        assert "schools" in exc_info.value.detail.lower()

    @given(
        entity_id=entity_ids,
        ref_count=positive_ref_counts,
    )
    @settings(max_examples=100, deadline=None)
    def test_conflict_error_message_includes_entity_name(
        self, entity_id: int, ref_count: int
    ):
        """
        The ConflictError detail message SHALL include the entity class name
        being deleted to provide clear context.

        **Validates: Requirements 2.14, 3.8**
        """
        # Test with GradeLevel -> Books relationship
        db = _create_mock_db_for_delete(GradeLevel, entity_id, ref_count)

        with pytest.raises(ConflictError) as exc_info:
            crud_service.delete(
                db,
                GradeLevel,
                entity_id,
                check_references=[(Book, "grade_level_id")],
            )

        # The error message should mention the entity being deleted
        assert "GradeLevel" in exc_info.value.detail
