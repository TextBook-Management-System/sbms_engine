"""Pydantic schemas for escalations endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EscalationCreate(BaseModel):
    """Request schema for creating an escalation."""

    replacement_request_id: int
    reason: str = Field(..., min_length=1, max_length=1000)


class EscalationResolve(BaseModel):
    """Request schema for resolving an escalation."""

    resolution_note: str = Field(..., min_length=1, max_length=2000)


class EscalationResponse(BaseModel):
    """Response schema for an escalation."""

    id: int
    replacement_request_id: int
    reason: str
    status: str
    resolution_note: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
