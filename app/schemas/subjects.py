"""Pydantic schemas for subjects endpoints."""

from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    """Request schema for creating a subject."""

    name: str = Field(..., min_length=1, max_length=100)


class SubjectUpdate(BaseModel):
    """Request schema for updating a subject."""

    name: str = Field(..., min_length=1, max_length=100)


class SubjectResponse(BaseModel):
    """Response schema for a subject."""

    id: int
    name: str

    model_config = {"from_attributes": True}
