from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.models import schemas
from app.services import distribution_logic

router = APIRouter()


@router.get("/", response_model=List[schemas.DistributionSuggestion])
async def get_distribution_suggestions(db: Session = Depends(get_db)):
    """Get book distribution suggestions based on shortages"""
    
    suggestions = await distribution_logic.generate_distribution_suggestions(db)
    return suggestions


@router.get("/shortages", response_model=List[schemas.SchoolBookShortage])
async def get_school_shortages(db: Session = Depends(get_db)):
    """Get schools with book shortages"""
    
    shortages = await distribution_logic.get_school_shortages(db)
    return shortages


@router.post("/request", response_model=schemas.DistributionRequest)
async def create_distribution_request(
    request: schemas.DistributionRequestCreate,
    db: Session = Depends(get_db)
):
    """Create a distribution request between schools"""
    
    # Check if request is valid
    distribution_request = await distribution_logic.create_distribution_request(
        db=db,
        request=request
    )
    
    return distribution_request