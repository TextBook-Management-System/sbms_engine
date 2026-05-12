
import os
import subprocess
import sys
from pathlib import Path


def create_directories():
    """Create necessary directories"""
    directories = [
        "uploads/images",
        "uploads/videos", 
        "models",
        "logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")


def create_env_file():
    """Create .env file if it doesn't exist"""
    env_file = Path(".env")
    if not env_file.exists():
        env_content = """# Database
DATABASE_URL=sqlite:///./sbms_engine.db

# Security
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ML Models
MODEL_PATH=models/textbook_quality_model.pth
OCR_MODEL_PATH=models/ocr_model

# File Upload
MAX_FILE_SIZE=104857600  # 100MB in bytes

# Geolocation
MAX_DISTANCE_KM=50.0
"""
        env_file.write_text(env_content)
        print("Created .env file with default values")


def install_dependencies():
    """Install Python dependencies"""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])


def initialize_database():
    """Initialize the database"""
    print("Initializing database...")
    try:
        from app.database.session import Base, engine
        # Import all models to register them with SQLAlchemy
        from app.models.database import (
            Book, School, BookInventory, BookAnalysis, DistributionRequest
        )
        Base.metadata.create_all(bind=engine)
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")


def main():
    print("Setting up SBMS ENGINE...")
    
    create_directories()
    create_env_file()
    

    if Path("requirements.txt").exists():
        install_dependencies()
    else:
        print("requirements.txt not found, skipping dependency installation")
    

    initialize_database()
    
    print("\nSBMS ENGINE setup completed!")
    print("To run the application:")
    print("  uvicorn app.main:app --reload")
    print("\nTo access the API:")
    print("  Visit http://localhost:8000/docs for the interactive API documentation")


if __name__ == "__main__":
    main()