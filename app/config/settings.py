from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "SBMS ENGINE - School Book Management System"
    
    # Database Settings
    DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    
    # ML Model Settings
    MODEL_PATH: str = "models/textbook_quality_model.pth"
    OCR_MODEL_PATH: str = "models/ocr_model"
    
    # File Upload Settings
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_IMAGE_EXTENSIONS: set = {"jpg", "jpeg", "png", "bmp", "tiff", "webp"}
    ALLOWED_VIDEO_EXTENSIONS: set = {"mp4", "avi", "mov", "mkv", "wmv"}
    UPLOAD_FOLDER_IMAGES: str = "uploads/images/"
    UPLOAD_FOLDER_VIDEOS: str = "uploads/videos/"
    
    # Security Settings
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Gemini AI Settings
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    
    # Firebase Storage
    FIREBASE_STORAGE_BUCKET: str = "hirepath-2dbd2.firebasestorage.app"
    
    # Geolocation Settings
    MAX_DISTANCE_KM: float = 50.0  # Maximum distance for book transfer suggestions
    
    class Config:
        env_file = ".env"


settings = Settings()