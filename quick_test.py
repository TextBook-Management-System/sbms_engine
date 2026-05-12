
import ast
import os
from pathlib import Path


def check_python_syntax(file_path):
    """Check if Python file has valid syntax"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def test_files():
    """Test all Python files for syntax errors"""
    files_to_check = [
        'app/models/schemas.py',
        'app/models/database.py',
        'app/config/settings.py',
        'app/database/session.py',
        'app/main.py',
        'app/api/v1/router.py',
        'app/api/v1/endpoints/books.py',
        'app/api/v1/endpoints/schools.py',
        'app/services/book_analysis.py'
    ]
    
    all_good = True
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            is_valid, error = check_python_syntax(file_path)
            if is_valid:
                print(f"✓ {file_path} - Syntax OK")
            else:
                print(f"✗ {file_path} - Syntax Error: {error}")
                all_good = False
        else:
            print(f"✗ {file_path} - File does not exist")
            all_good = False
    
    return all_good


if __name__ == "__main__":
    print("Checking Python syntax in all files...")
    success = test_files()
    
    if success:
        print("\n✅ All files have valid Python syntax!")
        print("Now testing imports...")
        
        # Test basic imports
        try:
            from app.models import schemas
            print("✓ Schemas module imports successfully")
        except ImportError as e:
            print(f"✗ Schemas import failed: {e}")
        
        try:
            from app.models import database
            print("✓ Database module imports successfully")
        except ImportError as e:
            print(f"✗ Database import failed: {e}")
            
    else:
        print("\n❌ Some files have syntax errors. Please fix them before proceeding.")