"""Replacement requests endpoints for the SBMS API.

Provides operations for replacement requests with role-based access control:
- POST /replacement-requests: Create a new replacement request
- GET /replacement-requests: List replacement requests scoped by role
- GET /replacement-requests/{id}: Get a replacement request by ID
- PUT /replacement-requests/{id}/approve: Approve a pending request (DeptAdmin only)
- PUT /replacement-requests/{id}/reject: Reject a pending request (DeptAdmin only)

Validates: Requirements 19.1–19.4, 19.8, 19.9, 19.11
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
from app.schemas.replacement_requests import (
    ReplacementRequestCreate,
    ReplacementRequestReject,
    ReplacementRequestResponse,
)
from app.services.notification_service import (
    approve_replacement_request,
    create_replacement_request,
    get_replacement_request,
    list_replacement_requests,
    reject_replacement_request,
)

router = APIRouter(prefix="/replacement-requests", tags=["replacement-requests"])


@router.post(
    "",
    response_model=ReplacementRequestResponse,
    status_code=201,
)
def create_replacement_request_endpoint(
    payload: ReplacementRequestCreate,
    current_user: User = Depends(
        require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER)
    ),
    db: Session = Depends(get_db),
) -> ReplacementRequestResponse:
    """Create a new replacement request with status "pending".

    Requires a valid damage_notification_id. Returns 404 if the
    referenced damage notification does not exist.

    Validates: Requirement 19.1, 19.9
    """
    request = create_replacement_request(
        db=db,
        damage_notification_id=payload.damage_notification_id,
    )
    return request


@router.get(
    "",
    response_model=PaginatedResponse[ReplacementRequestResponse],
)
def list_replacement_requests_endpoint(
    params: PaginationParams = Depends(),
    scope: Scope = Depends(get_user_scope),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ReplacementRequestResponse]:
    """List replacement requests scoped by the user's role.

    - DeptAdmin: sees all requests within their department.
    - SchoolAdmin/Teacher: sees only requests for their school.

    Validates: Requirement 19.2
    """
    return list_replacement_requests(db=db, params=params, scope=scope)


@router.get(
    "/{request_id}",
    response_model=ReplacementRequestResponse,
)
def get_replacement_request_endpoint(
    request_id: int,
    current_user: User = Depends(
        require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER)
    ),
    db: Session = Depends(get_db),
) -> ReplacementRequestResponse:
    """Get a replacement request by ID.

    Returns 404 if the replacement request does not exist.

    Validates: Requirement 19.11
    """
    return get_replacement_request(db=db, request_id=request_id)


@router.put(
    "/{request_id}/approve",
    response_model=ReplacementRequestResponse,
)
def approve_replacement_request_endpoint(
    request_id: int,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN)),
    db: Session = Depends(get_db),
) -> ReplacementRequestResponse:
    """Approve a pending replacement request. DeptAdmin only.

    Returns 409 if the request is not in "pending" status.
    Returns 403 if the user is not a DeptAdmin.

    Validates: Requirements 19.3, 19.8
    """
    return approve_replacement_request(db=db, request_id=request_id)


@router.put(
    "/{request_id}/reject",
    response_model=ReplacementRequestResponse,
)
def reject_replacement_request_endpoint(
    request_id: int,
    payload: ReplacementRequestReject,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN)),
    db: Session = Depends(get_db),
) -> ReplacementRequestResponse:
    """Reject a pending replacement request. DeptAdmin only.

    Requires a reason (1-1000 characters).
    Returns 409 if the request is not in "pending" status.
    Returns 403 if the user is not a DeptAdmin.

    Validates: Requirements 19.4, 19.8
    """
    return reject_replacement_request(
        db=db, request_id=request_id, reason=payload.reason
    )
