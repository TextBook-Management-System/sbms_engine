from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.database.session import get_db
from app.models import schemas, database
from app.services import file_processing
from app.utils.validators import validate_upload_request

router = APIRouter()


@router.post("/", response_model=schemas.FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    school_id: int = None,
    subject: str = None,
    grade_level: str = None,
    db: Session = Depends(get_db)
):
    """Upload image or video file for book analysis"""
    
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Process the uploaded file
    result = await file_processing.process_uploaded_file(
        file=file,
        school_id=school_id,
        subject=subject,
        grade_level=grade_level
    )
    
    return result


@router.post("/book/{book_id}/analyze")
async def analyze_existing_book(
    book_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Analyze existing book with new image/video"""
    
    # Check if book exists
    book = db.query(database.Book).filter(database.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Analyze the file
    analysis_result = await file_processing.analyze_book_file(
        file=file,
        book_id=book_id
    )
    
    return analysis_result