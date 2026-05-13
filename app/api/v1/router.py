from fastapi import APIRouter
from app.api.v1.endpoints import (
    acknowledgements,
    ai_models,
    allocations,
    auth,
    book_copies,
    book_requests,
    books,
    damage_notifications,
    deliveries,
    departments,
    escalations,
    grade_levels,
    grades,
    inventory,
    learners,
    replacement_requests,
    reports,
    scans,
    schools,
    subjects,
    suggestions,
    upload,
    users,
)

api_router = APIRouter()

# Include all endpoint routers
# Each module defines its own prefix and tags via APIRouter(prefix=..., tags=[...])
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(grade_levels.router)
api_router.include_router(subjects.router)
api_router.include_router(departments.router)
api_router.include_router(schools.router)
api_router.include_router(grades.router)
api_router.include_router(learners.router)
api_router.include_router(books.router)
api_router.include_router(inventory.router)
api_router.include_router(book_requests.router)
api_router.include_router(deliveries.router)
api_router.include_router(book_copies.router)
api_router.include_router(ai_models.router)
api_router.include_router(scans.router)
api_router.include_router(scans.book_copy_scans_router)
api_router.include_router(allocations.router)
api_router.include_router(acknowledgements.router)
api_router.include_router(damage_notifications.router)
api_router.include_router(replacement_requests.router)
api_router.include_router(escalations.router)

# Additional utility routers (not part of core SBMS domain endpoints)
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(suggestions.router, prefix="/suggestions", tags=["suggestions"])
api_router.include_router(reports.router)
