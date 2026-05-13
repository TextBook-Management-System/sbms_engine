from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from app.core.pagination import PaginatedResponse, PaginationParams
from app.database.session import get_db
from app.schemas.allocations import AllocationCreate, AllocationResponse
from app.services import allocation_service

router = APIRouter(prefix="/allocations", tags=["allocations"])


@router.post("", response_model=AllocationResponse, status_code=HTTP_201_CREATED)
def create_allocation(payload: AllocationCreate, db: Session = Depends(get_db)):
    allocation = allocation_service.allocate(
        db=db,
        book_copy_id=payload.book_copy_id,
        learner_id=payload.learner_id,
        scan_image_url=payload.scan_image_url,
        ai_condition=payload.ai_condition,
        ai_confidence_score=payload.ai_confidence_score,
        ai_quality_score=payload.ai_quality_score,
        ai_issues=payload.ai_issues,
    )
    return allocation


@router.get("", response_model=PaginatedResponse[AllocationResponse])
def list_allocations(
    learner_id: Optional[int] = Query(default=None, description="Filter by learner"),
    book_copy_id: Optional[int] = Query(default=None, description="Filter by book copy"),
    status: Optional[str] = Query(default=None, description="Filter by status (active or returned)"),
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    return allocation_service.list_allocations(
        db=db,
        params=params,
        learner_id=learner_id,
        book_copy_id=book_copy_id,
        status=status,
    )


@router.get("/{id}", response_model=AllocationResponse)
def get_allocation(id: int, db: Session = Depends(get_db)):
    return allocation_service.get_by_id(db, id)


@router.put("/{id}/return", response_model=AllocationResponse)
def return_allocation(id: int, db: Session = Depends(get_db)):
    return allocation_service.return_allocation(db, id)
