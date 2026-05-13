"""Learners endpoints with CRUD, filtering, and parent-learner link management.

Provides:
- POST /learners → create a learner
- GET /learners → paginated list with optional school_id and grade_id filters
- GET /learners/{id} → get learner by ID
- PUT /learners/{id} → update learner
- POST /learners/{learner_id}/parents → link a parent to a learner
- GET /learners/{learner_id}/parents → list parents linked to a learner
- DELETE /learners/{learner_id}/parents/{parent_id} → remove parent-learner link

Validates: Requirements 8.3–8.12
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.database.session import get_db
from app.models.database import Grade, Learner, ParentLearner, User, UserRole
from app.schemas.learners import (
    LearnerCreate,
    LearnerResponse,
    LearnerUpdate,
    ParentLearnerCreate,
    ParentLearnerResponse,
)
from app.services import crud_service

router = APIRouter(prefix="/learners", tags=["learners"])


# ---------------------------------------------------------------------------
# Helper validators
# ---------------------------------------------------------------------------


def _validate_grade_exists(db: Session, grade_id: int) -> None:
    """Check that the referenced grade_id exists. Raise 404 if not."""
    grade = db.query(Grade).filter(Grade.id == grade_id).first()
    if grade is None:
        raise NotFoundError(detail=f"Grade with id {grade_id} not found")


def _validate_learner_exists(db: Session, learner_id: int) -> Learner:
    """Check that the learner exists. Raise 404 if not. Returns the learner."""
    learner = db.query(Learner).filter(Learner.id == learner_id).first()
    if learner is None:
        raise NotFoundError(detail=f"Learner with id {learner_id} not found")
    return learner


def _validate_user_has_parent_role(db: Session, user_id: int) -> None:
    """Check that the user exists and has the Parent role. Raise 404 if not found."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise NotFoundError(detail=f"User with id {user_id} not found")

    has_parent_role = (
        db.query(UserRole)
        .filter(UserRole.user_id == user_id, UserRole.role == "Parent")
        .first()
    )
    if has_parent_role is None:
        raise NotFoundError(
            detail=f"User with id {user_id} does not have the Parent role"
        )


# ---------------------------------------------------------------------------
# Learner CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=LearnerResponse, status_code=HTTP_201_CREATED)
def create_learner(
    payload: LearnerCreate,
    db: Session = Depends(get_db),
):
    """Create a new learner. Validates that grade_id references an existing grade.
    
    Optionally links the learner to a parent if parent_id is provided.
    """
    _validate_grade_exists(db, payload.grade_id)

    learner = Learner(
        grade_id=payload.grade_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        id_number=payload.id_number,
        gender=payload.gender,
        date_of_birth=payload.date_of_birth,
    )
    db.add(learner)
    db.flush()

    # Optionally link to parent
    if payload.parent_id is not None:
        _validate_user_has_parent_role(db, payload.parent_id)
        # Check for duplicate link
        existing_link = (
            db.query(ParentLearner)
            .filter(
                ParentLearner.parent_id == payload.parent_id,
                ParentLearner.learner_id == learner.id,
            )
            .first()
        )
        if existing_link is None:
            link = ParentLearner(parent_id=payload.parent_id, learner_id=learner.id)
            db.add(link)

    db.commit()
    db.refresh(learner)
    return learner


@router.get("", response_model=PaginatedResponse[LearnerResponse])
def list_learners(
    school_id: Optional[int] = Query(default=None, description="Filter by school"),
    grade_id: Optional[int] = Query(default=None, description="Filter by grade"),
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """List learners with optional school_id and grade_id filters and pagination.

    The school_id filter joins through Grade to find learners in a specific school.
    """
    query = db.query(Learner)

    if school_id is not None:
        # Join through Grade to filter by school
        query = query.join(Grade, Learner.grade_id == Grade.id).filter(
            Grade.school_id == school_id
        )

    if grade_id is not None:
        query = query.filter(Learner.grade_id == grade_id)

    return paginate(query, params)


@router.get("/{id}", response_model=LearnerResponse)
def get_learner(id: int, db: Session = Depends(get_db)):
    """Get a learner by ID."""
    return crud_service.get_by_id(db, Learner, id)


@router.put("/{id}", response_model=LearnerResponse)
def update_learner(id: int, payload: LearnerUpdate, db: Session = Depends(get_db)):
    """Update a learner. Validates grade_id FK if provided."""
    data = payload.model_dump(exclude_unset=True)

    if "grade_id" in data and data["grade_id"] is not None:
        _validate_grade_exists(db, data["grade_id"])

    learner = crud_service.update(db, Learner, id, data)
    return learner


# ---------------------------------------------------------------------------
# Parent-Learner link endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{learner_id}/parents",
    response_model=ParentLearnerResponse,
    status_code=HTTP_201_CREATED,
)
def create_parent_learner_link(
    learner_id: int,
    payload: ParentLearnerCreate,
    db: Session = Depends(get_db),
):
    """Link a parent to a learner.

    Validates:
    - learner_id references an existing learner (404)
    - user_id references an existing user with the Parent role (404)
    - The link does not already exist (409)
    """
    _validate_learner_exists(db, learner_id)
    _validate_user_has_parent_role(db, payload.user_id)

    # Check for duplicate link
    existing_link = (
        db.query(ParentLearner)
        .filter(
            ParentLearner.learner_id == learner_id,
            ParentLearner.parent_id == payload.user_id,
        )
        .first()
    )
    if existing_link is not None:
        raise ConflictError(
            detail="Parent-learner link already exists for this learner and parent"
        )

    link = ParentLearner(parent_id=payload.user_id, learner_id=learner_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.get("/{learner_id}/parents", response_model=List[ParentLearnerResponse])
def list_parent_learner_links(
    learner_id: int,
    db: Session = Depends(get_db),
):
    """List all parents linked to a learner.

    Validates that the learner exists (404).
    """
    _validate_learner_exists(db, learner_id)

    links = (
        db.query(ParentLearner)
        .filter(ParentLearner.learner_id == learner_id)
        .all()
    )
    return links


@router.delete(
    "/{learner_id}/parents/{parent_id}",
    status_code=HTTP_204_NO_CONTENT,
)
def delete_parent_learner_link(
    learner_id: int,
    parent_id: int,
    db: Session = Depends(get_db),
):
    """Remove a parent-learner link.

    Validates that the link exists (404 if not found).
    """
    link = (
        db.query(ParentLearner)
        .filter(
            ParentLearner.learner_id == learner_id,
            ParentLearner.parent_id == parent_id,
        )
        .first()
    )
    if link is None:
        raise NotFoundError(
            detail=f"Parent-learner link not found for learner {learner_id} and parent {parent_id}"
        )

    db.delete(link)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Parent's view: learners with books, allocations, and acknowledgements
# ---------------------------------------------------------------------------


@router.get("/parent/{parent_id}/children")
def get_parent_learners_with_books(
    parent_id: int,
    db: Session = Depends(get_db),
):
    """Get all learners linked to a parent with their book allocations and acknowledgements.

    Returns each learner with:
    - Learner details
    - All book allocations (with book copy details)
    - Parent acknowledgements for each allocation
    """
    from app.models.database import BookAllocation, BookCopy, Book, ParentAcknowledgement, School

    user = db.query(User).filter(User.id == parent_id).first()
    if user is None:
        raise NotFoundError(detail=f"User with id {parent_id} not found")

    links = db.query(ParentLearner).filter(ParentLearner.parent_id == parent_id).all()

    if not links:
        return {"parent_id": parent_id, "learners": []}

    result_learners = []

    for link in links:
        learner = link.learner
        grade = learner.grade
        school = db.query(School).filter(School.id == grade.school_id).first() if grade else None

        allocations = (
            db.query(BookAllocation)
            .filter(BookAllocation.learner_id == learner.id)
            .all()
        )

        allocation_list = []
        for alloc in allocations:
            book_copy = db.query(BookCopy).filter(BookCopy.id == alloc.book_copy_id).first()

            book_info = None
            if book_copy:
                book = db.query(Book).filter(Book.id == book_copy.book_id).first()
                book_info = {
                    "id": book_copy.id,
                    "qr_code": book_copy.qr_code,
                    "condition": book_copy.condition,
                    "book_title": book.title if book else None,
                    "book_isbn": book.isbn if book else None,
                }

            acknowledgements = (
                db.query(ParentAcknowledgement)
                .filter(
                    ParentAcknowledgement.allocation_id == alloc.id,
                    ParentAcknowledgement.parent_id == parent_id,
                )
                .all()
            )

            ack_list = [
                {
                    "id": ack.id,
                    "status": ack.status,
                    "reason": ack.reason,
                    "created_at": ack.created_at.isoformat() if ack.created_at else None,
                }
                for ack in acknowledgements
            ]

            allocation_list.append({
                "id": alloc.id,
                "status": alloc.status,
                "allocation_date": alloc.allocation_date.isoformat() if alloc.allocation_date else None,
                "return_date": alloc.return_date.isoformat() if alloc.return_date else None,
                "scan_image_url": alloc.scan_image_url,
                "ai_condition": alloc.ai_condition,
                "ai_quality_score": alloc.ai_quality_score,
                "book_copy": book_info,
                "acknowledgements": ack_list,
            })

        result_learners.append({
            "id": learner.id,
            "first_name": learner.first_name,
            "last_name": learner.last_name,
            "grade_id": learner.grade_id,
            "grade_name": grade.name if grade else None,
            "school_name": school.name if school else None,
            "allocations": allocation_list,
        })

    return {
        "parent_id": parent_id,
        "learners": result_learners,
    }
