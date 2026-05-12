
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.database import Department
from app.services.ai_suggestions import generate_ai_suggestions

router = APIRouter()


@router.get("/department/{department_id}")
async def get_department_ai_suggestions(
    department_id: int,
    db: Session = Depends(get_db),
):
    # Validate department exists
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail=f"Department with id {department_id} not found")

    suggestions = await generate_ai_suggestions(db, department_id)
    return suggestions


@router.get("/")
async def get_distribution_suggestions(db: Session = Depends(get_db)):
    from app.services import distribution_logic

    try:
        suggestions = await distribution_logic.generate_distribution_suggestions(db)
        return suggestions
    except Exception as e:
        return {"suggestions": [], "error": str(e)}


@router.get("/shortages")
async def get_school_shortages(db: Session = Depends(get_db)):
    from app.services import distribution_logic

    try:
        shortages = await distribution_logic.get_school_shortages(db)
        return shortages
    except Exception as e:
        return {"shortages": [], "error": str(e)}
