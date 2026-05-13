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

SCAN_ANALYSIS_PROMPT = """You are a school book management expert. Analyze this textbook image and assess its physical condition for a school library system.

Return ONLY a valid JSON object (no markdown fences) with:
{
    "condition": "<one of: excellent, good, fair, poor, unusable>",
    "confidence_score": <float between 0.0 and 1.0>,
    "quality_score": <number 0-100>,
    "issues": ["list of specific physical issues found"],
    "suggestions": ["school-focused actionable suggestions"]
}

For suggestions, focus on school-based decisions:
- Whether the book should be allocated to a learner or held back
- If the school should request a replacement from the department
- Whether the book needs repair before being issued
- If it should be flagged for write-off
- Priority level for the school admin (urgent, soon, monitor)

Scoring guide:
- excellent (90-100): Like new, no visible damage
- good (70-89): Minor wear, fully usable
- fair (50-69): Noticeable wear but still readable
- poor (25-49): Significant damage, difficult to use
- unusable (0-24): Cannot be used for learning
"""

RETURN_COMPARISON_PROMPT = """You are a school book management expert. Compare these two images of the same textbook.

The FIRST image shows the book's condition when it was allocated to a learner.
The SECOND image shows the book's condition now that it is being returned.

Analyze both images and provide a comparison report. Return ONLY a valid JSON object (no markdown fences) with:
{{
    "condition_before": "<one of: excellent, good, fair, poor, unusable>",
    "condition_after": "<one of: excellent, good, fair, poor, unusable>",
    "quality_score_before": <number 0-100>,
    "quality_score_after": <number 0-100>,
    "condition_changed": <true or false>,
    "damage_detected": <true or false>,
    "new_issues": ["list of NEW damage or issues not present in the first image"],
    "comparison_summary": "brief summary of condition change",
    "suggestions": ["school-focused suggestions based on the comparison"],
    "charge_learner": <true or false - whether the learner should be charged for damage>
}}

For suggestions, focus on:
- Whether the book is still usable for the next learner
- If new damage warrants a replacement request
- Whether the learner should be held responsible for damage
- Action items for the school admin
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
            "maxOutputTokens": 4096,
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
        if text_content.startswith("```json"):
            text_content = text_content[7:]
        elif text_content.startswith("```"):
            text_content = text_content.split("\n", 1)[1] if "\n" in text_content else text_content[3:]
        if text_content.endswith("```"):
            text_content = text_content[:-3]
        text_content = text_content.strip()

        # Try to extract JSON object if there's extra text around it
        if not text_content.startswith("{"):
            start = text_content.find("{")
            if start != -1:
                text_content = text_content[start:]
        if not text_content.endswith("}"):
            end = text_content.rfind("}")
            if end != -1:
                text_content = text_content[:end + 1]

        try:
            analysis = json.loads(text_content)
        except json.JSONDecodeError:
            # Fallback: return safe defaults if parsing fails
            logger.warning(f"Could not parse Gemini response, using defaults. Raw: {text_content[:200]}")
            analysis = {
                "condition": "fair",
                "confidence_score": 0.5,
                "quality_score": 50,
                "issues": ["AI response could not be parsed"],
                "suggestions": ["Manual review recommended"],
            }

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
    image_data: bytes,
    file_extension: str = "jpg",
    scan_image_path: str = None,
) -> BookConditionScan:
    """Create a new book condition scan using Gemini AI + Firebase.

    Works entirely in-memory — no local disk writes needed (Vercel compatible).
    """
    book_copy = db.query(BookCopy).filter(BookCopy.id == book_copy_id).first()
    if book_copy is None:
        raise NotFoundError(detail=f"Book copy with id {book_copy_id} not found")

    active_model = get_active_model(db)

    firebase_result = await upload_to_firebase(
        file_content=image_data,
        filename=f"scan_{book_copy_id}.{file_extension}",
        book_copy_id=book_copy_id,
        file_extension=file_extension,
    )
    firebase_url = firebase_result.get("download_url") or ""

    try:
        result = await _invoke_gemini_analysis(image_data, file_extension)
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
        ai_quality_score=result.get("quality_score"),
        scan_image_path=firebase_url,
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


async def _invoke_gemini_comparison(
    before_image_data: bytes,
    before_extension: str,
    after_image_data: bytes,
    after_extension: str,
) -> dict:
    """Compare two book images using Gemini Vision API."""
    if not settings.GEMINI_API_KEY:
        raise AIModelInvocationError("GEMINI_API_KEY not configured")

    before_base64 = base64.b64encode(before_image_data).decode("utf-8")
    after_base64 = base64.b64encode(after_image_data).decode("utf-8")

    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
    before_mime = mime_map.get(before_extension, "image/jpeg")
    after_mime = mime_map.get(after_extension, "image/jpeg")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": RETURN_COMPARISON_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": before_mime,
                            "data": before_base64,
                        }
                    },
                    {
                        "inline_data": {
                            "mime_type": after_mime,
                            "data": after_base64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            logger.error(f"Gemini comparison API error {response.status_code}: {response.text}")
            raise AIModelInvocationError(f"Gemini API error: {response.status_code}")

        result = response.json()
        text_content = result["candidates"][0]["content"]["parts"][0]["text"]

        text_content = text_content.strip()
        if text_content.startswith("```json"):
            text_content = text_content[7:]
        elif text_content.startswith("```"):
            text_content = text_content.split("\n", 1)[1] if "\n" in text_content else text_content[3:]
        if text_content.endswith("```"):
            text_content = text_content[:-3]
        text_content = text_content.strip()

        if not text_content.startswith("{"):
            start = text_content.find("{")
            if start != -1:
                text_content = text_content[start:]
        if not text_content.endswith("}"):
            end = text_content.rfind("}")
            if end != -1:
                text_content = text_content[:end + 1]

        try:
            comparison = json.loads(text_content)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse Gemini comparison response. Raw: {text_content[:200]}")
            comparison = {
                "condition_before": "unknown",
                "condition_after": "unknown",
                "quality_score_before": 0,
                "quality_score_after": 0,
                "condition_changed": False,
                "damage_detected": False,
                "new_issues": ["AI comparison could not be parsed"],
                "comparison_summary": "Unable to compare - manual review needed",
                "suggestions": ["Manual inspection recommended"],
                "charge_learner": False,
            }

        return comparison

    except httpx.TimeoutException:
        logger.error("Gemini API timed out during comparison")
        raise AIModelInvocationError("AI service timed out")
    except AIModelInvocationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during comparison: {e}")
        raise AIModelInvocationError(str(e))


async def create_return_scan(
    db: Session,
    allocation_id: int,
    return_image_data: bytes,
    file_extension: str = "jpg",
) -> dict:
    """Create a return scan that compares the current book condition with the allocation image.

    Fetches the original allocation image URL, downloads it, then sends both images
    to Gemini for comparison.
    """
    from app.models.database import BookAllocation

    allocation = db.query(BookAllocation).filter(BookAllocation.id == allocation_id).first()
    if allocation is None:
        raise NotFoundError(detail=f"Allocation with id {allocation_id} not found")

    if not allocation.scan_image_url:
        raise ValidationError(detail="No allocation image found to compare against")

    # Upload return image to Firebase
    firebase_result = await upload_to_firebase(
        file_content=return_image_data,
        filename=f"return_{allocation.book_copy_id}.{file_extension}",
        book_copy_id=allocation.book_copy_id,
        file_extension=file_extension,
    )
    return_image_url = firebase_result.get("download_url") or ""

    # Download the original allocation image
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(allocation.scan_image_url)
        if resp.status_code != 200:
            raise ValidationError(detail="Could not download original allocation image for comparison")
        before_image_data = resp.content
    except httpx.TimeoutException:
        raise APIError(status_code=502, detail="Timed out downloading allocation image", error_type="server_error")
    except Exception as e:
        raise APIError(status_code=502, detail=f"Error fetching allocation image: {e}", error_type="server_error")

    # Determine extension of original image
    before_ext = "jpg"
    if allocation.scan_image_url.lower().endswith(".png"):
        before_ext = "png"

    # Run AI comparison
    try:
        comparison = await _invoke_gemini_comparison(
            before_image_data=before_image_data,
            before_extension=before_ext,
            after_image_data=return_image_data,
            after_extension=file_extension,
        )
    except AIModelInvocationError as exc:
        raise APIError(
            status_code=502,
            detail="AI comparison service unavailable. Please try again later.",
            error_type="server_error",
        ) from exc

    # Build response
    comparison["allocation_id"] = allocation_id
    comparison["book_copy_id"] = allocation.book_copy_id
    comparison["learner_id"] = allocation.learner_id
    comparison["allocation_image_url"] = allocation.scan_image_url
    comparison["return_image_url"] = return_image_url

    logger.info(
        f"Return scan comparison for allocation {allocation_id}: "
        f"changed={comparison.get('condition_changed')}, damage={comparison.get('damage_detected')}"
    )

    return comparison
