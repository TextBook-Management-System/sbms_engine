"""Pydantic schemas for user management endpoints."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RoleName(str, PyEnum):
    """Supported user roles."""

    DEPT_ADMIN = "DeptAdmin"
    SCHOOL_ADMIN = "SchoolAdmin"
    TEACHER = "Teacher"
    PARENT = "Parent"


class UserUpdateRequest(BaseModel):
    """Request schema for updating a user profile."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=200)
    is_active: Optional[bool] = None
    department_id: Optional[int] = None
    school_id: Optional[int] = None


class RoleAssignRequest(BaseModel):
    """Request schema for assigning a role to a user."""

    role: RoleName


class UserRoleResponse(BaseModel):
    """Response schema for a user role."""

    id: int
    user_id: int
    role: str

    model_config = {"from_attributes": True}


class UserWithRolesResponse(BaseModel):
    """Response schema for user with roles."""

    id: int
    email: str
    full_name: str
    is_active: bool
    department_id: Optional[int] = None
    school_id: Optional[int] = None
    roles: list[UserRoleResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
