from sqlalchemy.orm import Session
from typing import List
import asyncio
from app.models import schemas, database
from app.utils.logger import logger
from math import radians, cos, sin, asin, sqrt


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in kilometers"""
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    
    return c * r


async def generate_distribution_suggestions(db: Session) -> List[schemas.DistributionSuggestion]:
    """Generate book distribution suggestions based on shortages"""
    
    logger.info("Generating distribution suggestions...")
    
    # This is a simplified algorithm - in real implementation, you'd have more complex logic
    
    # Get schools with excess books
    schools_with_excess = db.query(database.School).join(
        database.BookInventory
    ).filter(
        database.BookInventory.quantity > 50  # Schools with more than 50 books
    ).distinct().all()
    
    # Get schools with shortages
    schools_with_shortage = db.query(database.School).join(
        database.BookInventory
    ).filter(
        database.BookInventory.quantity < 10  # Schools with less than 10 books
    ).distinct().all()
    
    suggestions = []
    
    for source_school in schools_with_excess:
        for dest_school in schools_with_shortage:
            # Calculate distance
            distance = calculate_distance(
                source_school.latitude, source_school.longitude,
                dest_school.latitude, dest_school.longitude
            )
            
            # Only suggest if schools are within reasonable distance
            if distance <= 50:  # Within 50km
                # Find books that source has in excess and destination needs
                excess_inventories = db.query(database.BookInventory).filter(
                    database.BookInventory.school_id == source_school.id,
                    database.BookInventory.quantity > 20  # Has more than 20
                ).all()
                
                for inv in excess_inventories:
                    suggestion = schemas.DistributionSuggestion(
                        source_school=schemas.School.from_orm(source_school) if hasattr(schemas.School, 'from_orm') else schemas.School.model_validate(source_school),
                        destination_school=schemas.School.from_orm(dest_school) if hasattr(schemas.School, 'from_orm') else schemas.School.model_validate(dest_school),
                        book_subject=inv.subject,
                        grade_level=inv.grade_level,
                        quantity_to_transfer=min(inv.quantity - 10, 15),  # Transfer up to 15 or until 10 remain
                        distance_km=distance,
                        estimated_delivery_days=2
                    )
                    suggestions.append(suggestion)
    
    logger.info(f"Generated {len(suggestions)} distribution suggestions")
    return suggestions


async def get_school_shortages(db: Session) -> List[schemas.SchoolBookShortage]:
    """Get list of schools with book shortages"""
    
    logger.info("Getting school shortages...")
    
    # This is a simplified version - real implementation would have more complex logic
    
    shortages = []
    
    # Query schools with low inventory
    low_inventory = db.query(database.BookInventory).filter(
        database.BookInventory.quantity < 10
    ).all()
    
    for inv in low_inventory:
        school = db.query(database.School).filter(
            database.School.id == inv.school_id
        ).first()
        
        shortage = schemas.SchoolBookShortage(
            school=schemas.School.from_orm(school) if hasattr(schemas.School, 'from_orm') else schemas.School.model_validate(school),
            subject=inv.subject,
            grade_level=inv.grade_level,
            current_stock=inv.quantity,
            required_stock=50,  # Default requirement
            shortage=max(0, 50 - inv.quantity)
        )
        shortages.append(shortage)
    
    return shortages


async def create_distribution_request(
    db: Session,
    request: schemas.DistributionRequestCreate
) -> schemas.DistributionRequest:
    """Create a distribution request between schools"""
    
    logger.info(f"Creating distribution request from {request.source_school_id} to {request.destination_school_id}")
    
    # Check if schools exist
    source_school = db.query(database.School).filter(
        database.School.id == request.source_school_id
    ).first()
    
    dest_school = db.query(database.School).filter(
        database.School.id == request.destination_school_id
    ).first()
    
    if not source_school or not dest_school:
        raise ValueError("Source or destination school not found")
    
    # Check if source school has enough books
    inventory = db.query(database.BookInventory).filter(
        database.BookInventory.school_id == request.source_school_id,
        database.BookInventory.subject == request.book_subject.value,
        database.BookInventory.grade_level == request.grade_level.value
    ).first()
    
    if not inventory or inventory.quantity < request.requested_quantity:
        raise ValueError("Insufficient books in source school")
    
    # Create distribution request
    dist_request = database.DistributionRequest(
        source_school_id=request.source_school_id,
        destination_school_id=request.destination_school_id,
        book_subject=request.book_subject.value,
        grade_level=request.grade_level.value,
        requested_quantity=request.requested_quantity,
        status="pending"
    )
    
    db.add(dist_request)
    db.commit()
    db.refresh(dist_request)
    
    return schemas.DistributionRequest.model_validate(dist_request)


__all__ = [
    'generate_distribution_suggestions',
    'get_school_shortages',
    'create_distribution_request',
    'calculate_distance'
]