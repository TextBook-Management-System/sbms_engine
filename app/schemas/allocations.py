"""Pydantic schemas for book allocations endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AllocationCreate(BaseModel):
    """Request schema for creating a book allocation."""

    book_copy_id: int
    learner_id: int
    scan_image_url: Optional[str] = None
    ai_condition: Optional[str] = None
    ai_confidence_score: Optional[float] = None
    ai_quality_score: Optional[int] = None
    ai_issues: Optional[str] = None
    ai_suggestions: Optional[str] = None


class AllocationResponse(BaseModel):
    """Response schema for a book allocation."""

    id: int
    book_copy_id: int
    learner_id: int
    status: str
    allocation_date: datetime
    return_date: Optional[datetime] = None
    scan_image_url: Optional[str] = None
    ai_condition: Optional[str] = None
    ai_confidence_score: Optional[float] = None
    ai_quality_score: Optional[int] = None
    ai_issues: Optional[str] = None
    ai_suggestions: Optional[str] = None

    model_config = {"from_attributes": True}
