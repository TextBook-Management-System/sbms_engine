# Feature: sbms-api-endpoints, Property 1: CRUD Round-Trip Preservation
"""
Property-based tests for CRUD round-trip preservation.

Tests validate that for any entity type and any valid creation payload,
creating the entity via crud_service.create() and then retrieving it via
crud_service.get_by_id() produces a response whose fields match the
original creation payload (plus server-generated fields like id, created_at).

Tests the crud_service directly (not via HTTP) with a mock DB session.

**Validates: Requirements 2.1, 2.3, 2.7, 2.9, 3.1, 3.3, 4.1, 4.4**
"""

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.database import Department, GradeLevel, Subject
from app.services import crud_service


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Grade level names: 1-100 characters, printable strings without leading/trailing whitespace
grade_level_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() == s and len(s.strip()) >= 1)

# Subject names: 1-100 characters
subject_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() == s and len(s.strip()) >= 1)

# Department names: 1-200 characters
department_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip() == s and len(s.strip()) >= 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db_for_roundtrip(model_class, data: dict):
    """Create a mock DB session that simulates create → refresh → get_by_id.

    The mock simulates:
    1. No existing record with the same unique field (uniqueness check passes)
    2. db.add() stores the instance
    3. db.commit() succeeds
    4. db.refresh() assigns an id and created_at to the instance
    5. get_by_id query returns the same instance
    """
    db = MagicMock()
    created_instance = None

    def capture_add(instance):
        nonlocal created_instance
        created_instance = instance

    def simulate_refresh(instance):
        # Simulate server-generated fields
        instance.id = 1
        if hasattr(instance, "created_at"):
            from datetime import datetime
            instance.created_at = datetime(2024, 1, 1, 12, 0, 0)
        if hasattr(instance, "updated_at"):
            from datetime import datetime
            instance.updated_at = datetime(2024, 1, 1, 12, 0, 0)

    def get_by_id_query(*args, **kwargs):
        """Simulate the query chain for get_by_id."""
        filter_mock = MagicMock()
        filter_mock.first.return_value = created_instance
        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        return query_mock

    # Uniqueness check: no existing record found
    uniqueness_query = MagicMock()
    uniqueness_query.filter.return_value = uniqueness_query
    uniqueness_query.first.return_value = None

    # Set up db.query to handle both uniqueness check and get_by_id
    # First call is for uniqueness check (during create), second is for get_by_id
    db.query.side_effect = [uniqueness_query, get_by_id_query()]

    db.add.side_effect = capture_add
    db.refresh.side_effect = simulate_refresh

    return db


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestCRUDRoundTripPreservation:
    """Property 1: CRUD Round-Trip Preservation.

    For any entity type and any valid creation payload, creating the entity
    via crud_service.create() and then retrieving it via crud_service.get_by_id()
    SHALL produce a response whose fields match the original creation payload
    (plus server-generated fields like id, created_at).
    """

    @given(name=grade_level_names)
    @settings(max_examples=100, deadline=None)
    def test_grade_level_roundtrip(self, name: str):
        """Creating a grade level and retrieving it preserves the name field.

        **Validates: Requirements 2.1, 2.3**
        """
        data = {"name": name}
        db = _make_mock_db_for_roundtrip(GradeLevel, data)

        # Create
        created = crud_service.create(db, GradeLevel, data, unique_fields=["name"])

        # Reset query side_effect for get_by_id call
        get_query = MagicMock()
        get_query.filter.return_value = get_query
        get_query.first.return_value = created
        db.query.side_effect = None
        db.query.return_value = get_query

        # Retrieve
        retrieved = crud_service.get_by_id(db, GradeLevel, created.id)

        # Assert round-trip preservation
        assert retrieved.id is not None, "Server should assign an id"
        assert retrieved.name == name, (
            f"Expected name='{name}', got name='{retrieved.name}'"
        )

    @given(name=subject_names)
    @settings(max_examples=100, deadline=None)
    def test_subject_roundtrip(self, name: str):
        """Creating a subject and retrieving it preserves the name field.

        **Validates: Requirements 2.7, 2.9**
        """
        data = {"name": name}
        db = _make_mock_db_for_roundtrip(Subject, data)

        # Create
        created = crud_service.create(db, Subject, data, unique_fields=["name"])

        # Reset query side_effect for get_by_id call
        get_query = MagicMock()
        get_query.filter.return_value = get_query
        get_query.first.return_value = created
        db.query.side_effect = None
        db.query.return_value = get_query

        # Retrieve
        retrieved = crud_service.get_by_id(db, Subject, created.id)

        # Assert round-trip preservation
        assert retrieved.id is not None, "Server should assign an id"
        assert retrieved.name == name, (
            f"Expected name='{name}', got name='{retrieved.name}'"
        )

    @given(name=department_names)
    @settings(max_examples=100, deadline=None)
    def test_department_roundtrip(self, name: str):
        """Creating a department and retrieving it preserves the name field.

        **Validates: Requirements 3.1, 3.3**
        """
        data = {"name": name}
        db = _make_mock_db_for_roundtrip(Department, data)

        # Create
        created = crud_service.create(db, Department, data, unique_fields=["name"])

        # Reset query side_effect for get_by_id call
        get_query = MagicMock()
        get_query.filter.return_value = get_query
        get_query.first.return_value = created
        db.query.side_effect = None
        db.query.return_value = get_query

        # Retrieve
        retrieved = crud_service.get_by_id(db, Department, created.id)

        # Assert round-trip preservation
        assert retrieved.id is not None, "Server should assign an id"
        assert retrieved.name == name, (
            f"Expected name='{name}', got name='{retrieved.name}'"
        )
        # Server-generated fields should be present
        assert retrieved.created_at is not None, "Server should assign created_at"
        assert retrieved.updated_at is not None, "Server should assign updated_at"
