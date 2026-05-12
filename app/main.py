from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1.router import api_router
from app.config.settings import settings
from app.core.middleware import add_middleware
from app.core.exceptions import register_exception_handlers
import uvicorn
import logging
import os
from pathlib import Path

# Only create upload directories if NOT running on Vercel
if not os.environ.get("VERCEL"):
    Path(settings.UPLOAD_FOLDER_IMAGES).mkdir(parents=True, exist_ok=True)
    Path(settings.UPLOAD_FOLDER_VIDEOS).mkdir(parents=True, exist_ok=True)

def create_app():
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="SBMS ENGINE - AI-powered School Book Management System for analyzing textbook quality and optimizing book distribution between schools"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register global exception handlers
    register_exception_handlers(app)
    
    # Mount static files safely
    # Check if directory exists before mounting to avoid startup errors on Vercel
    if os.path.exists("uploads"):
        app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    
    # Include API routers
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    @app.get("/")
    async def root():
        return {
            "message": "SBMS ENGINE - School Book Management System API is running!",
            "version": "1.0.0",
            "endpoints": f"{settings.API_V1_STR}/docs"
        }
    
    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )