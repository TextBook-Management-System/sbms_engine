"""
Generic CRUD service for simple entity operations.

Provides reusable create, get_by_id, get_all (with pagination), update, and delete
methods that can be used by all simple entity endpoints (grade levels, subjects,
departments, schools, etc.).

Includes:
- Uniqueness checks before create/update (returns 409 ConflictError if duplicate)
- Referential integrity checks before delete (returns 409 ConflictError if referenced)
- Not-found checks (returns 404 NotFoundError)
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple, Type

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate


def _check_uniqueness(
    db: Session,
    model_class: Type,
    data: Dict[str, Any],
    unique_fields: Optional[List[str]],
    exclude_id: Optional[int] = None,
) -> None:
    """Check that unique field values don't already exist in the database.

    Args:
        db: Database session.
        model_class: SQLAlchemy model class.
        data: Dictionary of field values to check.
        unique_fields: List of field names that must be unique.
        exclude_id: ID to exclude from the check (for updates).

    Raises:
        ConflictError: If a record with the same unique field value already exists.
    """
    if not unique_fields:
        return

    for field in unique_fields:
        value = data.get(field)
        if value is None:
            continue

        query = db.query(model_class).filter(
            getattr(model_class, field) == value
        )

        if exclude_id is not None:
            query = query.filter(model_class.id != exclude_id)

        existing = query.first()
        if existing:
            field_label = field.replace("_", " ")
            raise ConflictError(
                detail=f"A record with this {field_label} already exists"
            )


def create(
    db: Session,
    model_class: Type,
    data: Dict[str, Any],
    unique_fields: Optional[List[str]] = None,
) -> Any:
    """Create a new record.

    Args:
        db: Database session.
        model_class: SQLAlchemy model class to instantiate.
        data: Dictionary of field values for the new record.
        unique_fields: Optional list of field names to check for uniqueness
            before creating. If a duplicate is found, raises ConflictError (409).

    Returns:
        The newly created model instance.

    Raises:
        ConflictError: If unique_fields are specified and a duplicate exists.
    """
    _check_uniqueness(db, model_class, data, unique_fields)

    instance = model_class(**data)
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def get_by_id(
    db: Session,
    model_class: Type,
    id: int,
) -> Any:
    """Get a record by its ID.

    Args:
        db: Database session.
        model_class: SQLAlchemy model class to query.
        id: Primary key value.

    Returns:
        The model instance.

    Raises:
        NotFoundError: If no record with the given ID exists.
    """
    instance = db.query(model_class).filter(model_class.id == id).first()
    if instance is None:
        model_name = model_class.__name__
        raise NotFoundError(detail=f"{model_name} with id {id} not found")
    return instance


def get_all(
    db: Session,
    model_class: Type,
    params: PaginationParams,
    filters: Optional[Dict[str, Any]] = None,
) -> PaginatedResponse:
    """Get a paginated list of records with optional filters.

    Args:
        db: Database session.
        model_class: SQLAlchemy model class to query.
        params: Pagination parameters (page, page_size).
        filters: Optional dictionary of {field_name: value} to filter by.
            Only filters with non-None values are applied.

    Returns:
        PaginatedResponse with items, total, page, and page_size.
    """
    query = db.query(model_class)

    if filters:
        for field, value in filters.items():
            if value is not None:
                query = query.filter(getattr(model_class, field) == value)

    return paginate(query, params)


def update(
    db: Session,
    model_class: Type,
    id: int,
    data: Dict[str, Any],
    unique_fields: Optional[List[str]] = None,
) -> Any:
    """Update a record by ID.

    Args:
        db: Database session.
        model_class: SQLAlchemy model class to update.
        id: Primary key of the record to update.
        data: Dictionary of field values to update.
        unique_fields: Optional list of field names to check for uniqueness
            (excluding the current record). Raises ConflictError (409) if duplicate.

    Returns:
        The updated model instance.

    Raises:
        NotFoundError: If no record with the given ID exists.
        ConflictError: If unique_fields are specified and a duplicate exists.
    """
    instance = get_by_id(db, model_class, id)

    _check_uniqueness(db, model_class, data, unique_fields, exclude_id=id)

    for field, value in data.items():
        setattr(instance, field, value)

    db.commit()
    db.refresh(instance)
    return instance


def delete(
    db: Session,
    model_class: Type,
    id: int,
    check_references: Optional[List[Tuple[Type, str]]] = None,
) -> None:
    """Delete a record by ID.

    Args:
        db: Database session.
        model_class: SQLAlchemy model class to delete from.
        id: Primary key of the record to delete.
        check_references: Optional list of (related_model, fk_field) tuples.
            Before deleting, checks if any related records reference this ID.
            If references exist, raises ConflictError (409).

    Raises:
        NotFoundError: If no record with the given ID exists.
        ConflictError: If check_references finds existing related records.
    """
    instance = get_by_id(db, model_class, id)

    if check_references:
        for related_model, fk_field in check_references:
            ref_count = (
                db.query(func.count(related_model.id))
                .filter(getattr(related_model, fk_field) == id)
                .scalar()
            )
            if ref_count > 0:
                model_name = model_class.__name__
                related_name = related_model.__tablename__
                raise ConflictError(
                    detail=f"Cannot delete {model_name} because it is referenced by existing {related_name} records"
                )

    db.delete(instance)
    db.commit()
