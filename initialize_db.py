
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))

from app.database.session import Base, engine
from app.models.database import Book, School, BookInventory, BookAnalysis, DistributionRequest
from app.utils.logger import logger


def initialize_database():
    """Initialize the database by creating all tables"""
    print("Initializing SBMS ENGINE database...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        
        # Log the operation
        logger.info("Database initialized successfully with all tables")
        
        # Show what tables were created
        tables = Base.metadata.tables.keys()
        print(f"📋 Created tables: {list(tables)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        logger.error(f"Database initialization failed: {e}")
        return False


def main():
    print("🚀 SBMS ENGINE - Database Initialization Script")
    print("=" * 50)
    
    success = initialize_database()
    
    if success:
        print("\n🎉 Database initialization completed successfully!")
        print("You can now start the SBMS ENGINE server.")
        print("Use: python -m uvicorn app.main:app --reload")
    else:
        print("\n❌ Database initialization failed!")
        print("Please check the error messages above and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()