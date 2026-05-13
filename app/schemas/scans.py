"""Pydantic schemas for book condition scans endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.book_copies import BookCondition


class ScanCreate(BaseModel):
    """Request schema for creating a book condition scan."""

    book_copy_id: int


class ScanVerifyRequest(BaseModel):
    """Request schema for verifying a scan with human-assessed condition."""

    verified_condition: BookCondition


class ScanResponse(BaseModel):
    """Response schema for a book condition scan."""

    id: int
    book_copy_id: int
    ai_model_id: int
    condition: str
    confidence_score: float
    verified_condition: Optional[str] = None
    ai_issues: Optional[str] = None
    ai_suggestions: Optional[str] = None
    ai_quality_score: Optional[int] = None
    scan_image_path: str
    scanned_at: datetime

    model_config = {"from_attributes": True}
