"""Book condition scans endpoints.

Provides endpoints for AI-powered book condition scanning:
- POST create scan (with image upload)
- GET scan by ID
- GET scans by book_copy_id (paginated, ordered by scan date desc)
- PUT verify scan with human-assessed condition

Validates: Requirements 15.1–15.8
"""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from app.core.exceptions import APIError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams
from app.database.session import get_db
from app.schemas.scans import ScanResponse, ScanVerifyRequest
from app.services import scan_service

router = APIRouter(prefix="/scans", tags=["scans"])

# Maximum allowed image size: 10 MB
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Allowed image content types
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}

# Directory for storing scan images
SCAN_IMAGES_DIR = os.path.join("uploads", "scans")


def _ensure_upload_dir() -> None:
    """Ensure the scan images upload directory exists."""
    os.makedirs(SCAN_IMAGES_DIR, exist_ok=True)


@router.post("", response_model=ScanResponse, status_code=HTTP_201_CREATED)
async def create_scan(
    book_copy_id: int = Form(..., description="ID of the book copy being scanned"),
    scan_image: UploadFile = File(..., description="Scan image (JPEG or PNG, max 10MB)"),
    db: Session = Depends(get_db),
):
    """Create a new book condition scan.

    Accepts a book_copy_id and a scan image (JPEG/PNG, max 10MB).
    Invokes the active AI model to assess the book condition.
    Returns the scan result with condition and confidence_score.

    - 404 if book_copy_id does not exist
    - 422 if no active AI model is registered
    - 422 if image format is invalid or exceeds size limit
    - 502 if AI model invocation fails

    Validates: Requirements 15.1, 15.5, 15.6, 15.8
    """
    # Validate image content type
    if scan_image.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            detail=f"Invalid image format. Allowed formats: JPEG, PNG. Got: {scan_image.content_type}"
        )

    # Read image content and validate size
    image_content = await scan_image.read()
    if len(image_content) > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(
            detail=f"Image size exceeds maximum allowed size of 10MB. Got: {len(image_content)} bytes"
        )

    # Save image to disk
    _ensure_upload_dir()
    file_extension = "jpg" if scan_image.content_type == "image/jpeg" else "png"
    filename = f"{uuid.uuid4().hex}.{file_extension}"
    image_path = os.path.join(SCAN_IMAGES_DIR, filename)

    with open(image_path, "wb") as f:
        f.write(image_content)

    # Create scan via service (handles validation, AI invocation, and persistence)
    try:
        scan = scan_service.create_scan(
            db=db,
            book_copy_id=book_copy_id,
            scan_image_path=image_path,
        )
    except Exception:
        # Clean up the saved image if scan creation fails
        if os.path.exists(image_path):
            os.remove(image_path)
        raise

    return scan


@router.get("/{id}", response_model=ScanResponse)
def get_scan(id: int, db: Session = Depends(get_db)):
    """Get a scan record by ID.

    Returns 404 if the scan does not exist.

    Validates: Requirements 15.2, 15.7
    """
    return scan_service.get_scan_by_id(db, id)


@router.put("/{id}/verify", response_model=ScanResponse)
def verify_scan(
    id: int,
    payload: ScanVerifyRequest,
    db: Session = Depends(get_db),
):
    """Verify a scan with a human-assessed condition.

    The verified_condition must be one of: excellent, good, fair, poor, unusable.
    Returns 404 if the scan does not exist.
    Returns 422 if the condition value is invalid (handled by Pydantic enum validation).

    Validates: Requirements 15.4, 15.7
    """
    return scan_service.verify_scan(db, id, payload.verified_condition.value)


# --- Book copy scans sub-endpoint ---
# This is registered separately to handle the /book-copies/{book_copy_id}/scans path

book_copy_scans_router = APIRouter(prefix="/book-copies", tags=["scans"])


@book_copy_scans_router.get(
    "/{book_copy_id}/scans", response_model=PaginatedResponse[ScanResponse]
)
def get_scans_by_book_copy(
    book_copy_id: int,
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """Get a paginated list of scans for a specific book copy.

    Results are ordered by scan date descending (most recent first).
    Returns 404 if the book_copy_id does not exist.

    Validates: Requirements 15.3, 15.5
    """
    return scan_service.get_scans_by_book_copy(db, book_copy_id, params)
