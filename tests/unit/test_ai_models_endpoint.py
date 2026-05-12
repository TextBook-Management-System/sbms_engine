"""Unit tests for app.api.v1.endpoints.ai_models module.

Tests the AI model versions endpoint handlers with mocked DB sessions,
validating requirements 14.1–14.8.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginatedResponse, PaginationParams
from app.models.database import AIModelVersion
from app.api.v1.endpoints.ai_models import (
    list_ai_models,
    register_ai_model,
    get_active_ai_model,
    activate_ai_model,
)
from app.schemas.ai_models import AIModelCreate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ai_model(**overrides):
    """Create a fake AIModelVersion instance with default values."""
    defaults = {
        "id": 1,
        "model_name": "condition-scanner",
        "model_version": "1.0.0",
        "model_type": "book_condition",
        "is_active": False,
        "created_at": datetime(2024, 1, 1, 12, 0, 0),
    }
    defaults.update(overrides)
    model = MagicMock(spec=AIModelVersion)
    for key, value in defaults.items():
        setattr(model, key, value)
    return model


# ---------------------------------------------------------------------------
# List AI Models Tests
# ---------------------------------------------------------------------------


class TestListAIModels:
    """Tests for list_ai_models endpoint handler."""

    def test_list_returns_paginated_response(self):
        """Returns a paginated list of all AI model versions.

        Validates: Requirement 14.1
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.count.return_value = 2
        mock_query.offset.return_value.limit.return_value.all.return_value = [
            _make_ai_model(id=1),
            _make_ai_model(id=2),
        ]

        result = list_ai_models(params=params, db=db)

        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 20
        assert len(result.items) == 2

    def test_list_empty(self):
        """Returns empty paginated response when no models exist.

        Validates: Requirement 14.1
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)

        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.offset.return_value.limit.return_value.all.return_value = []

        result = list_ai_models(params=params, db=db)

        assert result.total == 0
        assert result.items == []


# ---------------------------------------------------------------------------
# Register AI Model Tests
# ---------------------------------------------------------------------------


class TestRegisterAIModel:
    """Tests for register_ai_model endpoint handler."""

    def test_register_success(self):
        """Registers a new AI model with is_active=False.

        Validates: Requirement 14.2
        """
        db = MagicMock()
        # No duplicate exists
        db.query.return_value.filter.return_value.first.return_value = None

        payload = AIModelCreate(
            model_name="condition-scanner",
            model_version="1.0.0",
            model_type="book_condition",
        )

        result = register_ai_model(payload, db)

        # Verify db.add was called
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

        # Verify the model was created with is_active=False
        added_model = db.add.call_args[0][0]
        assert added_model.model_name == "condition-scanner"
        assert added_model.model_version == "1.0.0"
        assert added_model.model_type == "book_condition"
        assert added_model.is_active is False

    def test_register_duplicate_name_version_raises_conflict(self):
        """Returns 409 when model_name + model_version already exists.

        Validates: Requirement 14.8
        """
        db = MagicMock()
        # Duplicate exists
        db.query.return_value.filter.return_value.first.return_value = _make_ai_model()

        payload = AIModelCreate(
            model_name="condition-scanner",
            model_version="1.0.0",
            model_type="book_condition",
        )

        with pytest.raises(ConflictError) as exc_info:
            register_ai_model(payload, db)

        assert "model_name" in exc_info.value.detail.lower() or "already exists" in exc_info.value.detail.lower()

    def test_register_same_name_different_version_succeeds(self):
        """Allows same model_name with different model_version.

        Validates: Requirement 14.2, 14.8
        """
        db = MagicMock()
        # No duplicate for this specific combination
        db.query.return_value.filter.return_value.first.return_value = None

        payload = AIModelCreate(
            model_name="condition-scanner",
            model_version="2.0.0",
            model_type="book_condition",
        )

        result = register_ai_model(payload, db)

        db.add.assert_called_once()
        db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Get Active AI Model Tests
# ---------------------------------------------------------------------------


class TestGetActiveAIModel:
    """Tests for get_active_ai_model endpoint handler."""

    def test_get_active_found(self):
        """Returns the currently active AI model.

        Validates: Requirement 14.4
        """
        db = MagicMock()
        active_model = _make_ai_model(is_active=True)
        db.query.return_value.filter.return_value.first.return_value = active_model

        result = get_active_ai_model(db)

        assert result == active_model

    def test_get_active_not_found(self):
        """Returns 404 when no active model exists.

        Validates: Requirement 14.5
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            get_active_ai_model(db)

        assert "no active" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Activate AI Model Tests
# ---------------------------------------------------------------------------


class TestActivateAIModel:
    """Tests for activate_ai_model endpoint handler."""

    def test_activate_success(self):
        """Activates a model and deactivates others of same type.

        Validates: Requirement 14.3
        """
        db = MagicMock()
        model = _make_ai_model(id=1, model_type="book_condition", is_active=False)
        db.query.return_value.filter.return_value.first.return_value = model

        # Mock the update query for deactivating others
        update_query = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value = update_query

        result = activate_ai_model(1, db)

        # Verify the model was activated
        assert model.is_active is True
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(model)

    def test_activate_not_found(self):
        """Returns 404 when model ID does not exist.

        Validates: Requirement 14.6
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            activate_ai_model(999, db)

        assert "999" in exc_info.value.detail

    def test_activate_already_active_model(self):
        """Activating an already active model is idempotent.

        Validates: Requirement 14.3
        """
        db = MagicMock()
        model = _make_ai_model(id=1, model_type="book_condition", is_active=True)
        db.query.return_value.filter.return_value.first.return_value = model

        update_query = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value = update_query

        result = activate_ai_model(1, db)

        # Model should still be active
        assert model.is_active is True
        db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Validation Tests (Pydantic schema level)
# ---------------------------------------------------------------------------


class TestAIModelCreateValidation:
    """Tests for AIModelCreate schema validation.

    Validates: Requirement 14.7
    """

    def test_valid_payload(self):
        """Accepts valid payload."""
        payload = AIModelCreate(
            model_name="scanner",
            model_version="1.0",
            model_type="condition",
        )
        assert payload.model_name == "scanner"

    def test_model_name_too_long(self):
        """Rejects model_name exceeding 100 characters."""
        with pytest.raises(Exception):
            AIModelCreate(
                model_name="x" * 101,
                model_version="1.0",
                model_type="condition",
            )

    def test_model_version_too_long(self):
        """Rejects model_version exceeding 50 characters."""
        with pytest.raises(Exception):
            AIModelCreate(
                model_name="scanner",
                model_version="x" * 51,
                model_type="condition",
            )

    def test_model_type_too_long(self):
        """Rejects model_type exceeding 50 characters."""
        with pytest.raises(Exception):
            AIModelCreate(
                model_name="scanner",
                model_version="1.0",
                model_type="x" * 51,
            )

    def test_model_name_empty(self):
        """Rejects empty model_name."""
        with pytest.raises(Exception):
            AIModelCreate(
                model_name="",
                model_version="1.0",
                model_type="condition",
            )

    def test_model_version_empty(self):
        """Rejects empty model_version."""
        with pytest.raises(Exception):
            AIModelCreate(
                model_name="scanner",
                model_version="",
                model_type="condition",
            )

    def test_model_type_empty(self):
        """Rejects empty model_type."""
        with pytest.raises(Exception):
            AIModelCreate(
                model_name="scanner",
                model_version="1.0",
                model_type="",
            )
