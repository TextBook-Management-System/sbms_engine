
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
   
    print("Testing imports...")
    
    try:
        from app.config import settings
        print("✓ Settings imported successfully")
    except Exception as e:
        print(f"✗ Error importing settings: {e}")
        return False
    
    try:
        from app.database.session import SessionLocal, engine, Base
        print("✓ Database session imported successfully")
    except Exception as e:
        print(f"✗ Error importing database session: {e}")
        return False
    
    try:
        from app.models.database import Book, School, BookInventory
        print("✓ Database models imported successfully")
    except Exception as e:
        print(f"✗ Error importing database models: {e}")
        return False
    
    try:
        from app.models.schemas import BookCreate, SchoolCreate
        print("✓ Schemas imported successfully")
    except Exception as e:
        print(f"✗ Error importing schemas: {e}")
        return False
    
    try:
        from app.services.book_analysis import analyze_uploaded_file
        print("✓ Services imported successfully")
    except ImportError as e:
        print(f"✗ Error importing services: {e}")
        try:
            import app.services.book_analysis as book_analysis
            if hasattr(book_analysis, 'analyze_uploaded_file'):
                print("✓ Services imported successfully (alternative method)")
            else:
                print("✗ analyze_uploaded_file not found in book_analysis module")
                return False
        except Exception as e2:
            print(f"✗ Alternative import also failed: {e2}")
            return False
    
    print("All imports successful!")
    return True


def test_directories():
    print("\nTesting directories...")
    
    required_dirs = [
        "uploads/images",
        "uploads/videos",
        "models",
        "logs"
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✓ Directory exists: {dir_path}")
        else:
            print(f"✗ Directory missing: {dir_path}")
            all_exist = False
    
    return all_exist


def main():
    print("Testing SBMS ENGINE setup...\n")
    
    imports_ok = test_imports()
    dirs_ok = test_directories()
    
    print(f"\nSetup test results:")
    print(f"- Imports: {'✓ PASS' if imports_ok else '✗ FAIL'}")
    print(f"- Directories: {'✓ PASS' if dirs_ok else '✗ FAIL'}")
    
    if imports_ok and dirs_ok:
        print("\n🎉 All tests passed! SBMS ENGINE is ready to run.")
        print("You can now start the server with: uvicorn app.main:app --reload")
        return True
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)