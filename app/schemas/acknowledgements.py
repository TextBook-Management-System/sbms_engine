"""Pydantic schemas for parent acknowledgements endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AcknowledgementCreate(BaseModel):
    """Request schema for creating a parent acknowledgement."""

    allocation_id: int


class AcknowledgementReject(BaseModel):
    """Request schema for rejecting an acknowledgement."""

    reason: str = Field(..., min_length=1, max_length=500)


class AcknowledgementResponse(BaseModel):
    """Response schema for a parent acknowledgement."""

    id: int
    allocation_id: int
    parent_id: int
    status: str
    reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
