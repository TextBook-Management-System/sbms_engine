"""Escalations endpoints for the SBMS API.

Provides operations for escalations with role-based access control:
- POST /escalations: Create a new escalation
- GET /escalations: List escalations scoped by role
- GET /escalations/{id}: Get an escalation by ID
- PUT /escalations/{id}/resolve: Resolve an open escalation

Validates: Requirements 19.5–19.7, 19.10
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
from app.schemas.escalations import (
    EscalationCreate,
    EscalationResolve,
    EscalationResponse,
)
from app.services.notification_service import (
    create_escalation,
    get_escalation,
    list_escalations,
    resolve_escalation,
)

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.post(
    "",
    response_model=EscalationResponse,
    status_code=201,
)
def create_escalation_endpoint(
    payload: EscalationCreate,
    current_user: User = Depends(
        require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER)
    ),
    db: Session = Depends(get_db),
) -> EscalationResponse:
    """Create a new escalation with status "open".

    Requires a valid replacement_request_id and a reason (1-1000 chars).
    Returns 404 if the referenced replacement request does not exist.

    Validates: Requirements 19.5, 19.10
    """
    return create_escalation(
        db=db,
        replacement_request_id=payload.replacement_request_id,
        reason=payload.reason,
    )


@router.get(
    "",
    response_model=PaginatedResponse[EscalationResponse],
)
def list_escalations_endpoint(
    params: PaginationParams = Depends(),
    scope: Scope = Depends(get_user_scope),
    db: Session = Depends(get_db),
) -> PaginatedResponse[EscalationResponse]:
    """List escalations scoped by the user's role.

    - DeptAdmin: sees all escalations within their department.
    - SchoolAdmin/Teacher: sees only escalations for their school.

    Validates: Requirement 19.6
    """
    return list_escalations(db=db, params=params, scope=scope)


@router.get(
    "/{escalation_id}",
    response_model=EscalationResponse,
)
def get_escalation_endpoint(
    escalation_id: int,
    current_user: User = Depends(
        require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER)
    ),
    db: Session = Depends(get_db),
) -> EscalationResponse:
    """Get an escalation by ID.

    Returns 404 if the escalation does not exist.
    """
    return get_escalation(db=db, escalation_id=escalation_id)


@router.put(
    "/{escalation_id}/resolve",
    response_model=EscalationResponse,
)
def resolve_escalation_endpoint(
    escalation_id: int,
    payload: EscalationResolve,
    current_user: User = Depends(
        require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER)
    ),
    db: Session = Depends(get_db),
) -> EscalationResponse:
    """Resolve an open escalation.

    Requires a resolution_note (1-2000 chars).
    Returns 409 if the escalation is not in "open" status.

    Validates: Requirement 19.7
    """
    return resolve_escalation(
        db=db,
        escalation_id=escalation_id,
        resolution_note=payload.resolution_note,
    )
