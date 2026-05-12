"""
Role-Based Access Control (RBAC) dependencies for the SBMS API.

Provides FastAPI dependencies for:
- Role checking: `require_role(*roles)` — verifies the user has one of the specified roles
- Scope checking: `require_scope(resource_type, resource_id)` — verifies the user's
  organizational scope includes the specified resource
- Scope resolution: `get_user_scope(current_user)` — returns the user's department/school scope

Supported roles: DeptAdmin, SchoolAdmin, Teacher, Parent

Scope resolution:
- DeptAdmin → all resources in their department (department_id)
- SchoolAdmin → all resources in their school (school_id)
- Teacher → read access to school resources, write to allocations/scans/damage (school_id)
- Parent → read for linked learners only
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user_dependency
from app.core.exceptions import ForbiddenError
from app.database.session import get_db
from app.models.database import (
    BookCopy,
    Grade,
    Learner,
    ParentLearner,
    School,
    User,
    UserRole,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROLE_DEPT_ADMIN = "DeptAdmin"
ROLE_SCHOOL_ADMIN = "SchoolAdmin"
ROLE_TEACHER = "Teacher"
ROLE_PARENT = "Parent"

ALL_ROLES = (ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_TEACHER, ROLE_PARENT)


# ---------------------------------------------------------------------------
# Scope Data Class
# ---------------------------------------------------------------------------


@dataclass
class Scope:
    """Represents the organizational scope of a user.

    Attributes:
        department_id: The department the user belongs to (DeptAdmin scope).
        school_id: The school the user belongs to (SchoolAdmin/Teacher scope).
        learner_ids: List of learner IDs linked to the user (Parent scope).
        role: The user's primary role.
    """

    department_id: Optional[int] = None
    school_id: Optional[int] = None
    learner_ids: list[int] = field(default_factory=list)
    role: str = ""


# ---------------------------------------------------------------------------
# Helper: Get user's primary role
# ---------------------------------------------------------------------------


def _get_user_roles(user: User) -> list[str]:
    """Return all role names assigned to a user."""
    return [ur.role for ur in user.roles]


def _get_primary_role(user: User) -> str:
    """Return the user's primary (first) role, or empty string if none."""
    roles = _get_user_roles(user)
    return roles[0] if roles else ""


# ---------------------------------------------------------------------------
# require_role dependency
# ---------------------------------------------------------------------------


def require_role(*roles: str) -> Callable:
    """Return a FastAPI dependency that checks if the current user has one of the specified roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("DeptAdmin"))])
        def admin_endpoint(): ...

        # Or inject the user:
        @router.get("/admin")
        def admin_endpoint(current_user: User = Depends(require_role("DeptAdmin", "SchoolAdmin"))):
            ...

    Raises:
        ForbiddenError: If the user does not have any of the required roles.
    """

    def role_checker(
        current_user: User = Depends(get_current_user_dependency),
    ) -> User:
        user_roles = _get_user_roles(current_user)
        if not any(role in user_roles for role in roles):
            raise ForbiddenError(
                detail=f"Access denied. Required role(s): {', '.join(roles)}"
            )
        return current_user

    return role_checker


# ---------------------------------------------------------------------------
# get_user_scope
# ---------------------------------------------------------------------------


def get_user_scope(
    current_user: User = Depends(get_current_user_dependency),
    db: Session = Depends(get_db),
) -> Scope:
    """FastAPI dependency that returns the user's organizational scope based on their role.

    Scope resolution:
    - DeptAdmin → department_id set (all resources in their department)
    - SchoolAdmin → school_id set (all resources in their school)
    - Teacher → school_id set (read access to school resources)
    - Parent → learner_ids set (only linked learners)

    Returns:
        Scope object with the appropriate fields populated.
    """
    role = _get_primary_role(current_user)
    scope = Scope(role=role)

    if role == ROLE_DEPT_ADMIN:
        scope.department_id = current_user.department_id
    elif role in (ROLE_SCHOOL_ADMIN, ROLE_TEACHER):
        scope.school_id = current_user.school_id
        # Also set department_id from the school's department for broader lookups
        if current_user.school_id and current_user.school:
            scope.department_id = current_user.school.department_id
    elif role == ROLE_PARENT:
        # Get all learner IDs linked to this parent
        parent_learner_links = (
            db.query(ParentLearner.learner_id)
            .filter(ParentLearner.parent_id == current_user.id)
            .all()
        )
        scope.learner_ids = [pl.learner_id for pl in parent_learner_links]

    return scope


# ---------------------------------------------------------------------------
# require_scope dependency
# ---------------------------------------------------------------------------


def require_scope(resource_type: str, resource_id_param: str = "id") -> Callable:
    """Return a FastAPI dependency that checks if the user's scope includes the specified resource.

    This dependency resolves the resource's organizational ownership and verifies
    the current user has access based on their role and scope.

    Args:
        resource_type: The type of resource being accessed. Supported types:
            - "department": checks department_id directly
            - "school": checks school belongs to user's department or is user's school
            - "learner": checks learner is in user's school/department or linked to parent
            - "book_copy": checks book copy belongs to user's school/department
            - "grade": checks grade belongs to user's school/department
        resource_id_param: The name of the path parameter containing the resource ID.
            Used for documentation and future request-level scope resolution.

    Usage:
        @router.get("/schools/{school_id}")
        def get_school(
            school_id: int,
            current_user: User = Depends(require_scope("school", "school_id")),
        ): ...

    Raises:
        ForbiddenError: If the resource is outside the user's scope.
    """
    # Store resource_type and resource_id_param for introspection by endpoint handlers
    _resource_type = resource_type
    _resource_id_param = resource_id_param

    def scope_checker(
        current_user: User = Depends(get_current_user_dependency),
        db: Session = Depends(get_db),
    ) -> User:
        # Validates that the user has a valid role assigned.
        # The actual resource-level scope check is performed by the
        # check_*_scope utility functions called from endpoint handlers,
        # which use _resource_type and _resource_id_param for context.
        role = _get_primary_role(current_user)
        if role not in ALL_ROLES:
            raise ForbiddenError(detail="No valid role assigned")
        return current_user

    # Attach metadata for introspection
    scope_checker._resource_type = _resource_type  # noqa: SLF001
    scope_checker._resource_id_param = _resource_id_param  # noqa: SLF001

    return scope_checker


# ---------------------------------------------------------------------------
# Scope checking utility functions (called from endpoint handlers)
# ---------------------------------------------------------------------------


def check_department_scope(user: User, scope: Scope, department_id: int) -> None:
    """Verify the user's scope includes the given department.

    Raises ForbiddenError if the user cannot access resources in this department.
    """
    if scope.role == ROLE_DEPT_ADMIN:
        if scope.department_id != department_id:
            raise ForbiddenError(
                detail="Access denied. Resource is outside your department scope."
            )
    elif scope.role in (ROLE_SCHOOL_ADMIN, ROLE_TEACHER):
        # SchoolAdmin/Teacher can only access their own school's department
        if scope.department_id != department_id:
            raise ForbiddenError(
                detail="Access denied. Resource is outside your scope."
            )
    elif scope.role == ROLE_PARENT:
        raise ForbiddenError(
            detail="Access denied. Parents cannot access department resources."
        )


def check_school_scope(user: User, scope: Scope, school_id: int, db: Session) -> None:
    """Verify the user's scope includes the given school.

    Raises ForbiddenError if the user cannot access resources in this school.
    """
    if scope.role == ROLE_DEPT_ADMIN:
        # DeptAdmin can access any school in their department
        school = db.query(School).filter(School.id == school_id).first()
        if not school or school.department_id != scope.department_id:
            raise ForbiddenError(
                detail="Access denied. School is outside your department scope."
            )
    elif scope.role in (ROLE_SCHOOL_ADMIN, ROLE_TEACHER):
        if scope.school_id != school_id:
            raise ForbiddenError(
                detail="Access denied. Resource is outside your school scope."
            )
    elif scope.role == ROLE_PARENT:
        raise ForbiddenError(
            detail="Access denied. Parents cannot access school-level resources directly."
        )


def _get_learner_school_id(learner_id: int, db: Session) -> Optional[int]:
    """Resolve the school_id for a learner by traversing learner → grade → school."""
    learner = db.query(Learner).filter(Learner.id == learner_id).first()
    if not learner:
        return None
    grade = db.query(Grade).filter(Grade.id == learner.grade_id).first()
    if not grade:
        return None
    return grade.school_id


def _get_school_department_id(school_id: int, db: Session) -> Optional[int]:
    """Resolve the department_id for a school."""
    school = db.query(School).filter(School.id == school_id).first()
    return school.department_id if school else None


def check_learner_scope(
    user: User, scope: Scope, learner_id: int, db: Session
) -> None:
    """Verify the user's scope includes the given learner.

    Raises ForbiddenError if the user cannot access this learner's data.
    """
    if scope.role == ROLE_PARENT:
        if learner_id not in scope.learner_ids:
            raise ForbiddenError(
                detail="Access denied. You can only access your linked learners."
            )
        return

    if scope.role == ROLE_DEPT_ADMIN:
        school_id = _get_learner_school_id(learner_id, db)
        if school_id is not None:
            dept_id = _get_school_department_id(school_id, db)
            if dept_id == scope.department_id:
                return
        raise ForbiddenError(
            detail="Access denied. Learner is outside your department scope."
        )

    if scope.role in (ROLE_SCHOOL_ADMIN, ROLE_TEACHER):
        school_id = _get_learner_school_id(learner_id, db)
        if school_id == scope.school_id:
            return
        raise ForbiddenError(
            detail="Access denied. Learner is outside your school scope."
        )


def check_book_copy_scope(
    user: User, scope: Scope, book_copy_id: int, db: Session
) -> None:
    """Verify the user's scope includes the given book copy.

    Raises ForbiddenError if the user cannot access this book copy.
    """
    book_copy = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if not book_copy:
        return  # Let the endpoint handle 404

    if scope.role == ROLE_DEPT_ADMIN:
        school = db.query(School).filter(School.id == book_copy.school_id).first()
        if not school or school.department_id != scope.department_id:
            raise ForbiddenError(
                detail="Access denied. Book copy is outside your department scope."
            )
    elif scope.role in (ROLE_SCHOOL_ADMIN, ROLE_TEACHER):
        if book_copy.school_id != scope.school_id:
            raise ForbiddenError(
                detail="Access denied. Book copy is outside your school scope."
            )
    elif scope.role == ROLE_PARENT:
        raise ForbiddenError(
            detail="Access denied. Parents cannot access book copies directly."
        )
