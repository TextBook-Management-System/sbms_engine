

import os
import uuid
from fastapi import UploadFile
from pathlib import Path
from app.config.settings import settings
from app.utils.logger import logger
from app.services import book_analysis


async def process_uploaded_file(
    file: UploadFile,
    school_id: int = None,
    subject: str = None,
    grade_level: str = None,
):
    file_extension = file.filename.split(".")[-1].lower()

    if file_extension in settings.ALLOWED_IMAGE_EXTENSIONS:
        upload_folder = settings.UPLOAD_FOLDER_IMAGES
        file_type = "image"
    elif file_extension in settings.ALLOWED_VIDEO_EXTENSIONS:
        upload_folder = settings.UPLOAD_FOLDER_VIDEOS
        file_type = "video"
    else:
        raise ValueError(f"File type {file_extension} not supported")

    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(upload_folder, unique_filename)

    try:
        Path(upload_folder).mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        response = {
            "filename": unique_filename,
            "file_path": file_path,
            "file_type": file_type,
            "message": f"Successfully uploaded {file_type} file",
        }
        logger.info(f"File uploaded successfully: {file_path}")
        return response

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise


async def analyze_book_copy_file(file: UploadFile, book_copy_id: int):
    analysis_result = await book_analysis.analyze_uploaded_file(
        file=file,
        book_copy_id=book_copy_id,
    )
    return analysis_result


# Keep backward compatibility
async def analyze_book_file(file: UploadFile, book_id: int):
    analysis_result = await book_analysis.analyze_uploaded_file(
        file=file,
        book_copy_id=book_id,
    )
    return analysis_result


__all__ = ["process_uploaded_file", "analyze_book_copy_file", "analyze_book_file"]
