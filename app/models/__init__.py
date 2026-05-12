"""
SBMS ENGINE Models Package

All 22 SQLAlchemy ORM models matching the MySQL schema.
"""

from .database import (
    GradeLevel,
    Subject,
    Department,
    School,
    User,
    UserRole,
    Grade,
    Learner,
    ParentLearner,
    Book,
    SchoolBooksInventory,
    BookRequest,
    Delivery,
    BookBox,
    BookCopy,
    AIModelVersion,
    BookConditionScan,
    BookAllocation,
    ParentAcknowledgement,
    DamageNotification,
    ReplacementRequest,
    Escalation,
)

__all__ = [
    # Lookup Tables
    "GradeLevel",
    "Subject",
    # Organizational Structure
    "Department",
    "School",
    # Users and RBAC
    "User",
    "UserRole",
    # Academic Structure
    "Grade",
    "Learner",
    "ParentLearner",
    # Book Catalog and Inventory
    "Book",
    "SchoolBooksInventory",
    # Logistics
    "BookRequest",
    "Delivery",
    "BookBox",
    # Book Copies and QR Tracking
    "BookCopy",
    # AI and Scanning
    "AIModelVersion",
    "BookConditionScan",
    # Allocations and Acknowledgements
    "BookAllocation",
    "ParentAcknowledgement",
    # Damage and Replacement Workflow
    "DamageNotification",
    "ReplacementRequest",
    "Escalation",
]
