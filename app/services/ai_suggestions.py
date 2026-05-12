

import json
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.database import (
    Book,
    BookAllocation,
    BookCopy,
    Department,
    GradeLevel,
    Learner,
    School,
    SchoolBooksInventory,
    Subject,
)
from app.utils.logger import logger


SUGGESTIONS_PROMPT = """You are an expert school book distribution advisor for a Department of Education.

Analyze the following data about schools in a department and provide actionable suggestions for:
1. **Book redistribution** — which schools have excess books that could be transferred to schools with shortages
2. **Condition-based replacements** — books in poor/unusable condition that need replacement
3. **Allocation optimization** — how to better distribute books to maximize student access
4. **Procurement priorities** — which books/subjects need urgent procurement

Department: {department_name}
Number of schools: {num_schools}

=== SCHOOL DATA ===
{school_data}

=== INVENTORY SUMMARY ===
{inventory_data}

=== BOOK CONDITION SUMMARY ===
{condition_data}

=== ALLOCATION SUMMARY ===
{allocation_data}

Based on this data, provide your analysis and suggestions as a JSON object:
{{
    "summary": "Brief overview of the department's book situation",
    "redistribution_suggestions": [
        {{
            "from_school": "school name",
            "to_school": "school name",
            "book_title": "book name",
            "quantity": <number>,
            "reason": "why this transfer makes sense"
        }}
    ],
    "replacement_needed": [
        {{
            "school": "school name",
            "book_title": "book name",
            "quantity": <number>,
            "urgency": "high/medium/low",
            "reason": "why replacement is needed"
        }}
    ],
    "procurement_priorities": [
        {{
            "subject": "subject name",
            "grade_level": "grade level",
            "quantity_needed": <number>,
            "priority": "urgent/high/medium/low",
            "reason": "why this is a priority"
        }}
    ],
    "general_recommendations": [
        "actionable recommendation 1",
        "actionable recommendation 2"
    ],
    "risk_alerts": [
        "any urgent issues that need immediate attention"
    ]
}}

Respond ONLY with valid JSON (no markdown fences).
"""


def _gather_department_data(db: Session, department_id: int) -> Dict[str, Any]:
    # Get department info
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        return None

    # Get all schools in the department
    schools = db.query(School).filter(School.department_id == department_id).all()

    school_data = []
    inventory_data = []
    condition_data = []
    allocation_data = []

    for school in schools:
        # School basic info
        school_info = {
            "name": school.name,
            "city": school.city,
            "total_students": school.total_students,
            "total_teachers": school.total_teachers,
        }
        school_data.append(school_info)

        # Inventory for this school
        inventories = (
            db.query(SchoolBooksInventory)
            .filter(SchoolBooksInventory.school_id == school.id)
            .all()
        )
        for inv in inventories:
            inventory_data.append({
                "school": school.name,
                "subject": inv.subject,
                "grade_level": inv.grade_level,
                "quantity": inv.quantity,
            })

        # Book copies and their conditions
        copies = db.query(BookCopy).filter(BookCopy.school_id == school.id).all()
        condition_counts = {"excellent": 0, "good": 0, "fair": 0, "poor": 0, "unusable": 0}
        for copy in copies:
            if copy.condition in condition_counts:
                condition_counts[copy.condition] += 1

        if copies:
            condition_data.append({
                "school": school.name,
                "total_copies": len(copies),
                **condition_counts,
            })

        # Active allocations
        active_allocations = (
            db.query(BookAllocation)
            .join(BookCopy, BookAllocation.book_copy_id == BookCopy.id)
            .filter(
                BookCopy.school_id == school.id,
                BookAllocation.status == "active",
            )
            .count()
        )
        total_learners = (
            db.query(Learner)
            .join(Learner.grade)
            .filter(Learner.grade.has(school_id=school.id))
            .count()
        )
        allocation_data.append({
            "school": school.name,
            "active_allocations": active_allocations,
            "total_learners": total_learners,
            "allocation_rate": f"{(active_allocations / max(total_learners, 1)) * 100:.1f}%",
        })

    return {
        "department_name": department.name,
        "num_schools": len(schools),
        "school_data": school_data,
        "inventory_data": inventory_data,
        "condition_data": condition_data,
        "allocation_data": allocation_data,
    }


async def generate_ai_suggestions(db: Session, department_id: int) -> Dict[str, Any]:
    # Gather data
    data = _gather_department_data(db, department_id)
    if data is None:
        return {"error": f"Department with id {department_id} not found"}

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, returning placeholder suggestions")
        return _placeholder_suggestions(data)

    # Format the prompt with actual data
    prompt = SUGGESTIONS_PROMPT.format(
        department_name=data["department_name"],
        num_schools=data["num_schools"],
        school_data=json.dumps(data["school_data"], indent=2),
        inventory_data=json.dumps(data["inventory_data"], indent=2),
        condition_data=json.dumps(data["condition_data"], indent=2),
        allocation_data=json.dumps(data["allocation_data"], indent=2),
    )

    # Call Gemini API
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 4096,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            logger.error(f"Gemini API error {response.status_code}: {response.text}")
            return _placeholder_suggestions(data, error=f"AI API error: {response.status_code}")

        result = response.json()
        text_content = result["candidates"][0]["content"]["parts"][0]["text"]

        # Clean up response
        text_content = text_content.strip()
        if text_content.startswith("```"):
            text_content = text_content.split("\n", 1)[1]
        if text_content.endswith("```"):
            text_content = text_content.rsplit("```", 1)[0]
        text_content = text_content.strip()

        suggestions = json.loads(text_content)
        suggestions["department_id"] = department_id
        suggestions["department_name"] = data["department_name"]
        suggestions["schools_analyzed"] = data["num_schools"]
        suggestions["ai_powered"] = True

        logger.info(f"AI suggestions generated for department {department_id}")
        return suggestions

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini suggestions response: {e}")
        return _placeholder_suggestions(data, error="Failed to parse AI response")
    except httpx.TimeoutException:
        logger.error("Gemini API request timed out for suggestions")
        return _placeholder_suggestions(data, error="AI analysis timed out")
    except Exception as e:
        logger.error(f"Unexpected error generating AI suggestions: {e}")
        return _placeholder_suggestions(data, error=str(e))


def _placeholder_suggestions(data: Dict[str, Any], error: Optional[str] = None) -> Dict[str, Any]:
    result = {
        "department_id": None,
        "department_name": data["department_name"],
        "schools_analyzed": data["num_schools"],
        "ai_powered": False,
        "summary": "AI suggestions unavailable. Please configure GEMINI_API_KEY.",
        "redistribution_suggestions": [],
        "replacement_needed": [],
        "procurement_priorities": [],
        "general_recommendations": [
            "Configure GEMINI_API_KEY in environment variables to enable AI-powered suggestions",
            f"Department has {data['num_schools']} schools to analyze",
        ],
        "risk_alerts": [],
    }
    if error:
        result["error"] = error
    return result


__all__ = ["generate_ai_suggestions"]
