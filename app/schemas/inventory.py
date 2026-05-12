"""Pydantic schemas for school books inventory endpoints (read-only)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InventoryResponse(BaseModel):
    """Response schema for a school books inventory record."""

    id: int
    school_id: int
    book_id: int
    quantity: int
    subject: str
    grade_level: str
    condition_notes: Optional[str] = None
    last_updated: datetime

    model_config = {"from_attributes": True}
