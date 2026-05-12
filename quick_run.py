
from app.main import create_app
import uvicorn

print("Creating SBMS ENGINE app...")
app = create_app()
print("✓ App created successfully!")

# Test importing the service function
try:
    from app.services.book_analysis import analyze_uploaded_file
    print("✓ Service function imported successfully!")
except Exception as e:
    print(f"✗ Service import failed: {e}")

print("\nSBMS ENGINE is ready to run!")