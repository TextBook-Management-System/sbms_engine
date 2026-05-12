# Feature: sbms-api-endpoints, Property 4: Status Transition Enforcement
"""
Property-based tests for status transition enforcement.

Tests validate that:
For any entity with a status-based lifecycle (book request, allocation,
acknowledgement, damage notification, replacement request, escalation),
if the entity is NOT in the required source status for a transition operation,
the API SHALL return HTTP 409 with error_type "conflict".

Specifically:
- Only "pending" book requests can be approved/rejected
- Only "active" allocations can be returned
- Only "pending" acknowledgements can be accepted/rejected
- Only "open" damage notifications can be resolved
- Only "pending" replacement requests can be approved/rejected
- Only "open" escalations can be resolved

**Validates: Requirements 11.8, 16.5, 16.8, 17.7, 18.7, 19.3, 19.4, 19.7**
"""

import pytest
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.exceptions import ConflictError
from app.models.database import (
    BookRequest,
    BookAllocation,
    ParentAcknowledgement,
    DamageNotification,
    ReplacementRequest,
    Escalation,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Book request statuses that are NOT "pending" (i.e., already processed)
book_request_non_pending_statuses = st.sampled_from(["approved", "rejected"])

# Allocation statuses that are NOT "active" (i.e., already returned)
allocation_non_active_statuses = st.sampled_from(["returned"])

# Acknowledgement statuses that are NOT "pending" (i.e., already processed)
acknowledgement_non_pending_statuses = st.sampled_from(["accepted", "rejected"])

# Damage notification statuses that are NOT "open" (i.e., already resolved)
damage_notification_non_open_statuses = st.sampled_from(["resolved"])

# Replacement request statuses that are NOT "pending" (i.e., already processed)
replacement_request_non_pending_statuses = st.sampled_from(["approved", "rejected"])

# Escalation statuses that are NOT "open" (i.e., already resolved)
escalation_non_open_statuses = st.sampled_from(["resolved"])

# Random entity IDs
entity_ids = st.integers(min_value=1, max_value=10000)

# Rejection/resolution reasons
reasons = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db_with_entity(model_class, entity_id: int, status: str, **extra_attrs):
    """Create a mock DB session that returns an entity with the given status."""
    mock_db = MagicMock()
    mock_entity = MagicMock(spec=model_class)
    mock_entity.id = entity_id
    mock_entity.status = status

    # Set any extra attributes
    for key, value in extra_attrs.items():
        setattr(mock_entity, key, value)

    # Setup query chain: db.query(Model).filter(...).first() -> mock_entity
    mock_query = MagicMock()
    mock_filter = MagicMock()
    mock_filter.first.return_value = mock_entity
    mock_query.filter.return_value = mock_filter
    mock_db.query.return_value = mock_query

    return mock_db, mock_entity


# ---------------------------------------------------------------------------
# Property Tests: Book Requests
# ---------------------------------------------------------------------------


class TestBookRequestStatusTransitions:
    """
    Book requests: only "pending" can be approved/rejected.
    Approved/rejected requests → 409.

    **Validates: Requirements 11.8**
    """

    @given(
        request_id=entity_ids,
        invalid_status=book_request_non_pending_statuses,
    )
    @settings(max_examples=100, deadline=None)
    def test_approve_non_pending_book_request_raises_conflict(
        self, request_id: int, invalid_status: str
    ):
        """
        Approving a book request that is not in "pending" status SHALL raise
        ConflictError (409).

        **Validates: Requirements 11.8**
        """
        from app.api.v1.endpoints.book_requests import approve_book_request

        mock_db, mock_entity = _make_mock_db_with_entity(
            BookRequest, request_id, invalid_status
        )

        with pytest.raises(ConflictError) as exc_info:
            approve_book_request(
                request_id=request_id,
                current_user=MagicMock(),
                db=mock_db,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"

    @given(
        request_id=entity_ids,
        invalid_status=book_request_non_pending_statuses,
        reason=reasons,
    )
    @settings(max_examples=100, deadline=None)
    def test_reject_non_pending_book_request_raises_conflict(
        self, request_id: int, invalid_status: str, reason: str
    ):
        """
        Rejecting a book request that is not in "pending" status SHALL raise
        ConflictError (409).

        **Validates: Requirements 11.8**
        """
        from app.api.v1.endpoints.book_requests import reject_book_request

        mock_db, mock_entity = _make_mock_db_with_entity(
            BookRequest, request_id, invalid_status
        )

        # Create a mock payload with a reason
        mock_payload = MagicMock()
        mock_payload.reason = reason

        with pytest.raises(ConflictError) as exc_info:
            reject_book_request(
                request_id=request_id,
                payload=mock_payload,
                current_user=MagicMock(),
                db=mock_db,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"


# ---------------------------------------------------------------------------
# Property Tests: Allocations
# ---------------------------------------------------------------------------


class TestAllocationStatusTransitions:
    """
    Allocations: only "active" can be returned.
    Already-returned allocations → 409.

    **Validates: Requirements 16.5, 16.8**
    """

    @given(
        allocation_id=entity_ids,
        invalid_status=allocation_non_active_statuses,
    )
    @settings(max_examples=100, deadline=None)
    def test_return_non_active_allocation_raises_conflict(
        self, allocation_id: int, invalid_status: str
    ):
        """
        Returning an allocation that is not in "active" status SHALL raise
        ConflictError (409).

        **Validates: Requirements 16.5, 16.8**
        """
        from app.services.allocation_service import return_allocation

        mock_db = MagicMock()
        mock_allocation = MagicMock(spec=BookAllocation)
        mock_allocation.id = allocation_id
        mock_allocation.status = invalid_status

        # Setup query chain for get_by_id
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = mock_allocation
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        with pytest.raises(ConflictError) as exc_info:
            return_allocation(mock_db, allocation_id)

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"


# ---------------------------------------------------------------------------
# Property Tests: Acknowledgements
# ---------------------------------------------------------------------------


class TestAcknowledgementStatusTransitions:
    """
    Acknowledgements: only "pending" can be accepted/rejected.
    Already-processed → 409.

    **Validates: Requirements 17.7**
    """

    @given(
        acknowledgement_id=entity_ids,
        invalid_status=acknowledgement_non_pending_statuses,
    )
    @settings(max_examples=100, deadline=None)
    def test_accept_non_pending_acknowledgement_raises_conflict(
        self, acknowledgement_id: int, invalid_status: str
    ):
        """
        Accepting an acknowledgement that is not in "pending" status SHALL raise
        ConflictError (409).

        **Validates: Requirements 17.7**
        """
        from app.api.v1.endpoints.acknowledgements import accept_acknowledgement

        mock_db, mock_entity = _make_mock_db_with_entity(
            ParentAcknowledgement, acknowledgement_id, invalid_status,
            parent_id=42,
        )

        # Create a mock current_user whose id matches the parent_id
        mock_user = MagicMock()
        mock_user.id = 42

        with pytest.raises(ConflictError) as exc_info:
            accept_acknowledgement(
                acknowledgement_id=acknowledgement_id,
                current_user=mock_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"

    @given(
        acknowledgement_id=entity_ids,
        invalid_status=acknowledgement_non_pending_statuses,
        reason=reasons,
    )
    @settings(max_examples=100, deadline=None)
    def test_reject_non_pending_acknowledgement_raises_conflict(
        self, acknowledgement_id: int, invalid_status: str, reason: str
    ):
        """
        Rejecting an acknowledgement that is not in "pending" status SHALL raise
        ConflictError (409).

        **Validates: Requirements 17.7**
        """
        from app.api.v1.endpoints.acknowledgements import reject_acknowledgement

        mock_db, mock_entity = _make_mock_db_with_entity(
            ParentAcknowledgement, acknowledgement_id, invalid_status,
            parent_id=42,
        )

        # Create a mock current_user whose id matches the parent_id
        mock_user = MagicMock()
        mock_user.id = 42

        # Create a mock payload with a reason
        mock_payload = MagicMock()
        mock_payload.reason = reason

        with pytest.raises(ConflictError) as exc_info:
            reject_acknowledgement(
                acknowledgement_id=acknowledgement_id,
                payload=mock_payload,
                current_user=mock_user,
                db=mock_db,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"


# ---------------------------------------------------------------------------
# Property Tests: Damage Notifications
# ---------------------------------------------------------------------------


class TestDamageNotificationStatusTransitions:
    """
    Damage notifications: only "open" can be resolved.
    Already-resolved → 409.

    **Validates: Requirements 18.7**
    """

    @given(
        notification_id=entity_ids,
        invalid_status=damage_notification_non_open_statuses,
        resolution_note=reasons,
    )
    @settings(max_examples=100, deadline=None)
    def test_resolve_non_open_damage_notification_raises_conflict(
        self, notification_id: int, invalid_status: str, resolution_note: str
    ):
        """
        Resolving a damage notification that is not in "open" status SHALL raise
        ConflictError (409).

        **Validates: Requirements 18.7**
        """
        from app.services.notification_service import resolve_damage_notification

        mock_db, mock_entity = _make_mock_db_with_entity(
            DamageNotification, notification_id, invalid_status
        )

        with pytest.raises(ConflictError) as exc_info:
            resolve_damage_notification(mock_db, notification_id, resolution_note)

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"


# ---------------------------------------------------------------------------
# Property Tests: Replacement Requests
# ---------------------------------------------------------------------------


class TestReplacementRequestStatusTransitions:
    """
    Replacement requests: only "pending" can be approved/rejected.
    Already-processed → 409.

    **Validates: Requirements 19.3, 19.4**
    """

    @given(
        request_id=entity_ids,
        invalid_status=replacement_request_non_pending_statuses,
    )
    @settings(max_examples=100, deadline=None)
    def test_approve_non_pending_replacement_request_raises_conflict(
        self, request_id: int, invalid_status: str
    ):
        """
        Approving a replacement request that is not in "pending" status SHALL raise
        ConflictError (409).

        **Validates: Requirements 19.3**
        """
        from app.services.notification_service import approve_replacement_request

        mock_db, mock_entity = _make_mock_db_with_entity(
            ReplacementRequest, request_id, invalid_status
        )

        with pytest.raises(ConflictError) as exc_info:
            approve_replacement_request(mock_db, request_id)

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"

    @given(
        request_id=entity_ids,
        invalid_status=replacement_request_non_pending_statuses,
        reason=reasons,
    )
    @settings(max_examples=100, deadline=None)
    def test_reject_non_pending_replacement_request_raises_conflict(
        self, request_id: int, invalid_status: str, reason: str
    ):
        """
        Rejecting a replacement request that is not in "pending" status SHALL raise
        ConflictError (409).

        **Validates: Requirements 19.4**
        """
        from app.services.notification_service import reject_replacement_request

        mock_db, mock_entity = _make_mock_db_with_entity(
            ReplacementRequest, request_id, invalid_status
        )

        with pytest.raises(ConflictError) as exc_info:
            reject_replacement_request(mock_db, request_id, reason)

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"


# ---------------------------------------------------------------------------
# Property Tests: Escalations
# ---------------------------------------------------------------------------


class TestEscalationStatusTransitions:
    """
    Escalations: only "open" can be resolved.
    Already-resolved → 409.

    **Validates: Requirements 19.7**
    """

    @given(
        escalation_id=entity_ids,
        invalid_status=escalation_non_open_statuses,
        resolution_note=reasons,
    )
    @settings(max_examples=100, deadline=None)
    def test_resolve_non_open_escalation_raises_conflict(
        self, escalation_id: int, invalid_status: str, resolution_note: str
    ):
        """
        Resolving an escalation that is not in "open" status SHALL raise
        ConflictError (409).

        **Validates: Requirements 19.7**
        """
        from app.services.notification_service import resolve_escalation

        mock_db, mock_entity = _make_mock_db_with_entity(
            Escalation, escalation_id, invalid_status
        )

        with pytest.raises(ConflictError) as exc_info:
            resolve_escalation(mock_db, escalation_id, resolution_note)

        assert exc_info.value.status_code == 409
        assert exc_info.value.error_type == "conflict"
