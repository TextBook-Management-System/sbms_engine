"""Damage notifications endpoints for the SBMS API.

Provides endpoints for creating, listing, retrieving, and resolving damage notifications:
- POST /damage-notifications: Create a new damage notification (status "open")
- GET /damage-notifications: List damage notifications scoped by role
- GET /damage-notifications/{id}: Get a damage notification by ID
- PUT /damage-notifications/{id}/resolve: Resolve an open notification

Enforces:
- Status transition: only open → resolved (409 if already resolved)
- FK validation: book_copy_id must exist (404 if not)
- Scope-based filtering on list endpoint

Validates: Requirements 18.1–18.7
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_dependency
from app.core.pagination import PaginatedResponse, PaginationParams
from app.core.rbac import (
    ROLE_DEPT_ADMIN,
    ROLE_SCHOOL_ADMIN,
    ROLE_TEACHER,
    Scope,
    get_user_scope,
    require_role,
)
from app.database.session import get_db
from app.models.database import User
from app.schemas.damage_notifications import (
    DamageNotificationCreate,
    DamageNotificationResolve,
    DamageNotificationResponse,
)
from app.services import notification_service

router = APIRouter(prefix="/damage-notifications", tags=["damage-notifications"])


@router.post(
    "",
    response_model=DamageNotificationResponse,
    status_code=201,
)
def create_damage_notification(
    payload: DamageNotificationCreate,
    current_user: User = Depends(
        require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER)
    ),
    db: Session = Depends(get_db),
) -> DamageNotificationResponse:
    """Create a new damage notification.

    Creates a damage notification with status "open" for the specified book copy.
    The reporting user is set to the current authenticated user.

    Returns 404 if book_copy_id does not exist.

    Validates: Requirement 18.1, 18.5
    """
    notification = notification_service.create_damage_notification(
        db=db,
        book_copy_id=payload.book_copy_id,
        reported_by=current_user.id,
        description=payload.description,
    )
    return notification


@router.get(
    "",
    response_model=PaginatedResponse[DamageNotificationResponse],
)
def list_damage_notifications(
    params: PaginationParams = Depends(),
    scope: Scope = Depends(get_user_scope),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DamageNotificationResponse]:
    """List damage notifications scoped by the user's role.

    - DeptAdmin: sees all notifications for book copies in schools within their department.
    - SchoolAdmin/Teacher: sees only notifications for book copies in their school.

    Validates: Requirement 18.2
    """
    return notification_service.list_damage_notifications(
        db=db,
        params=params,
        scope=scope,
    )


@router.get(
    "/{notification_id}",
    response_model=DamageNotificationResponse,
)
def get_damage_notification(
    notification_id: int,
    current_user: User = Depends(
        require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER)
    ),
    db: Session = Depends(get_db),
) -> DamageNotificationResponse:
    """Get a damage notification by ID.

    Returns 404 if no notification with the specified ID exists.

    Validates: Requirements 18.3, 18.6
    """
    return notification_service.get_damage_notification(db, notification_id)


@router.put(
    "/{notification_id}/resolve",
    response_model=DamageNotificationResponse,
)
def resolve_damage_notification(
    notification_id: int,
    payload: DamageNotificationResolve,
    current_user: User = Depends(
        require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER)
    ),
    db: Session = Depends(get_db),
) -> DamageNotificationResponse:
    """Resolve a damage notification.

    Updates the notification status to "resolved", records the resolution note,
    and sets resolved_at to the current timestamp.

    Returns 404 if notification not found.
    Returns 409 if the notification is not in "open" status.

    Validates: Requirements 18.4, 18.7
    """
    return notification_service.resolve_damage_notification(
        db=db,
        notification_id=notification_id,
        resolution_note=payload.resolution_note,
    )
