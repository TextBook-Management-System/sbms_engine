"""
Scan service for AI-powered book condition scanning.

Uses Google Gemini Vision API for actual book condition analysis
and Firebase Storage for image persistence.

Validates: Requirements 15.1–15.8
"""

import base64
import json
import uuid
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.exceptions import APIError, NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.models.database import AIModelVersion, BookConditionScan, BookCopy
from app.services.firebase_storage import upload_to_firebase
from app.utils.logger import logger


VALID_CONDITIONS = ["excellent", "good", "fair", "poor", "unusable"]

SCAN_ANALYSIS_PROMPT = """Analyze this book image and assess its physical condition.

Return ONLY a valid JSON object (no markdown fences) with:
{
    "condition": "<one of: excellent, good, fair, poor, unusable>",
    "confidence_score": <float between 0.0 and 1.0>,
    "quality_score": <number 0-100>,
    "issues": ["list of issues found"],
    "suggestions": ["list of actionable suggestions for the book's use or replacement"]
}

Scoring guide:
- excellent (90-100): Like new, no visible damage
- good (70-89): Minor wear, fully usable
- fair (50-69): Noticeable wear but still readable
- poor (25-49): Significant damage, difficult to use
- unusable (0-24): Cannot be used for learning
"""


class AIModelInvocationError(Exception):
    pass


async def _invoke_gemini_analysis(image_data: bytes, file_extension: str) -> dict:
    """Invoke Gemini Vision API for book condition analysis."""
    if not settings.GEMINI_API_KEY:
        raise AIModelInvocationError("GEMINI_API_KEY not configured")

    image_base64 = base64.b64encode(image_data).decode("utf-8")

    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }
    mime_type = mime_map.get(file_extension, "image/jpeg")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": SCAN_ANALYSIS_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": image_base64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            logger.error(f"Gemini API error {response.status_code}: {response.text}")
            raise AIModelInvocationError(f"Gemini API error: {response.status_code}")

        result = response.json()
        text_content = result["candidates"][0]["content"]["parts"][0]["text"]

        text_content = text_content.strip()
        if text_content.startswith("```"):
            text_content = text_content.split("\n", 1)[1]
        if text_content.endswith("```"):
            text_content = text_content.rsplit("```", 1)[0]
        text_content = text_content.strip()

        analysis = json.loads(text_content)

        condition = analysis.get("condition", "fair")
        if condition not in VALID_CONDITIONS:
            condition = "fair"

        confidence = analysis.get("confidence_score", 0.7)
        if not isinstance(confidence, (int, float)):
            confidence = 0.7
        confidence = max(0.0, min(1.0, float(confidence)))

        return {
            "condition": condition,
            "confidence_score": round(confidence, 4),
            "quality_score": analysis.get("quality_score", 50),
            "issues": analysis.get("issues", []),
            "suggestions": analysis.get("suggestions", []),
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini scan response: {e}")
        raise AIModelInvocationError("Failed to parse AI response")
    except httpx.TimeoutException:
        logger.error("Gemini API timed out during scan")
        raise AIModelInvocationError("AI service timed out")
    except AIModelInvocationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during scan analysis: {e}")
        raise AIModelInvocationError(str(e))


def get_active_model(db: Session) -> AIModelVersion:
    active_model = (
        db.query(AIModelVersion)
        .filter(AIModelVersion.is_active == True)  # noqa: E712
        .first()
    )
    if active_model is None:
        raise ValidationError(
            detail="No active AI model is available. Please activate a model before scanning."
        )
    return active_model


async def create_scan(
    db: Session,
    book_copy_id: int,
    scan_image_path: str,
    image_data: bytes = None,
    file_extension: str = "jpg",
) -> BookConditionScan:
    """Create a new book condition scan using Gemini AI + Firebase.

    If image_data is provided, uploads to Firebase and runs Gemini analysis.
    Otherwise falls back to reading from scan_image_path.
    """
    book_copy = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if book_copy is None:
        raise NotFoundError(detail=f"Book copy with id {book_copy_id} not found")

    active_model = get_active_model(db)

    firebase_url = None

    if image_data:
        firebase_result = await upload_to_firebase(
            file_content=image_data,
            filename=f"scan_{book_copy_id}.{file_extension}",
            book_copy_id=book_copy_id,
            file_extension=file_extension,
        )
        firebase_url = firebase_result.get("download_url")

        try:
            result = await _invoke_gemini_analysis(image_data, file_extension)
        except AIModelInvocationError as exc:
            raise APIError(
                status_code=502,
                detail="AI model service is unavailable. Please try again later.",
                error_type="server_error",
            ) from exc
    else:
        with open(scan_image_path, "rb") as f:
            file_data = f.read()

        ext = scan_image_path.rsplit(".", 1)[-1] if "." in scan_image_path else "jpg"

        firebase_result = await upload_to_firebase(
            file_content=file_data,
            filename=f"scan_{book_copy_id}.{ext}",
            book_copy_id=book_copy_id,
            file_extension=ext,
        )
        firebase_url = firebase_result.get("download_url")

        try:
            result = await _invoke_gemini_analysis(file_data, ext)
        except AIModelInvocationError as exc:
            raise APIError(
                status_code=502,
                detail="AI model service is unavailable. Please try again later.",
                error_type="server_error",
            ) from exc

    import json as _json

    issues_str = _json.dumps(result.get("issues", [])) if result.get("issues") else None
    suggestions_str = _json.dumps(result.get("suggestions", [])) if result.get("suggestions") else None

    scan = BookConditionScan(
        book_copy_id=book_copy_id,
        ai_model_id=active_model.id,
        condition=result["condition"],
        confidence_score=result["confidence_score"],
        ai_issues=issues_str,
        ai_suggestions=suggestions_str,
        scan_image_path=firebase_url or scan_image_path,
    )
    db.add(scan)

    if result["condition"] in VALID_CONDITIONS:
        book_copy.condition = result["condition"]

    db.commit()
    db.refresh(scan)

    logger.info(
        f"Scan created for book_copy {book_copy_id}: condition={result['condition']}, "
        f"confidence={result['confidence_score']}"
    )
    return scan


def get_scan_by_id(db: Session, scan_id: int) -> BookConditionScan:
    scan = db.query(BookConditionScan).filter(BookConditionScan.id == scan_id).first()
    if scan is None:
        raise NotFoundError(detail=f"Scan with id {scan_id} not found")
    return scan


def get_scans_by_book_copy(
    db: Session,
    book_copy_id: int,
    params: PaginationParams,
) -> PaginatedResponse:
    book_copy = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if book_copy is None:
        raise NotFoundError(detail=f"Book copy with id {book_copy_id} not found")

    query = (
        db.query(BookConditionScan)
        .filter(BookConditionScan.book_copy_id == book_copy_id)
        .order_by(BookConditionScan.scanned_at.desc())
    )
    return paginate(query, params)


def verify_scan(
    db: Session,
    scan_id: int,
    verified_condition: str,
) -> BookConditionScan:
    scan = get_scan_by_id(db, scan_id)
    scan.verified_condition = verified_condition
    db.commit()
    db.refresh(scan)
    return scan
