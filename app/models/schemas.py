from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum as PyEnum


class BookQualityStatus(str, PyEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNUSABLE = "unusable"


class GradeLevel(str, PyEnum):
    GRADE_1 = "grade_1"
    GRADE_2 = "grade_2"
    GRADE_3 = "grade_3"
    GRADE_4 = "grade_4"
    GRADE_5 = "grade_5"
    GRADE_6 = "grade_6"
    GRADE_7 = "grade_7"
    GRADE_8 = "grade_8"
    GRADE_9 = "grade_9"
    GRADE_10 = "grade_10"
    GRADE_11 = "grade_11"
    GRADE_12 = "grade_12"


class Subject(str, PyEnum):
    MATHEMATICS = "mathematics"
    ENGLISH = "english"
    SCIENCE = "science"
    SOCIAL_STUDIES = "social_studies"
    ART = "art"
    MUSIC = "music"
    PHYSICAL_EDUCATION = "physical_education"
    HISTORY = "history"
    GEOGRAPHY = "geography"
    BIOLOGY = "biology"
    CHEMISTRY = "chemistry"
    PHYSICS = "physics"
    LITERATURE = "literature"
    FOREIGN_LANGUAGE = "foreign_language"


class BookBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    subject: Subject
    grade_level: GradeLevel
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    author: Optional[str] = None
    edition: Optional[str] = None


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = None
    subject: Optional[Subject] = None
    grade_level: Optional[GradeLevel] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    author: Optional[str] = None
    edition: Optional[str] = None


class Book(BookBase):
    id: int
    quality_score: Optional[float] = None
    quality_status: Optional[BookQualityStatus] = None
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    analysis_result: Optional[str] = None
    pages_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SchoolBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    address: str = Field(..., min_length=1, max_length=500)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=1, max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    total_students: Optional[int] = 0
    total_teachers: Optional[int] = 0


class SchoolCreate(SchoolBase):
    pass


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    total_students: Optional[int] = None
    total_teachers: Optional[int] = None


class School(SchoolBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BookInventoryBase(BaseModel):
    school_id: int
    book_id: int
    quantity: int = Field(..., ge=0)
    condition_notes: Optional[str] = None


class BookInventoryCreate(BookInventoryBase):
    pass


class BookInventoryUpdate(BaseModel):
    quantity: Optional[int] = Field(None, ge=0)
    condition_notes: Optional[str] = None


class BookInventory(BookInventoryBase):
    id: int
    subject: Subject
    grade_level: GradeLevel
    last_updated: datetime
    
    class Config:
        from_attributes = True


class AnalysisResult(BaseModel):
    quality_score: float = Field(..., ge=0, le=100)
    quality_status: BookQualityStatus
    issues_found: List[str]
    suggestions: List[str]
    readability_score: Optional[float] = None
    completeness_score: Optional[float] = None
    extracted_text_preview: Optional[str] = None
    page_count: Optional[int] = None


class FileUploadResponse(BaseModel):
    filename: str
    file_path: str
    file_type: str  # 'image' or 'video'
    message: str
    book_id: Optional[int] = None


class DistributionSuggestion(BaseModel):
    source_school: School
    destination_school: School
    book_subject: Subject
    grade_level: GradeLevel
    quantity_to_transfer: int
    distance_km: float
    estimated_delivery_days: int
    cost_estimate: Optional[float] = None


class DistributionRequestBase(BaseModel):
    source_school_id: int
    destination_school_id: int
    book_subject: Subject
    grade_level: GradeLevel
    requested_quantity: int


class DistributionRequestCreate(DistributionRequestBase):
    pass


class DistributionRequest(DistributionRequestBase):
    id: int
    approved_quantity: int
    status: str
    reason: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SchoolBookShortage(BaseModel):
    school: School
    subject: Subject
    grade_level: GradeLevel
    current_stock: int
    required_stock: int
    shortage: int


class UploadFileRequest(BaseModel):
    school_id: int
    subject: Subject
    grade_level: GradeLevel
    book_title: Optional[str] = None
    book_author: Optional[str] = None
    book_publisher: Optional[str] = None