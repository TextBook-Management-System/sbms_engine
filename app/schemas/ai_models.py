"""Pydantic schemas for AI model versions endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class AIModelCreate(BaseModel):
    """Request schema for registering a new AI model version."""

    model_name: str = Field(..., min_length=1, max_length=100)
    model_version: str = Field(..., min_length=1, max_length=50)
    model_type: str = Field(..., min_length=1, max_length=50)


class AIModelResponse(BaseModel):
    """Response schema for an AI model version."""

    id: int
    model_name: str
    model_version: str
    model_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
