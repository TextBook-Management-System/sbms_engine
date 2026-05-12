"""Pydantic schemas for books catalog endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    """Request schema for creating a book."""

    title: str = Field(..., min_length=1, max_length=200)
    subject_id: int
    grade_level_id: int
    isbn: Optional[str] = Field(None, max_length=50)
    publisher: Optional[str] = Field(None, max_length=200)
    author: Optional[str] = Field(None, max_length=200)
    edition: Optional[str] = Field(None, max_length=100)


class BookUpdate(BaseModel):
    """Request schema for updating a book."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    subject_id: Optional[int] = None
    grade_level_id: Optional[int] = None
    isbn: Optional[str] = Field(None, max_length=50)
    publisher: Optional[str] = Field(None, max_length=200)
    author: Optional[str] = Field(None, max_length=200)
    edition: Optional[str] = Field(None, max_length=100)


class BookResponse(BaseModel):
    """Response schema for a book."""

    id: int
    title: str
    subject_id: int
    grade_level_id: int
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    author: Optional[str] = None
    edition: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
