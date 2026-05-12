"""
Book Quality Analysis Service using Google Gemini Vision API.

Analyzes uploaded book images for:
- Physical condition (damage, wear, torn pages, water damage)
- Cover quality
- Page readability
- Overall quality scoring (0-100)
"""

import asyncio
import base64
import json
import httpx
from fastapi import UploadFile
import os
from pathlib import Path
from app.config.settings import settings
from app.utils.logger import logger
from typing import Dict, Any, Optional


QUALITY_ANALYSIS_PROMPT = """You are a book quality assessment expert. Analyze this image of a school textbook and provide a detailed quality assessment.

Evaluate the following aspects:
1. **Physical Condition**: Look for tears, creases, bent corners, spine damage, water damage, stains, writing/marks
2. **Cover Quality**: Is the cover intact? Any peeling, fading, or damage?
3. **Page Readability**: Can text be clearly read? Any blurriness, fading, or obstruction?
4. **Binding**: Is the book still well-bound? Any loose pages visible?
5. **Overall Usability**: Can a student still use this book effectively for learning?

Respond ONLY with a valid JSON object (no markdown, no code fences) in this exact format:
{
    "quality_score": <number 0-100>,
    "quality_status": "<one of: excellent, good, fair, poor, unusable>",
    "physical_condition": {
        "score": <number 0-100>,
        "issues": ["list of specific issues found"]
    },
    "cover_quality": {
        "score": <number 0-100>,
        "issues": ["list of specific issues found"]
    },
    "page_readability": {
        "score": <number 0-100>,
        "issues": ["list of specific issues found"]
    },
    "binding_condition": {
        "score": <number 0-100>,
        "issues": ["list of specific issues found"]
    },
    "issues_found": ["summary list of all major issues"],
    "suggestions": ["actionable suggestions for the book's use or replacement"],
    "usability_verdict": "<brief statement on whether students can still use this book>"
}

Scoring guide:
- 90-100: Excellent - Like new, no visible damage
- 70-89: Good - Minor wear, fully usable
- 50-69: Fair - Noticeable wear but still readable
- 25-49: Poor - Significant damage, difficult to use
- 0-24: Unusable - Cannot be used for learning
"""


async def analyze_uploaded_file(file: UploadFile, book_copy_id: int) -> Dict[str, Any]:
    """Analyze uploaded image/video file for book quality assessment.

    Args:
        file: The uploaded image or video file.
        book_copy_id: The ID of the specific book copy being analyzed.
    """

    file_extension = file.filename.split('.')[-1].lower()

    if file_extension in settings.ALLOWED_IMAGE_EXTENSIONS:
        upload_folder = settings.UPLOAD_FOLDER_IMAGES
        file_type = "image"
    elif file_extension in settings.ALLOWED_VIDEO_EXTENSIONS:
        upload_folder = settings.UPLOAD_FOLDER_VIDEOS
        file_type = "video"
    else:
        raise ValueError(f"File type '{file_extension}' not supported")

    # Create unique filename using book_copy_id
    filename = f"book_copy_{book_copy_id}_{file.filename}"
    file_path = os.path.join(upload_folder, filename)

    # Read file content
    file_content = await file.read()

    # Save file to disk
    try:
        Path(upload_folder).mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        raise

    # Perform AI analysis
    if file_type == "image":
        analysis_result = await analyze_book_image(file_content, file_extension)
    else:
        # For video, extract a frame and analyze it
        analysis_result = await analyze_book_video(file_path)

    # Add metadata
    analysis_result["file_path"] = file_path
    analysis_result["file_type"] = file_type
    analysis_result["book_copy_id"] = book_copy_id

    return analysis_result


async def analyze_book_image(
    image_data: bytes, file_extension: str
) -> Dict[str, Any]:
    """Analyze a book image using Google Gemini Vision API."""

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, returning placeholder analysis")
        return _placeholder_analysis()

    # Encode image to base64
    image_base64 = base64.b64encode(image_data).decode("utf-8")

    # Map extension to MIME type
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
    }
    mime_type = mime_map.get(file_extension, "image/jpeg")

    # Build Gemini API request
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": QUALITY_ANALYSIS_PROMPT},
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
            "maxOutputTokens": 2048,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            logger.error(
                f"Gemini API error {response.status_code}: {response.text}"
            )
            return _placeholder_analysis(
                error=f"API error: {response.status_code}"
            )

        # Parse response
        result = response.json()
        text_content = (
            result["candidates"][0]["content"]["parts"][0]["text"]
        )

        # Clean up response (remove markdown fences if present)
        text_content = text_content.strip()
        if text_content.startswith("```"):
            text_content = text_content.split("\n", 1)[1]
        if text_content.endswith("```"):
            text_content = text_content.rsplit("```", 1)[0]
        text_content = text_content.strip()

        analysis = json.loads(text_content)

        logger.info(
            f"Gemini analysis complete - quality_score: {analysis.get('quality_score')}"
        )
        return analysis

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        return _placeholder_analysis(error="Failed to parse AI response")
    except httpx.TimeoutException:
        logger.error("Gemini API request timed out")
        return _placeholder_analysis(error="AI analysis timed out")
    except Exception as e:
        logger.error(f"Unexpected error during Gemini analysis: {e}")
        return _placeholder_analysis(error=str(e))


async def analyze_book_video(video_path: str) -> Dict[str, Any]:
    """Analyze a book video by extracting a frame and analyzing it.

    For now, returns a placeholder. Full implementation would extract
    key frames using OpenCV and analyze each.
    """
    logger.info(f"Video analysis requested for: {video_path}")

    # TODO: Extract frames with OpenCV and analyze each
    # For now, return a note that video analysis requires frame extraction
    result = _placeholder_analysis()
    result["note"] = (
        "Video analysis extracts key frames for assessment. "
        "For best results, upload clear images of book pages and covers."
    )
    return result


def _placeholder_analysis(error: Optional[str] = None) -> Dict[str, Any]:
    """Return placeholder analysis when AI is unavailable."""
    result = {
        "quality_score": 0.0,
        "quality_status": "unknown",
        "physical_condition": {"score": 0, "issues": ["Analysis unavailable"]},
        "cover_quality": {"score": 0, "issues": ["Analysis unavailable"]},
        "page_readability": {"score": 0, "issues": ["Analysis unavailable"]},
        "binding_condition": {"score": 0, "issues": ["Analysis unavailable"]},
        "issues_found": ["AI analysis not performed"],
        "suggestions": ["Please configure GEMINI_API_KEY in .env to enable AI analysis"],
        "usability_verdict": "Unable to assess - AI not configured",
    }
    if error:
        result["error"] = error
    return result


__all__ = ["analyze_uploaded_file", "analyze_book_image", "analyze_book_video"]
