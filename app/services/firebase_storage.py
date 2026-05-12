

import uuid
from typing import Optional

import httpx

from app.config.settings import settings
from app.utils.logger import logger


# Firebase Storage upload URL template
FIREBASE_UPLOAD_URL = (
    "https://firebasestorage.googleapis.com/v0/b/{bucket}/o?uploadType=media&name={path}"
)

# Firebase Storage download URL template
FIREBASE_DOWNLOAD_URL = (
    "https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{encoded_path}?alt=media&token={token}"
)


def _get_bucket() -> str:
    return getattr(settings, "FIREBASE_STORAGE_BUCKET", "hirepath-2dbd2.firebasestorage.app")


def _get_mime_type(file_extension: str) -> str:
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
        "gif": "image/gif",
        "mp4": "video/mp4",
        "avi": "video/x-msvideo",
        "mov": "video/quicktime",
        "mkv": "video/x-matroska",
    }
    return mime_map.get(file_extension.lower(), "application/octet-stream")


async def upload_to_firebase(
    file_content: bytes,
    filename: str,
    book_copy_id: int,
    file_extension: str,
) -> dict:
    bucket = _get_bucket()
    mime_type = _get_mime_type(file_extension)

    # Generate unique filename to avoid collisions
    unique_id = uuid.uuid4().hex[:12]
    storage_path = f"book_scans/{book_copy_id}/{unique_id}_{filename}"

    # Build upload URL
    upload_url = FIREBASE_UPLOAD_URL.format(bucket=bucket, path=storage_path)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                upload_url,
                content=file_content,
                headers={"Content-Type": mime_type},
            )

        if response.status_code != 200:
            logger.error(
                f"Firebase upload failed ({response.status_code}): {response.text}"
            )
            return {
                "firebase_path": None,
                "download_url": None,
                "error": f"Upload failed: {response.status_code}",
            }

        # Parse response to get the download token
        result = response.json()
        download_token = result.get("downloadTokens", "")

        # Build the public download URL
        encoded_path = storage_path.replace("/", "%2F")
        download_url = FIREBASE_DOWNLOAD_URL.format(
            bucket=bucket,
            encoded_path=encoded_path,
            token=download_token,
        )

        logger.info(f"File uploaded to Firebase: {storage_path}")

        return {
            "firebase_path": storage_path,
            "download_url": download_url,
            "bucket": bucket,
        }

    except httpx.TimeoutException:
        logger.error("Firebase upload timed out")
        return {
            "firebase_path": None,
            "download_url": None,
            "error": "Upload timed out",
        }
    except Exception as e:
        logger.error(f"Firebase upload error: {e}")
        return {
            "firebase_path": None,
            "download_url": None,
            "error": str(e),
        }


__all__ = ["upload_to_firebase"]
