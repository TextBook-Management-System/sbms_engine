"""Pydantic schemas for grades endpoints (school grades/classes)."""

from pydantic import BaseModel, Field


class GradeCreate(BaseModel):
    """Request schema for creating a grade within a school."""

    name: str = Field(..., min_length=1, max_length=100)


class GradeUpdate(BaseModel):
    """Request schema for updating a grade."""

    name: str = Field(..., min_length=1, max_length=100)


class GradeResponse(BaseModel):
    """Response schema for a grade."""

    id: int
    school_id: int
    name: str

    model_config = {"from_attributes": True}
