"""
Notification service for damage notifications, replacement requests, and escalations.

Handles the complete damage/replacement workflow:
- Damage notifications: create, resolve, get, list (scoped)
- Replacement requests: create, approve, reject, get, list (scoped)
- Escalations: create, resolve, get, list (scoped)

All status transitions enforce valid source → target status (else 409 ConflictError).
All FK references are validated (non-existent → 404 NotFoundError).

Validates: Requirements 18.1–18.7, 19.1–19.11
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.rbac import ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER, Scope
from app.models.database import (
    BookCopy,
    DamageNotification,
    Escalation,
    ReplacementRequest,
    School,
    User,
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_book_copy_exists(db: Session, book_copy_id: int) -> BookCopy:
    """Check that the referenced book_copy_id exists. Raise 404 if not.

    Validates: Requirement 18.5
    """
    book_copy = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if book_copy is None:
        raise NotFoundError(detail=f"Book copy with id {book_copy_id} not found")
    return book_copy


def _validate_user_exists(db: Session, user_id: int) -> User:
    """Check that the referenced user_id exists. Raise 404 if not."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise NotFoundError(detail=f"User with id {user_id} not found")
    return user


def _validate_damage_notification_exists(
    db: Session, notification_id: int
) -> DamageNotification:
    """Check that the referenced damage_notification_id exists. Raise 404 if not.

    Validates: Requirement 19.9
    """
    notification = (
        db.query(DamageNotification)
        .filter(DamageNotification.id == notification_id)
        .first()
    )
    if notification is None:
        raise NotFoundError(
            detail=f"Damage notification with id {notification_id} not found"
        )
    return notification


def _validate_replacement_request_exists(
    db: Session, request_id: int
) -> ReplacementRequest:
    """Check that the referenced replacement_request_id exists. Raise 404 if not.

    Validates: Requirements 19.10, 19.11
    """
    request = (
        db.query(ReplacementRequest)
        .filter(ReplacementRequest.id == request_id)
        .first()
    )
    if request is None:
        raise NotFoundError(
            detail=f"Replacement request with id {request_id} not found"
        )
    return request


def _apply_scope_filter_damage_notifications(
    query, scope: Scope, db: Session
):
    """Apply scope-based filtering to damage notifications query.

    - DeptAdmin: sees all notifications for book copies in schools within their department
    - SchoolAdmin/Teacher: sees only notifications for book copies in their school

    Validates: Requirement 18.2
    """
    if scope.role == ROLE_DEPT_ADMIN and scope.department_id is not None:
        # Get all school IDs in the department
        school_ids = (
            db.query(School.id)
            .filter(School.department_id == scope.department_id)
            .subquery()
        )
        # Get book copy IDs in those schools
        book_copy_ids = (
            db.query(BookCopy.id)
            .filter(BookCopy.school_id.in_(school_ids))
            .subquery()
        )
        query = query.filter(DamageNotification.book_copy_id.in_(book_copy_ids))
    elif scope.role in (ROLE_SCHOOL_ADMIN, ROLE_TEACHER) and scope.school_id is not None:
        # Get book copy IDs in the user's school
        book_copy_ids = (
            db.query(BookCopy.id)
            .filter(BookCopy.school_id == scope.school_id)
            .subquery()
        )
        query = query.filter(DamageNotification.book_copy_id.in_(book_copy_ids))
    else:
        # Other roles: return empty
        query = query.filter(DamageNotification.id == None)  # noqa: E711

    return query


def _apply_scope_filter_replacement_requests(
    query, scope: Scope, db: Session
):
    """Apply scope-based filtering to replacement requests query.

    Filters through damage_notification → book_copy → school → department chain.

    Validates: Requirement 19.2
    """
    if scope.role == ROLE_DEPT_ADMIN and scope.department_id is not None:
        school_ids = (
            db.query(School.id)
            .filter(School.department_id == scope.department_id)
            .subquery()
        )
        book_copy_ids = (
            db.query(BookCopy.id)
            .filter(BookCopy.school_id.in_(school_ids))
            .subquery()
        )
        notification_ids = (
            db.query(DamageNotification.id)
            .filter(DamageNotification.book_copy_id.in_(book_copy_ids))
            .subquery()
        )
        query = query.filter(
            ReplacementRequest.damage_notification_id.in_(notification_ids)
        )
    elif scope.role in (ROLE_SCHOOL_ADMIN, ROLE_TEACHER) and scope.school_id is not None:
        book_copy_ids = (
            db.query(BookCopy.id)
            .filter(BookCopy.school_id == scope.school_id)
            .subquery()
        )
        notification_ids = (
            db.query(DamageNotification.id)
            .filter(DamageNotification.book_copy_id.in_(book_copy_ids))
            .subquery()
        )
        query = query.filter(
            ReplacementRequest.damage_notification_id.in_(notification_ids)
        )
    else:
        query = query.filter(ReplacementRequest.id == None)  # noqa: E711

    return query


def _apply_scope_filter_escalations(query, scope: Scope, db: Session):
    """Apply scope-based filtering to escalations query.

    Filters through replacement_request → damage_notification → book_copy → school chain.

    Validates: Requirement 19.6
    """
    if scope.role == ROLE_DEPT_ADMIN and scope.department_id is not None:
        school_ids = (
            db.query(School.id)
            .filter(School.department_id == scope.department_id)
            .subquery()
        )
        book_copy_ids = (
            db.query(BookCopy.id)
            .filter(BookCopy.school_id.in_(school_ids))
            .subquery()
        )
        notification_ids = (
            db.query(DamageNotification.id)
            .filter(DamageNotification.book_copy_id.in_(book_copy_ids))
            .subquery()
        )
        request_ids = (
            db.query(ReplacementRequest.id)
            .filter(ReplacementRequest.damage_notification_id.in_(notification_ids))
            .subquery()
        )
        query = query.filter(Escalation.replacement_request_id.in_(request_ids))
    elif scope.role in (ROLE_SCHOOL_ADMIN, ROLE_TEACHER) and scope.school_id is not None:
        book_copy_ids = (
            db.query(BookCopy.id)
            .filter(BookCopy.school_id == scope.school_id)
            .subquery()
        )
        notification_ids = (
            db.query(DamageNotification.id)
            .filter(DamageNotification.book_copy_id.in_(book_copy_ids))
            .subquery()
        )
        request_ids = (
            db.query(ReplacementRequest.id)
            .filter(ReplacementRequest.damage_notification_id.in_(notification_ids))
            .subquery()
        )
        query = query.filter(Escalation.replacement_request_id.in_(request_ids))
    else:
        query = query.filter(Escalation.id == None)  # noqa: E711

    return query


# ---------------------------------------------------------------------------
# Damage Notifications
# ---------------------------------------------------------------------------


def create_damage_notification(
    db: Session,
    book_copy_id: int,
    reported_by: int,
    description: str,
) -> DamageNotification:
    """Create a new damage notification with status "open".

    Validates: Requirement 18.1

    Args:
        db: Database session.
        book_copy_id: ID of the damaged book copy.
        reported_by: ID of the user reporting the damage.
        description: Description of the damage (1-1000 chars).

    Returns:
        The newly created DamageNotification instance.

    Raises:
        NotFoundError: If book_copy_id does not exist (404).
    """
    _validate_book_copy_exists(db, book_copy_id)
    _validate_user_exists(db, reported_by)

    notification = DamageNotification(
        book_copy_id=book_copy_id,
        reported_by=reported_by,
        description=description,
        status="open",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def resolve_damage_notification(
    db: Session,
    notification_id: int,
    resolution_note: str,
) -> DamageNotification:
    """Resolve a damage notification by updating status to "resolved".

    Only notifications with status "open" can be resolved.

    Validates: Requirements 18.4, 18.7

    Args:
        db: Database session.
        notification_id: ID of the notification to resolve.
        resolution_note: Note describing the resolution (1-1000 chars).

    Returns:
        The updated DamageNotification instance.

    Raises:
        NotFoundError: If no notification with the given ID exists (404).
        ConflictError: If the notification status is not "open" (409).
    """
    notification = get_damage_notification(db, notification_id)

    if notification.status != "open":
        raise ConflictError(
            detail="This damage notification is already resolved"
        )

    notification.status = "resolved"
    notification.resolution_note = resolution_note
    notification.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(notification)
    return notification


def get_damage_notification(
    db: Session, notification_id: int
) -> DamageNotification:
    """Get a damage notification by its ID.

    Validates: Requirements 18.3, 18.6

    Args:
        db: Database session.
        notification_id: Primary key of the notification.

    Returns:
        The DamageNotification instance.

    Raises:
        NotFoundError: If no notification with the given ID exists (404).
    """
    notification = (
        db.query(DamageNotification)
        .filter(DamageNotification.id == notification_id)
        .first()
    )
    if notification is None:
        raise NotFoundError(
            detail=f"Damage notification with id {notification_id} not found"
        )
    return notification


def list_damage_notifications(
    db: Session,
    params: PaginationParams,
    scope: Scope,
) -> PaginatedResponse:
    """Get a paginated, scope-filtered list of damage notifications.

    Validates: Requirement 18.2

    Args:
        db: Database session.
        params: Pagination parameters.
        scope: The authenticated user's organizational scope.

    Returns:
        PaginatedResponse with damage notification records.
    """
    query = db.query(DamageNotification)
    query = _apply_scope_filter_damage_notifications(query, scope, db)
    query = query.order_by(DamageNotification.created_at.desc())
    return paginate(query, params)


# ---------------------------------------------------------------------------
# Replacement Requests
# ---------------------------------------------------------------------------


def create_replacement_request(
    db: Session,
    damage_notification_id: int,
) -> ReplacementRequest:
    """Create a new replacement request with status "pending".

    Validates: Requirement 19.1

    Args:
        db: Database session.
        damage_notification_id: ID of the damage notification triggering the request.

    Returns:
        The newly created ReplacementRequest instance.

    Raises:
        NotFoundError: If damage_notification_id does not exist (404).
    """
    _validate_damage_notification_exists(db, damage_notification_id)

    request = ReplacementRequest(
        damage_notification_id=damage_notification_id,
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def approve_replacement_request(
    db: Session,
    request_id: int,
) -> ReplacementRequest:
    """Approve a replacement request by updating status to "approved".

    Only requests with status "pending" can be approved.

    Validates: Requirements 19.3

    Args:
        db: Database session.
        request_id: ID of the replacement request to approve.

    Returns:
        The updated ReplacementRequest instance.

    Raises:
        NotFoundError: If no request with the given ID exists (404).
        ConflictError: If the request status is not "pending" (409).
    """
    request = get_replacement_request(db, request_id)

    if request.status != "pending":
        raise ConflictError(
            detail=f"Replacement request has already been {request.status}. Only pending requests can be approved."
        )

    request.status = "approved"
    db.commit()
    db.refresh(request)
    return request


def reject_replacement_request(
    db: Session,
    request_id: int,
    reason: str,
) -> ReplacementRequest:
    """Reject a replacement request by updating status to "rejected".

    Only requests with status "pending" can be rejected.

    Validates: Requirements 19.4

    Args:
        db: Database session.
        request_id: ID of the replacement request to reject.
        reason: Reason for rejection (1-1000 chars).

    Returns:
        The updated ReplacementRequest instance.

    Raises:
        NotFoundError: If no request with the given ID exists (404).
        ConflictError: If the request status is not "pending" (409).
    """
    request = get_replacement_request(db, request_id)

    if request.status != "pending":
        raise ConflictError(
            detail=f"Replacement request has already been {request.status}. Only pending requests can be rejected."
        )

    request.status = "rejected"
    request.reason = reason
    db.commit()
    db.refresh(request)
    return request


def get_replacement_request(
    db: Session, request_id: int
) -> ReplacementRequest:
    """Get a replacement request by its ID.

    Validates: Requirement 19.11

    Args:
        db: Database session.
        request_id: Primary key of the replacement request.

    Returns:
        The ReplacementRequest instance.

    Raises:
        NotFoundError: If no request with the given ID exists (404).
    """
    request = (
        db.query(ReplacementRequest)
        .filter(ReplacementRequest.id == request_id)
        .first()
    )
    if request is None:
        raise NotFoundError(
            detail=f"Replacement request with id {request_id} not found"
        )
    return request


def list_replacement_requests(
    db: Session,
    params: PaginationParams,
    scope: Scope,
) -> PaginatedResponse:
    """Get a paginated, scope-filtered list of replacement requests.

    Validates: Requirement 19.2

    Args:
        db: Database session.
        params: Pagination parameters.
        scope: The authenticated user's organizational scope.

    Returns:
        PaginatedResponse with replacement request records.
    """
    query = db.query(ReplacementRequest)
    query = _apply_scope_filter_replacement_requests(query, scope, db)
    query = query.order_by(ReplacementRequest.created_at.desc())
    return paginate(query, params)


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------


def create_escalation(
    db: Session,
    replacement_request_id: int,
    reason: str,
) -> Escalation:
    """Create a new escalation with status "open".

    Validates: Requirement 19.5

    Args:
        db: Database session.
        replacement_request_id: ID of the replacement request being escalated.
        reason: Reason for escalation (1-1000 chars).

    Returns:
        The newly created Escalation instance.

    Raises:
        NotFoundError: If replacement_request_id does not exist (404).
    """
    _validate_replacement_request_exists(db, replacement_request_id)

    escalation = Escalation(
        replacement_request_id=replacement_request_id,
        reason=reason,
        status="open",
    )
    db.add(escalation)
    db.commit()
    db.refresh(escalation)
    return escalation


def resolve_escalation(
    db: Session,
    escalation_id: int,
    resolution_note: str,
) -> Escalation:
    """Resolve an escalation by updating status to "resolved".

    Only escalations with status "open" can be resolved.

    Validates: Requirement 19.7

    Args:
        db: Database session.
        escalation_id: ID of the escalation to resolve.
        resolution_note: Note describing the resolution (1-2000 chars).

    Returns:
        The updated Escalation instance.

    Raises:
        NotFoundError: If no escalation with the given ID exists (404).
        ConflictError: If the escalation status is not "open" (409).
    """
    escalation = get_escalation(db, escalation_id)

    if escalation.status != "open":
        raise ConflictError(
            detail="This escalation is already resolved"
        )

    escalation.status = "resolved"
    escalation.resolution_note = resolution_note
    escalation.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(escalation)
    return escalation


def get_escalation(db: Session, escalation_id: int) -> Escalation:
    """Get an escalation by its ID.

    Args:
        db: Database session.
        escalation_id: Primary key of the escalation.

    Returns:
        The Escalation instance.

    Raises:
        NotFoundError: If no escalation with the given ID exists (404).
    """
    escalation = (
        db.query(Escalation)
        .filter(Escalation.id == escalation_id)
        .first()
    )
    if escalation is None:
        raise NotFoundError(
            detail=f"Escalation with id {escalation_id} not found"
        )
    return escalation


def list_escalations(
    db: Session,
    params: PaginationParams,
    scope: Scope,
) -> PaginatedResponse:
    """Get a paginated, scope-filtered list of escalations.

    Validates: Requirement 19.6

    Args:
        db: Database session.
        params: Pagination parameters.
        scope: The authenticated user's organizational scope.

    Returns:
        PaginatedResponse with escalation records.
    """
    query = db.query(Escalation)
    query = _apply_scope_filter_escalations(query, scope, db)
    query = query.order_by(Escalation.created_at.desc())
    return paginate(query, params)
