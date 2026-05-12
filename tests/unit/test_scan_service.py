"""Unit tests for app.services.scan_service module.

Tests the scan service functions with mocked DB sessions,
validating requirements 15.1–15.8.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import APIError, NotFoundError, ValidationError
from app.core.pagination import PaginationParams
from app.models.database import AIModelVersion, BookConditionScan, BookCopy
from app.services import scan_service


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


def _make_ai_model(**overrides):
    """Create a fake AIModelVersion instance."""
    defaults = {
        "id": 1,
        "model_name": "condition-scanner",
        "model_version": "1.0.0",
        "model_type": "book_condition",
        "is_active": True,
        "created_at": datetime(2024, 1, 1),
    }
    defaults.update(overrides)
    obj = MagicMock(spec=AIModelVersion)
    for key, value in defaults.items():
        setattr(obj, key, value)
    return obj


def _make_scan(**overrides):
    """Create a fake BookConditionScan instance."""
    defaults = {
        "id": 1,
        "book_copy_id": 1,
        "ai_model_id": 1,
        "condition": "good",
        "confidence_score": 0.85,
        "verified_condition": None,
        "scan_image_path": "uploads/scans/test.jpg",
        "scanned_at": datetime(2024, 1, 15, 10, 30, 0),
    }
    defaults.update(overrides)
    obj = MagicMock(spec=BookConditionScan)
    for key, value in defaults.items():
        setattr(obj, key, value)
    return obj


# ---------------------------------------------------------------------------
# get_active_model Tests
# ---------------------------------------------------------------------------


class TestGetActiveModel:
    """Tests for scan_service.get_active_model."""

    def test_returns_active_model(self):
        """Returns the active AI model when one exists.

        Validates: Requirement 15.1 (prerequisite)
        """
        db = MagicMock()
        active_model = _make_ai_model(is_active=True)
        db.query.return_value.filter.return_value.first.return_value = active_model

        result = scan_service.get_active_model(db)

        assert result == active_model

    def test_raises_validation_error_when_no_active_model(self):
        """Raises ValidationError (422) when no active model exists.

        Validates: Requirement 15.6
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValidationError) as exc_info:
            scan_service.get_active_model(db)

        assert "no active" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# create_scan Tests
# ---------------------------------------------------------------------------


class TestCreateScan:
    """Tests for scan_service.create_scan."""

    def test_create_scan_success(self):
        """Creates a scan record with AI model result.

        Validates: Requirement 15.1
        """
        db = MagicMock()
        book_copy = _make_book_copy(id=1)
        active_model = _make_ai_model(id=1)

        # First query: book copy lookup
        # Second query: active model lookup
        db.query.return_value.filter.return_value.first.side_effect = [
            book_copy,
            active_model,
        ]

        with patch.object(scan_service, "_invoke_ai_model") as mock_invoke:
            mock_invoke.return_value = {
                "condition": "good",
                "confidence_score": 0.92,
            }

            result = scan_service.create_scan(db, 1, "uploads/scans/test.jpg")

        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()

    def test_create_scan_book_copy_not_found(self):
        """Raises NotFoundError (404) when book_copy_id doesn't exist.

        Validates: Requirement 15.5
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            scan_service.create_scan(db, 999, "uploads/scans/test.jpg")

        assert "999" in exc_info.value.detail

    def test_create_scan_no_active_model(self):
        """Raises ValidationError (422) when no active AI model exists.

        Validates: Requirement 15.6
        """
        db = MagicMock()
        book_copy = _make_book_copy(id=1)

        # Book copy found, but no active model
        db.query.return_value.filter.return_value.first.side_effect = [
            book_copy,
            None,
        ]

        with pytest.raises(ValidationError) as exc_info:
            scan_service.create_scan(db, 1, "uploads/scans/test.jpg")

        assert "no active" in exc_info.value.detail.lower()

    def test_create_scan_ai_model_failure(self):
        """Raises APIError (502) when AI model invocation fails.

        Validates: Requirement 15.8
        """
        db = MagicMock()
        book_copy = _make_book_copy(id=1)
        active_model = _make_ai_model(id=1)

        db.query.return_value.filter.return_value.first.side_effect = [
            book_copy,
            active_model,
        ]

        with patch.object(scan_service, "_invoke_ai_model") as mock_invoke:
            mock_invoke.side_effect = scan_service.AIModelInvocationError(
                "Model unavailable"
            )

            with pytest.raises(APIError) as exc_info:
                scan_service.create_scan(db, 1, "uploads/scans/test.jpg")

            assert exc_info.value.status_code == 502
            assert "unavailable" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# get_scan_by_id Tests
# ---------------------------------------------------------------------------


class TestGetScanById:
    """Tests for scan_service.get_scan_by_id."""

    def test_returns_scan_when_found(self):
        """Returns the scan record when it exists.

        Validates: Requirement 15.2
        """
        db = MagicMock()
        scan = _make_scan(id=1)
        db.query.return_value.filter.return_value.first.return_value = scan

        result = scan_service.get_scan_by_id(db, 1)

        assert result == scan

    def test_raises_not_found_when_missing(self):
        """Raises NotFoundError (404) when scan doesn't exist.

        Validates: Requirement 15.7
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            scan_service.get_scan_by_id(db, 999)

        assert "999" in exc_info.value.detail


# ---------------------------------------------------------------------------
# get_scans_by_book_copy Tests
# ---------------------------------------------------------------------------


class TestGetScansByBookCopy:
    """Tests for scan_service.get_scans_by_book_copy."""

    def test_returns_paginated_scans(self):
        """Returns paginated scans for a book copy.

        Validates: Requirement 15.3
        """
        db = MagicMock()
        book_copy = _make_book_copy(id=1)
        params = PaginationParams(page=1, page_size=20)

        # First call: book copy lookup
        mock_filter = MagicMock()
        mock_filter.first.return_value = book_copy

        # Second call: scans query
        mock_scans_query = MagicMock()
        mock_scans_query.count.return_value = 2
        mock_scans_query.offset.return_value.limit.return_value.all.return_value = [
            _make_scan(id=1),
            _make_scan(id=2),
        ]

        # Chain: db.query().filter().first() for book copy
        # Chain: db.query().filter().order_by() for scans
        db.query.return_value.filter.return_value.first.return_value = book_copy
        db.query.return_value.filter.return_value.order_by.return_value = mock_scans_query

        result = scan_service.get_scans_by_book_copy(db, 1, params)

        assert result.total == 2
        assert len(result.items) == 2

    def test_raises_not_found_when_book_copy_missing(self):
        """Raises NotFoundError (404) when book_copy_id doesn't exist.

        Validates: Requirement 15.5
        """
        db = MagicMock()
        params = PaginationParams(page=1, page_size=20)
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            scan_service.get_scans_by_book_copy(db, 999, params)

        assert "999" in exc_info.value.detail


# ---------------------------------------------------------------------------
# verify_scan Tests
# ---------------------------------------------------------------------------


class TestVerifyScan:
    """Tests for scan_service.verify_scan."""

    def test_verify_scan_success(self):
        """Updates scan with verified condition.

        Validates: Requirement 15.4
        """
        db = MagicMock()
        scan = _make_scan(id=1, verified_condition=None)
        db.query.return_value.filter.return_value.first.return_value = scan

        result = scan_service.verify_scan(db, 1, "fair")

        assert scan.verified_condition == "fair"
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(scan)

    def test_verify_scan_not_found(self):
        """Raises NotFoundError (404) when scan doesn't exist.

        Validates: Requirement 15.7
        """
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            scan_service.verify_scan(db, 999, "good")

        assert "999" in exc_info.value.detail


# ---------------------------------------------------------------------------
# _invoke_ai_model Tests
# ---------------------------------------------------------------------------


class TestInvokeAIModel:
    """Tests for the mock AI model invocation."""

    def test_returns_valid_condition_and_score(self):
        """Mock AI model returns a valid condition and confidence score."""
        model = _make_ai_model()
        result = scan_service._invoke_ai_model(model, "test/path.jpg")

        assert result["condition"] in scan_service.VALID_CONDITIONS
        assert 0.5 <= result["confidence_score"] <= 1.0

    def test_returns_dict_with_expected_keys(self):
        """Mock AI model returns dict with 'condition' and 'confidence_score' keys."""
        model = _make_ai_model()
        result = scan_service._invoke_ai_model(model, "test/path.jpg")

        assert "condition" in result
        assert "confidence_score" in result
