"""Parent acknowledgements endpoints for the SBMS API.

Provides endpoints for parents to acknowledge book allocations to their children:
- POST /acknowledgements: Create a new acknowledgement (Parent only)
- GET /acknowledgements: List acknowledgements filtered by parent_id
- PUT /acknowledgements/{id}/accept: Accept a pending acknowledgement
- PUT /acknowledgements/{id}/reject: Reject a pending acknowledgement with reason
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.rbac import ROLE_PARENT, require_role
from app.database.session import get_db
from app.models.database import (
    BookAllocation,
    ParentAcknowledgement,
    ParentLearner,
    User,
)
from app.schemas.acknowledgements import (
    AcknowledgementCreate,
    AcknowledgementReject,
    AcknowledgementResponse,
)

router = APIRouter(prefix="/acknowledgements", tags=["acknowledgements"])


def _get_parent_learner_ids(parent_id: int, db: Session) -> list[int]:
    """Get all learner IDs linked to a parent."""
    links = (
        db.query(ParentLearner.learner_id)
        .filter(ParentLearner.parent_id == parent_id)
        .all()
    )
    return [link.learner_id for link in links]


@router.post(
    "",
    response_model=AcknowledgementResponse,
    status_code=201,
)
def create_acknowledgement(
    payload: AcknowledgementCreate,
    current_user: User = Depends(require_role(ROLE_PARENT)),
    db: Session = Depends(get_db),
) -> AcknowledgementResponse:
    """Create a new parent acknowledgement for a book allocation.

    Validates:
    - The allocation exists
    - The allocation's learner is linked to the requesting parent
    - No duplicate acknowledgement exists for the same allocation
    """
    # Validate allocation exists
    allocation = (
        db.query(BookAllocation)
        .filter(BookAllocation.id == payload.allocation_id)
        .first()
    )
    if not allocation:
        raise ValidationError(
            detail=f"Allocation with id {payload.allocation_id} not found or does not belong to your linked child"
        )

    # Validate the allocation's learner is linked to this parent
    parent_learner_ids = _get_parent_learner_ids(current_user.id, db)
    if allocation.learner_id not in parent_learner_ids:
        raise ValidationError(
            detail=f"Allocation with id {payload.allocation_id} not found or does not belong to your linked child"
        )

    # Check for duplicate acknowledgement for the same allocation
    existing = (
        db.query(ParentAcknowledgement)
        .filter(ParentAcknowledgement.allocation_id == payload.allocation_id)
        .first()
    )
    if existing:
        raise ConflictError(
            detail="An acknowledgement already exists for this allocation"
        )

    acknowledgement = ParentAcknowledgement(
        allocation_id=payload.allocation_id,
        parent_id=current_user.id,
        status="pending",
    )
    db.add(acknowledgement)
    db.commit()
    db.refresh(acknowledgement)
    return acknowledgement


@router.get(
    "",
    response_model=PaginatedResponse[AcknowledgementResponse],
)
def list_acknowledgements(
    parent_id: int = Query(..., description="Filter acknowledgements by parent ID"),
    params: PaginationParams = Depends(),
    current_user: User = Depends(require_role(ROLE_PARENT)),
    db: Session = Depends(get_db),
) -> PaginatedResponse[AcknowledgementResponse]:
    """List acknowledgements for a given parent.

    Only the parent themselves can view their acknowledgements.
    """
    # Ensure the requesting parent can only see their own acknowledgements
    if current_user.id != parent_id:
        raise ForbiddenError(
            detail="Access denied. You can only view your own acknowledgements."
        )

    query = (
        db.query(ParentAcknowledgement)
        .filter(ParentAcknowledgement.parent_id == parent_id)
        .order_by(ParentAcknowledgement.created_at.desc())
    )
    return paginate(query, params)


@router.put(
    "/{acknowledgement_id}/accept",
    response_model=AcknowledgementResponse,
)
def accept_acknowledgement(
    acknowledgement_id: int,
    current_user: User = Depends(require_role(ROLE_PARENT)),
    db: Session = Depends(get_db),
) -> AcknowledgementResponse:
    """Accept a pending acknowledgement.

    Only the linked parent can accept, and only if status is "pending".
    """
    acknowledgement = (
        db.query(ParentAcknowledgement)
        .filter(ParentAcknowledgement.id == acknowledgement_id)
        .first()
    )
    if not acknowledgement:
        raise NotFoundError(
            detail=f"Acknowledgement with id {acknowledgement_id} not found"
        )

    # Verify the requesting user is the parent on this acknowledgement
    if acknowledgement.parent_id != current_user.id:
        raise ForbiddenError(
            detail="Access denied. You can only manage your own acknowledgements."
        )

    # Enforce status transition: only pending → accepted
    if acknowledgement.status != "pending":
        raise ConflictError(
            detail=f"Acknowledgement has already been {acknowledgement.status}. Only pending acknowledgements can be accepted."
        )

    acknowledgement.status = "accepted"
    db.commit()
    db.refresh(acknowledgement)
    return acknowledgement


@router.put(
    "/{acknowledgement_id}/reject",
    response_model=AcknowledgementResponse,
)
def reject_acknowledgement(
    acknowledgement_id: int,
    payload: AcknowledgementReject,
    current_user: User = Depends(require_role(ROLE_PARENT)),
    db: Session = Depends(get_db),
) -> AcknowledgementResponse:
    """Reject a pending acknowledgement with a reason.

    Only the linked parent can reject, and only if status is "pending".
    Requires a reason (1-500 characters).
    """
    acknowledgement = (
        db.query(ParentAcknowledgement)
        .filter(ParentAcknowledgement.id == acknowledgement_id)
        .first()
    )
    if not acknowledgement:
        raise NotFoundError(
            detail=f"Acknowledgement with id {acknowledgement_id} not found"
        )

    # Verify the requesting user is the parent on this acknowledgement
    if acknowledgement.parent_id != current_user.id:
        raise ForbiddenError(
            detail="Access denied. You can only manage your own acknowledgements."
        )

    # Enforce status transition: only pending → rejected
    if acknowledgement.status != "pending":
        raise ConflictError(
            detail=f"Acknowledgement has already been {acknowledgement.status}. Only pending acknowledgements can be rejected."
        )

    acknowledgement.status = "rejected"
    acknowledgement.reason = payload.reason
    db.commit()
    db.refresh(acknowledgement)
    return acknowledgement
