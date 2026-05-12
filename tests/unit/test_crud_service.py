"""Unit tests for app.services.crud_service module."""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginationParams
from app.services import crud_service


class FakeModel:
    """Fake SQLAlchemy model for testing."""

    __name__ = "FakeModel"
    __tablename__ = "fake_models"

    id = None
    name = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeRelatedModel:
    """Fake related model for referential integrity tests."""

    __name__ = "FakeRelatedModel"
    __tablename__ = "fake_related_models"

    id = None
    fake_model_id = None


def _make_mock_db():
    """Create a mock database session."""
    db = MagicMock()
    # Make query chainable
    db.query.return_value = db.query
    db.query.filter.return_value = db.query
    db.query.filter.return_value.first.return_value = None
    return db


class TestCreate:
    """Tests for crud_service.create."""

    def test_create_without_unique_fields(self):
        """Creates a record without uniqueness checks."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = crud_service.create(db, FakeModel, {"name": "Test"})

        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_create_with_unique_fields_no_conflict(self):
        """Creates a record when unique field value doesn't exist."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = crud_service.create(
            db, FakeModel, {"name": "Unique"}, unique_fields=["name"]
        )

        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_create_with_unique_fields_conflict(self):
        """Raises ConflictError when unique field value already exists."""
        db = MagicMock()
        existing = FakeModel(id=1, name="Duplicate")
        db.query.return_value.filter.return_value.first.return_value = existing

        with pytest.raises(ConflictError) as exc_info:
            crud_service.create(
                db, FakeModel, {"name": "Duplicate"}, unique_fields=["name"]
            )

        assert "already exists" in str(exc_info.value.detail)
        db.add.assert_not_called()

    def test_create_with_none_unique_field_value_skips_check(self):
        """Skips uniqueness check when the field value is None."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = crud_service.create(
            db, FakeModel, {"name": None}, unique_fields=["name"]
        )

        db.add.assert_called_once()
        db.commit.assert_called_once()


class TestGetById:
    """Tests for crud_service.get_by_id."""

    def test_get_by_id_found(self):
        """Returns the record when it exists."""
        db = MagicMock()
        expected = FakeModel(id=1, name="Test")
        db.query.return_value.filter.return_value.first.return_value = expected

        result = crud_service.get_by_id(db, FakeModel, 1)

        assert result == expected

    def test_get_by_id_not_found(self):
        """Raises NotFoundError when record doesn't exist."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            crud_service.get_by_id(db, FakeModel, 999)

        assert "999" in str(exc_info.value.detail)
        assert "FakeModel" in str(exc_info.value.detail)


class TestGetAll:
    """Tests for crud_service.get_all."""

    def test_get_all_no_filters(self):
        """Returns paginated results without filters."""
        db = MagicMock()
        query_mock = MagicMock()
        db.query.return_value = query_mock
        query_mock.count.return_value = 2
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = [
            FakeModel(id=1, name="A"),
            FakeModel(id=2, name="B"),
        ]

        params = PaginationParams(page=1, page_size=20)
        result = crud_service.get_all(db, FakeModel, params)

        assert result.total == 2
        assert len(result.items) == 2
        assert result.page == 1

    def test_get_all_with_filters(self):
        """Applies filters to the query."""
        db = MagicMock()
        query_mock = MagicMock()
        db.query.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.count.return_value = 1
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = [FakeModel(id=1, name="Filtered")]

        params = PaginationParams(page=1, page_size=20)
        result = crud_service.get_all(
            db, FakeModel, params, filters={"name": "Filtered"}
        )

        assert result.total == 1
        query_mock.filter.assert_called_once()

    def test_get_all_skips_none_filters(self):
        """Skips filter fields with None values."""
        db = MagicMock()
        query_mock = MagicMock()
        db.query.return_value = query_mock
        query_mock.count.return_value = 0
        query_mock.offset.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = []

        params = PaginationParams(page=1, page_size=20)
        result = crud_service.get_all(
            db, FakeModel, params, filters={"name": None}
        )

        # filter should not be called since value is None
        query_mock.filter.assert_not_called()


class TestUpdate:
    """Tests for crud_service.update."""

    def test_update_success(self):
        """Updates a record and returns it."""
        db = MagicMock()
        existing = FakeModel(id=1, name="Old")
        db.query.return_value.filter.return_value.first.return_value = existing

        result = crud_service.update(db, FakeModel, 1, {"name": "New"})

        assert existing.name == "New"
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_update_not_found(self):
        """Raises NotFoundError when record doesn't exist."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            crud_service.update(db, FakeModel, 999, {"name": "New"})

    def test_update_with_unique_conflict(self):
        """Raises ConflictError when update would create a duplicate."""
        db = MagicMock()
        existing = FakeModel(id=1, name="Old")
        other = FakeModel(id=2, name="Taken")

        # First call for get_by_id returns the record to update
        # Second call for uniqueness check returns the conflicting record
        db.query.return_value.filter.return_value.first.side_effect = [
            existing,  # get_by_id
            other,  # uniqueness check finds conflict
        ]

        with pytest.raises(ConflictError):
            crud_service.update(
                db, FakeModel, 1, {"name": "Taken"}, unique_fields=["name"]
            )


class TestDelete:
    """Tests for crud_service.delete."""

    def test_delete_success(self):
        """Deletes a record when no references exist."""
        db = MagicMock()
        existing = FakeModel(id=1, name="ToDelete")
        db.query.return_value.filter.return_value.first.return_value = existing

        crud_service.delete(db, FakeModel, 1)

        db.delete.assert_called_once_with(existing)
        db.commit.assert_called_once()

    def test_delete_not_found(self):
        """Raises NotFoundError when record doesn't exist."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            crud_service.delete(db, FakeModel, 999)

    def test_delete_with_references_conflict(self):
        """Raises ConflictError when referenced by other records."""
        db = MagicMock()
        existing = FakeModel(id=1, name="Referenced")

        # get_by_id returns the record
        db.query.return_value.filter.return_value.first.return_value = existing
        # Reference count check returns > 0
        db.query.return_value.filter.return_value.scalar.return_value = 3

        with pytest.raises(ConflictError) as exc_info:
            crud_service.delete(
                db,
                FakeModel,
                1,
                check_references=[(FakeRelatedModel, "fake_model_id")],
            )

        assert "Cannot delete" in str(exc_info.value.detail)
        assert "referenced" in str(exc_info.value.detail)
        db.delete.assert_not_called()

    def test_delete_with_no_references_succeeds(self):
        """Deletes when check_references finds no related records."""
        db = MagicMock()
        existing = FakeModel(id=1, name="Safe")

        # get_by_id returns the record
        db.query.return_value.filter.return_value.first.return_value = existing
        # Reference count check returns 0
        db.query.return_value.filter.return_value.scalar.return_value = 0

        crud_service.delete(
            db,
            FakeModel,
            1,
            check_references=[(FakeRelatedModel, "fake_model_id")],
        )

        db.delete.assert_called_once_with(existing)
        db.commit.assert_called_once()
