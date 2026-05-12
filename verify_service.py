
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from app.services.book_analysis import analyze_uploaded_file, perform_ml_analysis
    print("✅ analyze_uploaded_file function exists")
    print("✅ perform_ml_analysis function exists")
    

    print(f"✅ analyze_uploaded_file is callable: {callable(analyze_uploaded_file)}")
    print(f"✅ perform_ml_analysis is callable: {callable(perform_ml_analysis)}")
    
except ImportError as e:
    print(f"❌ Import error: {e}")

    try:
        import app.services.book_analysis as ba
        print(f"Module contents: {dir(ba)}")
    except Exception as e2:
        print(f"Could not inspect module: {e2}")