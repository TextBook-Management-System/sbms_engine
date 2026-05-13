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

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


@router.post("", response_model=ScanResponse, status_code=HTTP_201_CREATED)
async def create_scan(
    book_copy_id: int = Form(..., description="ID of the book copy being scanned"),
    scan_image: UploadFile = File(..., description="Scan image (JPEG or PNG, max 10MB)"),
    db: Session = Depends(get_db),
):
    if scan_image.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            detail=f"Invalid image format. Allowed formats: JPEG, PNG. Got: {scan_image.content_type}"
        )

    image_content = await scan_image.read()
    if len(image_content) > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(
            detail=f"Image size exceeds maximum allowed size of 10MB. Got: {len(image_content)} bytes"
        )

    file_extension = "jpg" if scan_image.content_type == "image/jpeg" else "png"

    scan = await scan_service.create_scan(
        db=db,
        book_copy_id=book_copy_id,
        image_data=image_content,
        file_extension=file_extension,
    )

    return scan


@router.get("/{id}", response_model=ScanResponse)
def get_scan(id: int, db: Session = Depends(get_db)):
    return scan_service.get_scan_by_id(db, id)


@router.put("/{id}/verify", response_model=ScanResponse)
def verify_scan(
    id: int,
    payload: ScanVerifyRequest,
    db: Session = Depends(get_db),
):
    return scan_service.verify_scan(db, id, payload.verified_condition.value)


book_copy_scans_router = APIRouter(prefix="/book-copies", tags=["scans"])


@book_copy_scans_router.get(
    "/{book_copy_id}/scans", response_model=PaginatedResponse[ScanResponse]
)
def get_scans_by_book_copy(
    book_copy_id: int,
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    return scan_service.get_scans_by_book_copy(db, book_copy_id, params)
