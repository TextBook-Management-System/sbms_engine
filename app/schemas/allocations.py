"""Pydantic schemas for book allocations endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AllocationCreate(BaseModel):
    """Request schema for creating a book allocation."""

    book_copy_id: int
    learner_id: int


class AllocationResponse(BaseModel):
    """Response schema for a book allocation."""

    id: int
    book_copy_id: int
    learner_id: int
    status: str
    allocation_date: datetime
    return_date: Optional[datetime] = None

    model_config = {"from_attributes": True}
