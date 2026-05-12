"""User management endpoints.

Provides:
- GET /users — paginated list filtered by requester's scope
- GET /users/{id} — get user by ID (within scope)
- PUT /users/{id} — update user profile
- DELETE /users/{id} — deactivate user (set is_active=False), prevent self-deactivation
- POST /users/{user_id}/roles — assign role to user (DeptAdmin only)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.rbac import (
    ROLE_DEPT_ADMIN,
    ROLE_SCHOOL_ADMIN,
    Scope,
    get_user_scope,
    require_role,
)
from app.database.session import get_db
from app.models.database import School, User, UserRole
from app.schemas.users import (
    RoleAssignRequest,
    UserUpdateRequest,
    UserWithRolesResponse,
)

router = APIRouter(prefix="/users", tags=["users"])

SUPPORTED_ROLES = {"DeptAdmin", "SchoolAdmin", "Teacher", "Parent"}


def _apply_scope_filter(query, scope: Scope, db: Session):
    """Filter a User query based on the requester's organizational scope."""
    if scope.role == ROLE_DEPT_ADMIN and scope.department_id is not None:
        # DeptAdmin sees all users in their department directly,
        # plus users in schools belonging to their department
        school_ids = (
            db.query(School.id)
            .filter(School.department_id == scope.department_id)
            .subquery()
        )
        query = query.filter(
            (User.department_id == scope.department_id)
            | (User.school_id.in_(school_ids))
        )
    elif scope.role == ROLE_SCHOOL_ADMIN and scope.school_id is not None:
        query = query.filter(User.school_id == scope.school_id)
    return query


def _is_user_in_dept_scope(user: User, department_id: int, db: Session) -> bool:
    """Check if a user belongs to the given department scope."""
    if user.department_id == department_id:
        return True
    if user.school_id is not None:
        school = db.query(School).filter(School.id == user.school_id).first()
        if school and school.department_id == department_id:
            return True
    return False


def _check_user_in_scope(user: User, scope: Scope, db: Session) -> None:
    """Verify that the target user is within the requester's scope.

    Raises ForbiddenError if the target user is outside scope.
    """
    if scope.role == ROLE_DEPT_ADMIN and scope.department_id is not None:
        if not _is_user_in_dept_scope(user, scope.department_id, db):
            raise ForbiddenError(
                detail="Access denied. User is outside your department scope."
            )
    elif scope.role == ROLE_SCHOOL_ADMIN and scope.school_id is not None:
        if user.school_id != scope.school_id:
            raise ForbiddenError(
                detail="Access denied. User is outside your school scope."
            )


@router.get(
    "",
    response_model=PaginatedResponse[UserWithRolesResponse],
)
def list_users(
    params: PaginationParams = Depends(),
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    scope: Scope = Depends(get_user_scope),
    db: Session = Depends(get_db),
):
    """Return a paginated list of users filtered by the requester's scope.

    DeptAdmin sees all users within their department.
    SchoolAdmin sees all users within their school.
    """
    query = db.query(User)
    query = _apply_scope_filter(query, scope, db)
    return paginate(query, params)


@router.get(
    "/{id}",
    response_model=UserWithRolesResponse,
)
def get_user(
    id: int,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    scope: Scope = Depends(get_user_scope),
    db: Session = Depends(get_db),
):
    """Get a user by ID. Must be within the requester's scope."""
    user = db.query(User).filter(User.id == id).first()
    if user is None:
        raise NotFoundError(detail=f"User with id {id} not found")
    _check_user_in_scope(user, scope, db)
    return user


@router.put(
    "/{id}",
    response_model=UserWithRolesResponse,
)
def update_user(
    id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    scope: Scope = Depends(get_user_scope),
    db: Session = Depends(get_db),
):
    """Update a user profile. Target user must be within the requester's scope."""
    user = db.query(User).filter(User.id == id).first()
    if user is None:
        raise NotFoundError(detail=f"User with id {id} not found")
    _check_user_in_scope(user, scope, db)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deactivate_user(
    id: int,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN, ROLE_SCHOOL_ADMIN)),
    scope: Scope = Depends(get_user_scope),
    db: Session = Depends(get_db),
):
    """Deactivate a user (set is_active=False).

    Returns 403 if attempting to deactivate own account.
    """
    if current_user.id == id:
        raise ForbiddenError(detail="Self-deactivation is not permitted")

    user = db.query(User).filter(User.id == id).first()
    if user is None:
        raise NotFoundError(detail=f"User with id {id} not found")
    _check_user_in_scope(user, scope, db)

    user.is_active = False
    db.commit()


@router.post(
    "/{user_id}/roles",
    response_model=UserWithRolesResponse,
    status_code=status.HTTP_200_OK,
)
def assign_role(
    user_id: int,
    payload: RoleAssignRequest,
    current_user: User = Depends(require_role(ROLE_DEPT_ADMIN)),
    db: Session = Depends(get_db),
):
    """Assign a role to a user. Only DeptAdmin can assign roles.

    Validates that the role is in the supported roles list.
    """
    # Validate role is supported
    if payload.role.value not in SUPPORTED_ROLES:
        raise ValidationError(
            detail=f"Invalid role. Supported roles: {', '.join(sorted(SUPPORTED_ROLES))}"
        )

    # Find the target user
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise NotFoundError(detail=f"User with id {user_id} not found")

    # Create the role assignment
    new_role = UserRole(user_id=user_id, role=payload.role.value)
    db.add(new_role)
    db.commit()
    db.refresh(user)
    return user
