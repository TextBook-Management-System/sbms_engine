from fastapi import HTTPException
from app.models import schemas


def validate_book_data(book: schemas.BookCreate):
    """Validate book data before creation"""
    
    if len(book.title.strip()) < 3:
        raise HTTPException(status_code=400, detail="Book title must be at least 3 characters long")
    
    if not book.subject:
        raise HTTPException(status_code=400, detail="Subject is required")
    
    if not book.grade_level:
        raise HTTPException(status_code=400, detail="Grade level is required")
    
    # Validate ISBN format if provided
    if book.isbn:
        isbn_clean = book.isbn.replace("-", "").replace(" ", "")
        if len(isbn_clean) not in [10, 13]:
            raise HTTPException(status_code=400, detail="Invalid ISBN format")
    
    return True


def validate_school_data(school: schemas.SchoolCreate):
    """Validate school data before creation"""
    
    if len(school.name.strip()) < 2:
        raise HTTPException(status_code=400, detail="School name must be at least 2 characters long")
    
    if len(school.address.strip()) < 5:
        raise HTTPException(status_code=400, detail="Address must be at least 5 characters long")
    
    if len(school.city.strip()) < 2:
        raise HTTPException(status_code=400, detail="City must be at least 2 characters long")
    
    if len(school.state.strip()) < 2:
        raise HTTPException(status_code=400, detail="State must be at least 2 characters long")
    
    if len(school.country.strip()) < 2:
        raise HTTPException(status_code=400, detail="Country must be at least 2 characters long")
    
    # Validate coordinates
    if not (-90 <= school.latitude <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
    
    if not (-180 <= school.longitude <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
    
    return True


def validate_upload_request(upload_req: schemas.UploadFileRequest):
    """Validate upload request data"""
    
    if not upload_req.school_id:
        raise HTTPException(status_code=400, detail="School ID is required")
    
    if not upload_req.subject:
        raise HTTPException(status_code=400, detail="Subject is required")
    
    if not upload_req.grade_level:
        raise HTTPException(status_code=400, detail="Grade level is required")
    
    return True


# Export the functions
__all__ = ['validate_book_data', 'validate_school_data', 'validate_upload_request']