

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database.session import get_db
from app.models.database import BookCopy
from app.services import file_processing
from app.utils.logger import logger

router = APIRouter()


@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    school_id: int = None,
    subject: str = None,
    grade_level: str = None,
    db: Session = Depends(get_db),
):
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    result = await file_processing.process_uploaded_file(
        file=file,
        school_id=school_id,
        subject=subject,
        grade_level=grade_level,
    )
    return result


@router.post("/book-copy/{book_copy_id}/analyze")
async def analyze_book_copy(
    book_copy_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Validate book copy exists
    book_copy = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if not book_copy:
        raise HTTPException(status_code=404, detail=f"Book copy with id {book_copy_id} not found")

    # Read file content
    file_content = await file.read()
    file_extension = file.filename.split(".")[-1].lower()

    # Upload to Firebase Storage
    from app.services.firebase_storage import upload_to_firebase

    firebase_result = await upload_to_firebase(
        file_content=file_content,
        filename=file.filename,
        book_copy_id=book_copy_id,
        file_extension=file_extension,
    )

    # Reset file position for AI analysis
    await file.seek(0)

    # Run AI analysis
    analysis_result = await file_processing.analyze_book_copy_file(
        file=file,
        book_copy_id=book_copy_id,
    )

    # Enrich with book copy context
    analysis_result["book_copy_id"] = book_copy_id
    analysis_result["qr_code"] = book_copy.qr_code
    analysis_result["current_condition"] = book_copy.condition
    analysis_result["book_id"] = book_copy.book_id
    analysis_result["school_id"] = book_copy.school_id

    # Add Firebase URLs
    analysis_result["firebase_path"] = firebase_result.get("firebase_path")
    analysis_result["image_url"] = firebase_result.get("download_url")

    # Optionally update the book copy condition based on AI result
    ai_condition = analysis_result.get("quality_status")
    if ai_condition in ("excellent", "good", "fair", "poor", "unusable"):
        book_copy.condition = ai_condition
        db.commit()
        db.refresh(book_copy)
        analysis_result["condition_updated"] = True
        analysis_result["new_condition"] = ai_condition
        logger.info(
            f"Book copy {book_copy_id} condition updated to '{ai_condition}' based on AI analysis"
        )

    return analysis_result
