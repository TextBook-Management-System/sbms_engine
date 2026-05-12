"""
Scan service for AI-powered book condition scanning.

Handles scan creation (with AI model invocation), retrieval, listing by book copy,
and human verification of scan results.

The AI model invocation is a mock/stub that returns a random condition and confidence
score. The actual AI integration is external and will be implemented separately.

Validates: Requirements 15.1–15.8
"""

import random
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import APIError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.models.database import AIModelVersion, BookConditionScan, BookCopy


# Valid condition values for AI model output
VALID_CONDITIONS = ["excellent", "good", "fair", "poor", "unusable"]


class AIModelInvocationError(Exception):
    """Raised when the AI model invocation fails."""

    pass


def _invoke_ai_model(model: AIModelVersion, image_path: str) -> dict:
    """Mock/stub AI model invocation.

    In production, this would call an external AI service. For now, it returns
    a random condition and confidence score to simulate the AI model behavior.

    Args:
        model: The active AI model version to use.
        image_path: Path to the scan image file.

    Returns:
        Dictionary with 'condition' and 'confidence_score' keys.

    Raises:
        AIModelInvocationError: If the model invocation fails.
    """
    # Simulate AI model response with random condition and confidence
    condition = random.choice(VALID_CONDITIONS)
    confidence_score = round(random.uniform(0.5, 1.0), 4)

    return {
        "condition": condition,
        "confidence_score": confidence_score,
    }


def get_active_model(db: Session) -> AIModelVersion:
    """Get the currently active AI model.

    Args:
        db: Database session.

    Returns:
        The active AIModelVersion instance.

    Raises:
        ValidationError: If no active AI model is registered (422).
    """
    active_model = (
        db.query(AIModelVersion)
        .filter(AIModelVersion.is_active == True)  # noqa: E712
        .first()
    )
    if active_model is None:
        raise ValidationError(
            detail="No active AI model is available. Please activate a model before scanning."
        )
    return active_model


def create_scan(
    db: Session,
    book_copy_id: int,
    scan_image_path: str,
) -> BookConditionScan:
    """Create a new book condition scan by invoking the active AI model.

    Args:
        db: Database session.
        book_copy_id: ID of the book copy being scanned.
        scan_image_path: Path to the uploaded scan image.

    Returns:
        The newly created BookConditionScan instance.

    Raises:
        NotFoundError: If the book_copy_id does not exist (404).
        ValidationError: If no active AI model is registered (422).
        APIError: If the AI model invocation fails (502).
    """
    # Validate book copy exists
    book_copy = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if book_copy is None:
        raise NotFoundError(detail=f"Book copy with id {book_copy_id} not found")

    # Get active AI model
    active_model = get_active_model(db)

    # Invoke AI model
    try:
        result = _invoke_ai_model(active_model, scan_image_path)
    except AIModelInvocationError as exc:
        raise APIError(
            status_code=502,
            detail="AI model service is unavailable. Please try again later.",
            error_type="server_error",
        ) from exc

    # Create scan record
    scan = BookConditionScan(
        book_copy_id=book_copy_id,
        ai_model_id=active_model.id,
        condition=result["condition"],
        confidence_score=result["confidence_score"],
        scan_image_path=scan_image_path,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


def get_scan_by_id(db: Session, scan_id: int) -> BookConditionScan:
    """Get a scan record by its ID.

    Args:
        db: Database session.
        scan_id: Primary key of the scan.

    Returns:
        The BookConditionScan instance.

    Raises:
        NotFoundError: If no scan with the given ID exists (404).
    """
    scan = db.query(BookConditionScan).filter(BookConditionScan.id == scan_id).first()
    if scan is None:
        raise NotFoundError(detail=f"Scan with id {scan_id} not found")
    return scan


def get_scans_by_book_copy(
    db: Session,
    book_copy_id: int,
    params: PaginationParams,
) -> PaginatedResponse:
    """Get a paginated list of scans for a specific book copy, ordered by scan date descending.

    Args:
        db: Database session.
        book_copy_id: ID of the book copy.
        params: Pagination parameters.

    Returns:
        PaginatedResponse with scan records.

    Raises:
        NotFoundError: If the book_copy_id does not exist (404).
    """
    # Validate book copy exists
    book_copy = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if book_copy is None:
        raise NotFoundError(detail=f"Book copy with id {book_copy_id} not found")

    query = (
        db.query(BookConditionScan)
        .filter(BookConditionScan.book_copy_id == book_copy_id)
        .order_by(BookConditionScan.scanned_at.desc())
    )
    return paginate(query, params)


def verify_scan(
    db: Session,
    scan_id: int,
    verified_condition: str,
) -> BookConditionScan:
    """Update a scan with a human-verified condition.

    Args:
        db: Database session.
        scan_id: Primary key of the scan to verify.
        verified_condition: The human-assessed condition value.

    Returns:
        The updated BookConditionScan instance.

    Raises:
        NotFoundError: If no scan with the given ID exists (404).
    """
    scan = get_scan_by_id(db, scan_id)
    scan.verified_condition = verified_condition
    db.commit()
    db.refresh(scan)
    return scan
