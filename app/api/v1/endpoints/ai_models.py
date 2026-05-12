"""AI model versions endpoints.

Provides endpoints for managing AI model versions used for book condition scanning:
- GET list (paginated)
- POST register (new model, inactive by default)
- PUT activate (mutual exclusivity within same model_type)
- GET active (currently active model or 404)

Validates: Requirements 14.1–14.8
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.status import HTTP_201_CREATED

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.database.session import get_db
from app.models.database import AIModelVersion
from app.schemas.ai_models import AIModelCreate, AIModelResponse

router = APIRouter(prefix="/ai-models", tags=["ai-models"])


@router.get("", response_model=PaginatedResponse[AIModelResponse])
def list_ai_models(
    params: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    """Return a paginated list of all registered AI model versions.

    Validates: Requirement 14.1
    """
    query = db.query(AIModelVersion)
    return paginate(query, params)


@router.post("", response_model=AIModelResponse, status_code=HTTP_201_CREATED)
def register_ai_model(payload: AIModelCreate, db: Session = Depends(get_db)):
    """Register a new AI model version.

    The model is created with is_active=False by default.
    Enforces unique (model_name, model_version) combination — returns 409 on duplicate.
    Returns 422 on validation failure (handled by Pydantic).

    Validates: Requirements 14.2, 14.7, 14.8
    """
    # Check for duplicate model_name + model_version combination
    existing = (
        db.query(AIModelVersion)
        .filter(
            AIModelVersion.model_name == payload.model_name,
            AIModelVersion.model_version == payload.model_version,
        )
        .first()
    )
    if existing:
        raise ConflictError(
            detail="A model with this model_name and model_version combination already exists"
        )

    ai_model = AIModelVersion(
        model_name=payload.model_name,
        model_version=payload.model_version,
        model_type=payload.model_type,
        is_active=False,
    )
    db.add(ai_model)
    db.commit()
    db.refresh(ai_model)
    return ai_model


@router.get("/active", response_model=AIModelResponse)
def get_active_ai_model(db: Session = Depends(get_db)):
    """Return the currently active AI model version.

    Returns 404 if no active model is configured.

    Validates: Requirements 14.4, 14.5
    """
    active_model = (
        db.query(AIModelVersion).filter(AIModelVersion.is_active == True).first()  # noqa: E712
    )
    if active_model is None:
        raise NotFoundError(detail="No active AI model is configured")
    return active_model


@router.put("/{id}/activate", response_model=AIModelResponse)
def activate_ai_model(id: int, db: Session = Depends(get_db)):
    """Activate an AI model version.

    Sets the specified model as active and deactivates all other models
    sharing the same model_type value (mutual exclusivity).
    Returns 404 if the model ID does not exist.

    Validates: Requirements 14.3, 14.6
    """
    # Find the model to activate
    ai_model = db.query(AIModelVersion).filter(AIModelVersion.id == id).first()
    if ai_model is None:
        raise NotFoundError(detail=f"AIModelVersion with id {id} not found")

    # Deactivate all other models of the same model_type
    db.query(AIModelVersion).filter(
        AIModelVersion.model_type == ai_model.model_type,
        AIModelVersion.id != id,
    ).update({"is_active": False})

    # Activate the specified model
    ai_model.is_active = True
    db.commit()
    db.refresh(ai_model)
    return ai_model
