"""Unit tests for app.api.v1.endpoints.acknowledgements module.

Tests the parent acknowledgements endpoint handlers with mocked DB sessions,
validating requirements 17.1–17.8.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams
from app.models.database import BookAllocation, ParentAcknowledgement, ParentLearner, User
from app.api.v1.endpoints.acknowledgements import (
    _get_parent_learner_ids,
    create_acknowledgement,
    list_acknowledgements,
    accept_acknowledgement,
    reject_acknowledgement,
)
from app.schemas.acknowledgements import (
    AcknowledgementCreate,
    AcknowledgementReject,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(user_id=1):
    """Create a fake User instance."""
    user = MagicMock(spec=User)
    user.id = user_id
    return user


def _make_allocation(allocation_id=1, learner_id=10, status="active"):
    """Create a fake BookAllocation instance."""
    alloc = MagicMock(spec=BookAllocation)
    alloc.id = allocation_id
    alloc.learner_id = learner_id
    alloc.status = status
    return alloc


def _make_acknowledgement(ack_id=1, allocation_id=1, parent_id=1, status="pending", reason=None):
    """Create a fake ParentAcknowledgement instance."""
    ack = MagicMock(spec=ParentAcknowledgement)
    ack.id = ack_id
    ack.allocation_id = allocation_id
    ack.parent_id = parent_id
    ack.status = status
    ack.reason = reason
    ack.created_at = datetime(2024, 1, 1, 12, 0, 0)
    return ack


def _mock_db_for_create(allocation=None, parent_learner_ids=None, existing_ack=None):
    """Set up a mock DB session for the create_acknowledgement flow.

    The create endpoint queries:
    1. BookAllocation by allocation_id
    2. ParentLearner.learner_id by parent_id
    3. ParentAcknowledgement by allocation_id (duplicate check)
    """
    db = MagicMock()

    # We need to handle multiple db.query() calls with different models
    allocation_query = MagicMock()
    allocation_query.filter.return_value.first.return_value = allocation

    parent_learner_query = MagicMock()
    if parent_learner_ids is not None:
        parent_learner_query.filter.return_value.all.return_value = [
            MagicMock(learner_id=lid) for lid in parent_learner_ids
        ]
    else:
        parent_learner_query.filter.return_value.all.return_value = []

    ack_query = MagicMock()
    ack_query.filter.return_value.first.return_value = existing_ack

    # db.query(BookAllocation), db.query(ParentLearner.learner_id), db.query(ParentAcknowledgement)
    db.query.side_effect = [allocation_query, parent_learner_query, ack_query]

    return db


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------


class TestGetParentLearnerIds:
    """Tests for _get_parent_learner_ids helper."""

    def test_returns_learner_ids(self):
        """Returns list of learner IDs linked to parent."""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            MagicMock(learner_id=10),
            MagicMock(learner_id=20),
        ]

        result = _get_parent_learner_ids(1, db)

        assert result == [10, 20]

    def test_returns_empty_when_no_links(self):
        """Returns empty list when parent has no linked learners."""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []

        result = _get_parent_learner_ids(1, db)

        assert result == []


# ---------------------------------------------------------------------------
# Create Acknowledgement Tests
# ---------------------------------------------------------------------------


class TestCreateAcknowledgement:
    """Tests for create_acknowledgement endpoint handler."""

    def test_create_success(self):
        """Creates acknowledgement with status 'pending' when allocation is valid.

        Validates: Requirement 17.1
        """
        allocation = _make_allocation(allocation_id=5, learner_id=10)
        db = _mock_db_for_create(
            allocation=allocation,
            parent_learner_ids=[10, 20],
            existing_ack=None,
        )
        user = _make_user(user_id=1)
        payload = AcknowledgementCreate(allocation_id=5)

        # Mock the add/commit/refresh cycle
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        result = create_acknowledgement(payload, user, db)

        db.add.assert_called_once()
        db.commit.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert added_obj.allocation_id == 5
        assert added_obj.parent_id == 1
        assert added_obj.status == "pending"

    def test_create_allocation_not_found(self):
        """Returns 422 when allocation does not exist.

        Validates: Requirement 17.6
        """
        db = _mock_db_for_create(
            allocation=None,
            parent_learner_ids=[10],
            existing_ack=None,
        )
        user = _make_user(user_id=1)
        payload = AcknowledgementCreate(allocation_id=999)

        with pytest.raises(ValidationError) as exc_info:
            create_acknowledgement(payload, user, db)

        assert "allocation" in exc_info.value.detail.lower()

    def test_create_allocation_not_linked_to_parent(self):
        """Returns 422 when allocation's learner is not linked to the parent.

        Validates: Requirement 17.6
        """
        # Allocation exists but learner_id=99 is not in parent's linked learners [10, 20]
        allocation = _make_allocation(allocation_id=5, learner_id=99)
        db = _mock_db_for_create(
            allocation=allocation,
            parent_learner_ids=[10, 20],
            existing_ack=None,
        )
        user = _make_user(user_id=1)
        payload = AcknowledgementCreate(allocation_id=5)

        with pytest.raises(ValidationError) as exc_info:
            create_acknowledgement(payload, user, db)

        assert "allocation" in exc_info.value.detail.lower()

    def test_create_duplicate_acknowledgement(self):
        """Returns 409 when acknowledgement already exists for allocation.

        Validates: Requirement 17.8
        """
        allocation = _make_allocation(allocation_id=5, learner_id=10)
        existing = _make_acknowledgement(ack_id=1, allocation_id=5)
        db = _mock_db_for_create(
            allocation=allocation,
            parent_learner_ids=[10],
            existing_ack=existing,
        )
        user = _make_user(user_id=1)
        payload = AcknowledgementCreate(allocation_id=5)

        with pytest.raises(ConflictError) as exc_info:
            create_acknowledgement(payload, user, db)

        assert "already exists" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# List Acknowledgements Tests
# ---------------------------------------------------------------------------


class TestListAcknowledgements:
    """Tests for list_acknowledgements endpoint handler."""

    def test_list_own_acknowledgements(self):
        """Returns paginated list of parent's own acknowledgements.

        Validates: Requirement 17.4
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        params = PaginationParams(page=1, page_size=20)

        # Mock the query chain
        mock_query = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value.limit.return_value.all.return_value = [
            _make_acknowledgement()
        ]

        result = list_acknowledgements(parent_id=1, params=params, current_user=user, db=db)

        assert result.total == 1
        assert result.page == 1

    def test_list_other_parent_forbidden(self):
        """Returns 403 when trying to view another parent's acknowledgements.

        Validates: Requirement 17.5
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        params = PaginationParams(page=1, page_size=20)

        with pytest.raises(ForbiddenError):
            list_acknowledgements(parent_id=99, params=params, current_user=user, db=db)


# ---------------------------------------------------------------------------
# Accept Acknowledgement Tests
# ---------------------------------------------------------------------------


class TestAcceptAcknowledgement:
    """Tests for accept_acknowledgement endpoint handler."""

    def test_accept_success(self):
        """Accepts a pending acknowledgement.

        Validates: Requirement 17.2
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        ack = _make_acknowledgement(ack_id=5, parent_id=1, status="pending")
        db.query.return_value.filter.return_value.first.return_value = ack

        result = accept_acknowledgement(5, user, db)

        assert ack.status == "accepted"
        db.commit.assert_called_once()

    def test_accept_not_found(self):
        """Returns 404 when acknowledgement does not exist.

        Validates: Requirement 17.7 (implied 404)
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError):
            accept_acknowledgement(999, user, db)

    def test_accept_wrong_parent(self):
        """Returns 403 when another parent tries to accept.

        Validates: Requirement 17.5
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        ack = _make_acknowledgement(ack_id=5, parent_id=99, status="pending")
        db.query.return_value.filter.return_value.first.return_value = ack

        with pytest.raises(ForbiddenError):
            accept_acknowledgement(5, user, db)

    def test_accept_already_accepted(self):
        """Returns 409 when acknowledgement is already accepted.

        Validates: Requirement 17.7
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        ack = _make_acknowledgement(ack_id=5, parent_id=1, status="accepted")
        db.query.return_value.filter.return_value.first.return_value = ack

        with pytest.raises(ConflictError):
            accept_acknowledgement(5, user, db)

    def test_accept_already_rejected(self):
        """Returns 409 when acknowledgement is already rejected.

        Validates: Requirement 17.7
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        ack = _make_acknowledgement(ack_id=5, parent_id=1, status="rejected")
        db.query.return_value.filter.return_value.first.return_value = ack

        with pytest.raises(ConflictError):
            accept_acknowledgement(5, user, db)


# ---------------------------------------------------------------------------
# Reject Acknowledgement Tests
# ---------------------------------------------------------------------------


class TestRejectAcknowledgement:
    """Tests for reject_acknowledgement endpoint handler."""

    def test_reject_success(self):
        """Rejects a pending acknowledgement with a reason.

        Validates: Requirement 17.3
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        ack = _make_acknowledgement(ack_id=5, parent_id=1, status="pending")
        db.query.return_value.filter.return_value.first.return_value = ack

        payload = AcknowledgementReject(reason="Book is damaged")

        result = reject_acknowledgement(5, payload, user, db)

        assert ack.status == "rejected"
        assert ack.reason == "Book is damaged"
        db.commit.assert_called_once()

    def test_reject_not_found(self):
        """Returns 404 when acknowledgement does not exist."""
        db = MagicMock()
        user = _make_user(user_id=1)
        db.query.return_value.filter.return_value.first.return_value = None

        payload = AcknowledgementReject(reason="Some reason")

        with pytest.raises(NotFoundError):
            reject_acknowledgement(999, payload, user, db)

    def test_reject_wrong_parent(self):
        """Returns 403 when another parent tries to reject.

        Validates: Requirement 17.5
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        ack = _make_acknowledgement(ack_id=5, parent_id=99, status="pending")
        db.query.return_value.filter.return_value.first.return_value = ack

        payload = AcknowledgementReject(reason="Some reason")

        with pytest.raises(ForbiddenError):
            reject_acknowledgement(5, payload, user, db)

    def test_reject_already_processed(self):
        """Returns 409 when acknowledgement is not pending.

        Validates: Requirement 17.7
        """
        db = MagicMock()
        user = _make_user(user_id=1)
        ack = _make_acknowledgement(ack_id=5, parent_id=1, status="accepted")
        db.query.return_value.filter.return_value.first.return_value = ack

        payload = AcknowledgementReject(reason="Some reason")

        with pytest.raises(ConflictError):
            reject_acknowledgement(5, payload, user, db)

    def test_reject_reason_validation(self):
        """Validates reason field constraints (1-500 characters).

        Validates: Requirement 17.3
        """
        # Empty reason should fail Pydantic validation
        with pytest.raises(Exception):
            AcknowledgementReject(reason="")

        # Valid reason should pass
        valid = AcknowledgementReject(reason="Valid reason")
        assert valid.reason == "Valid reason"
