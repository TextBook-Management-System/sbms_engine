"""Pydantic request/response schemas for all SBMS API endpoints."""

from app.schemas.acknowledgements import (
    AcknowledgementCreate,
    AcknowledgementReject,
    AcknowledgementResponse,
)
from app.schemas.ai_models import AIModelCreate, AIModelResponse
from app.schemas.allocations import AllocationCreate, AllocationResponse
from app.schemas.auth import (
    AccessTokenResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.book_copies import (
    BookCondition,
    BookCopyConditionUpdate,
    BookCopyCreate,
    BookCopyResponse,
)
from app.schemas.book_requests import (
    BookRequestCreate,
    BookRequestReject,
    BookRequestResponse,
)
from app.schemas.books import BookCreate, BookResponse, BookUpdate
from app.schemas.damage_notifications import (
    DamageNotificationCreate,
    DamageNotificationResolve,
    DamageNotificationResponse,
)
from app.schemas.deliveries import (
    BookBoxCreate,
    BookBoxResponse,
    DeliveryCreate,
    DeliveryResponse,
)
from app.schemas.departments import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.schemas.escalations import (
    EscalationCreate,
    EscalationResolve,
    EscalationResponse,
)
from app.schemas.grade_levels import (
    GradeLevelCreate,
    GradeLevelResponse,
    GradeLevelUpdate,
)
from app.schemas.grades import GradeCreate, GradeResponse, GradeUpdate
from app.schemas.inventory import InventoryResponse
from app.schemas.learners import (
    LearnerCreate,
    LearnerResponse,
    LearnerUpdate,
    ParentLearnerCreate,
    ParentLearnerResponse,
)
from app.schemas.replacement_requests import (
    ReplacementRequestCreate,
    ReplacementRequestReject,
    ReplacementRequestResponse,
)
from app.schemas.scans import ScanCreate, ScanResponse, ScanVerifyRequest
from app.schemas.schools import SchoolCreate, SchoolResponse, SchoolUpdate
from app.schemas.subjects import SubjectCreate, SubjectResponse, SubjectUpdate
from app.schemas.users import (
    RoleAssignRequest,
    RoleName,
    UserRoleResponse,
    UserUpdateRequest,
    UserWithRolesResponse,
)

__all__ = [
    # Auth
    "UserRegisterRequest",
    "UserLoginRequest",
    "TokenResponse",
    "AccessTokenResponse",
    "RefreshTokenRequest",
    "UserResponse",
    # Users
    "UserUpdateRequest",
    "RoleAssignRequest",
    "RoleName",
    "UserRoleResponse",
    "UserWithRolesResponse",
    # Grade Levels
    "GradeLevelCreate",
    "GradeLevelUpdate",
    "GradeLevelResponse",
    # Subjects
    "SubjectCreate",
    "SubjectUpdate",
    "SubjectResponse",
    # Departments
    "DepartmentCreate",
    "DepartmentUpdate",
    "DepartmentResponse",
    # Schools
    "SchoolCreate",
    "SchoolUpdate",
    "SchoolResponse",
    # Grades
    "GradeCreate",
    "GradeUpdate",
    "GradeResponse",
    # Learners
    "LearnerCreate",
    "LearnerUpdate",
    "LearnerResponse",
    "ParentLearnerCreate",
    "ParentLearnerResponse",
    # Books
    "BookCreate",
    "BookUpdate",
    "BookResponse",
    # Inventory
    "InventoryResponse",
    # Book Requests
    "BookRequestCreate",
    "BookRequestReject",
    "BookRequestResponse",
    # Deliveries
    "DeliveryCreate",
    "DeliveryResponse",
    "BookBoxCreate",
    "BookBoxResponse",
    # Book Copies
    "BookCondition",
    "BookCopyCreate",
    "BookCopyConditionUpdate",
    "BookCopyResponse",
    # AI Models
    "AIModelCreate",
    "AIModelResponse",
    # Scans
    "ScanCreate",
    "ScanVerifyRequest",
    "ScanResponse",
    # Allocations
    "AllocationCreate",
    "AllocationResponse",
    # Acknowledgements
    "AcknowledgementCreate",
    "AcknowledgementReject",
    "AcknowledgementResponse",
    # Damage Notifications
    "DamageNotificationCreate",
    "DamageNotificationResolve",
    "DamageNotificationResponse",
    # Replacement Requests
    "ReplacementRequestCreate",
    "ReplacementRequestReject",
    "ReplacementRequestResponse",
    # Escalations
    "EscalationCreate",
    "EscalationResolve",
    "EscalationResponse",
]
