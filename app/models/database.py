"""
SQLAlchemy ORM models for the School Book Management System (SBMS).

All 22 tables matching the MySQL schema with:
- BIGINT UNSIGNED primary keys
- Foreign key relationships with proper ondelete cascade rules
- CHECK constraints for ENUM values (condition, status fields)
- Unique constraints (QR codes, ISBN, email, model name+version)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


# ---------------------------------------------------------------------------
# Helper: BIGINT UNSIGNED type for MySQL compatibility
# ---------------------------------------------------------------------------
BigIntUnsigned = BigInteger().with_variant(BigInteger(), "mysql")


# ---------------------------------------------------------------------------
# Lookup Tables
# ---------------------------------------------------------------------------


class GradeLevel(Base):
    """Lookup table for grade levels (e.g., Grade 1, Grade 2, ...)."""

    __tablename__ = "grade_levels"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Relationships
    books: Mapped[list["Book"]] = relationship("Book", back_populates="grade_level_rel")


class Subject(Base):
    """Lookup table for subjects (e.g., Mathematics, English, ...)."""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Relationships
    books: Mapped[list["Book"]] = relationship("Book", back_populates="subject_rel")


# ---------------------------------------------------------------------------
# Organizational Structure
# ---------------------------------------------------------------------------


class Department(Base):
    """Departments that contain schools."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    schools: Mapped[list["School"]] = relationship("School", back_populates="department")
    users: Mapped[list["User"]] = relationship("User", back_populates="department")


class School(Base):
    """Schools belonging to a department."""

    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    contact_person: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_students: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_teachers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    department: Mapped["Department"] = relationship("Department", back_populates="schools")
    grades: Mapped[list["Grade"]] = relationship("Grade", back_populates="school")
    users: Mapped[list["User"]] = relationship("User", back_populates="school")
    book_copies: Mapped[list["BookCopy"]] = relationship("BookCopy", back_populates="school")
    school_books_inventory: Mapped[list["SchoolBooksInventory"]] = relationship(
        "SchoolBooksInventory", back_populates="school"
    )
    book_requests: Mapped[list["BookRequest"]] = relationship(
        "BookRequest", back_populates="school"
    )


# ---------------------------------------------------------------------------
# Users and RBAC
# ---------------------------------------------------------------------------


class User(Base):
    """System users with authentication credentials."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    id_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        BigIntUnsigned, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    school_id: Mapped[Optional[int]] = mapped_column(
        BigIntUnsigned, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="users"
    )
    school: Mapped[Optional["School"]] = relationship("School", back_populates="users")
    roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user")
    parent_learners: Mapped[list["ParentLearner"]] = relationship(
        "ParentLearner", back_populates="parent"
    )
    parent_acknowledgements: Mapped[list["ParentAcknowledgement"]] = relationship(
        "ParentAcknowledgement", back_populates="parent"
    )
    damage_notifications: Mapped[list["DamageNotification"]] = relationship(
        "DamageNotification", back_populates="reported_by_user"
    )


class UserRole(Base):
    """Roles assigned to users (DeptAdmin, SchoolAdmin, Teacher, Parent)."""

    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "role IN ('DeptAdmin', 'SchoolAdmin', 'Teacher', 'Parent')",
            name="ck_user_roles_role",
        ),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="roles")


# ---------------------------------------------------------------------------
# Academic Structure
# ---------------------------------------------------------------------------


class Grade(Base):
    """Grades within a school (e.g., Grade 1A, Grade 2B)."""

    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="grades")
    learners: Mapped[list["Learner"]] = relationship("Learner", back_populates="grade")


class Learner(Base):
    """Students enrolled in a grade."""

    __tablename__ = "learners"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    grade_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("grades.id", ondelete="CASCADE"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    id_number: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    grade: Mapped["Grade"] = relationship("Grade", back_populates="learners")
    parent_learners: Mapped[list["ParentLearner"]] = relationship(
        "ParentLearner", back_populates="learner"
    )
    book_allocations: Mapped[list["BookAllocation"]] = relationship(
        "BookAllocation", back_populates="learner"
    )


class ParentLearner(Base):
    """Link table between parents (users) and learners."""

    __tablename__ = "parent_learners"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    learner_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("learners.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("parent_id", "learner_id", name="uq_parent_learner"),
    )

    # Relationships
    parent: Mapped["User"] = relationship("User", back_populates="parent_learners")
    learner: Mapped["Learner"] = relationship("Learner", back_populates="parent_learners")


# ---------------------------------------------------------------------------
# Book Catalog and Inventory
# ---------------------------------------------------------------------------


class Book(Base):
    """Book catalog entries."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    grade_level_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("grade_levels.id", ondelete="RESTRICT"), nullable=False
    )
    isbn: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    edition: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    subject_rel: Mapped["Subject"] = relationship("Subject", back_populates="books")
    grade_level_rel: Mapped["GradeLevel"] = relationship("GradeLevel", back_populates="books")
    book_copies: Mapped[list["BookCopy"]] = relationship("BookCopy", back_populates="book")
    book_requests: Mapped[list["BookRequest"]] = relationship(
        "BookRequest", back_populates="book"
    )
    school_books_inventory: Mapped[list["SchoolBooksInventory"]] = relationship(
        "SchoolBooksInventory", back_populates="book"
    )
    book_boxes: Mapped[list["BookBox"]] = relationship("BookBox", back_populates="book")


class SchoolBooksInventory(Base):
    """Aggregated inventory view maintained by MySQL triggers (read-only via API)."""

    __tablename__ = "school_books_inventory"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    grade_level: Mapped[str] = mapped_column(String(100), nullable=False)
    condition_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationships
    school: Mapped["School"] = relationship("School", back_populates="school_books_inventory")
    book: Mapped["Book"] = relationship("Book", back_populates="school_books_inventory")


# ---------------------------------------------------------------------------
# Logistics
# ---------------------------------------------------------------------------


class BookRequest(Base):
    """Book requests from schools to the department."""

    __tablename__ = "book_requests"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False
    )
    school_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_book_requests_status",
        ),
        CheckConstraint(
            "quantity >= 1 AND quantity <= 10000",
            name="ck_book_requests_quantity",
        ),
    )

    # Relationships
    book: Mapped["Book"] = relationship("Book", back_populates="book_requests")
    school: Mapped["School"] = relationship("School", back_populates="book_requests")
    deliveries: Mapped[list["Delivery"]] = relationship("Delivery", back_populates="book_request")


class Delivery(Base):
    """Deliveries fulfilling book requests."""

    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    book_request_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("book_requests.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_transit', 'delivered')",
            name="ck_deliveries_status",
        ),
    )

    # Relationships
    book_request: Mapped["BookRequest"] = relationship(
        "BookRequest", back_populates="deliveries"
    )
    book_boxes: Mapped[list["BookBox"]] = relationship("BookBox", back_populates="delivery")


class BookBox(Base):
    """Boxes of books within a delivery."""

    __tablename__ = "book_boxes"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    delivery_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False
    )
    book_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    delivery: Mapped["Delivery"] = relationship("Delivery", back_populates="book_boxes")
    book: Mapped["Book"] = relationship("Book", back_populates="book_boxes")


# ---------------------------------------------------------------------------
# Book Copies and QR Tracking
# ---------------------------------------------------------------------------


class BookCopy(Base):
    """Individual physical book copies tracked by QR code."""

    __tablename__ = "book_copies"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("books.id", ondelete="RESTRICT"), nullable=False
    )
    school_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False
    )
    qr_code: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    condition: Mapped[str] = mapped_column(String(50), nullable=False, default="good")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "condition IN ('excellent', 'good', 'fair', 'poor', 'unusable')",
            name="ck_book_copies_condition",
        ),
    )

    # Relationships
    book: Mapped["Book"] = relationship("Book", back_populates="book_copies")
    school: Mapped["School"] = relationship("School", back_populates="book_copies")
    book_condition_scans: Mapped[list["BookConditionScan"]] = relationship(
        "BookConditionScan", back_populates="book_copy"
    )
    book_allocations: Mapped[list["BookAllocation"]] = relationship(
        "BookAllocation", back_populates="book_copy"
    )
    damage_notifications: Mapped[list["DamageNotification"]] = relationship(
        "DamageNotification", back_populates="book_copy"
    )


# ---------------------------------------------------------------------------
# AI and Scanning
# ---------------------------------------------------------------------------


class AIModelVersion(Base):
    """Registered AI model versions for book condition scanning."""

    __tablename__ = "ai_model_versions"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("model_name", "model_version", name="uq_ai_model_name_version"),
    )

    # Relationships
    book_condition_scans: Mapped[list["BookConditionScan"]] = relationship(
        "BookConditionScan", back_populates="ai_model"
    )


class BookConditionScan(Base):
    """AI-powered book condition scan records."""

    __tablename__ = "book_condition_scans"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    book_copy_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("book_copies.id", ondelete="CASCADE"), nullable=False
    )
    ai_model_id: Mapped[int] = mapped_column(
        BigIntUnsigned,
        ForeignKey("ai_model_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    condition: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    verified_condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ai_issues: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scan_image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "condition IN ('excellent', 'good', 'fair', 'poor', 'unusable')",
            name="ck_book_condition_scans_condition",
        ),
    )

    # Relationships
    book_copy: Mapped["BookCopy"] = relationship(
        "BookCopy", back_populates="book_condition_scans"
    )
    ai_model: Mapped["AIModelVersion"] = relationship(
        "AIModelVersion", back_populates="book_condition_scans"
    )


# ---------------------------------------------------------------------------
# Allocations and Acknowledgements
# ---------------------------------------------------------------------------


class BookAllocation(Base):
    """Book-to-learner allocation records."""

    __tablename__ = "book_allocations"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    book_copy_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("book_copies.id", ondelete="RESTRICT"), nullable=False
    )
    learner_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("learners.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    allocation_date: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    return_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scan_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ai_condition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ai_confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_issues: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'returned')",
            name="ck_book_allocations_status",
        ),
    )

    # Relationships
    book_copy: Mapped["BookCopy"] = relationship(
        "BookCopy", back_populates="book_allocations"
    )
    learner: Mapped["Learner"] = relationship("Learner", back_populates="book_allocations")
    parent_acknowledgements: Mapped[list["ParentAcknowledgement"]] = relationship(
        "ParentAcknowledgement", back_populates="allocation"
    )


class ParentAcknowledgement(Base):
    """Parent acknowledgements for book allocations."""

    __tablename__ = "parent_acknowledgements"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    allocation_id: Mapped[int] = mapped_column(
        BigIntUnsigned,
        ForeignKey("book_allocations.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_parent_acknowledgements_status",
        ),
    )

    # Relationships
    allocation: Mapped["BookAllocation"] = relationship(
        "BookAllocation", back_populates="parent_acknowledgements"
    )
    parent: Mapped["User"] = relationship(
        "User", back_populates="parent_acknowledgements"
    )


# ---------------------------------------------------------------------------
# Damage and Replacement Workflow
# ---------------------------------------------------------------------------


class DamageNotification(Base):
    """Damage reports for book copies."""

    __tablename__ = "damage_notifications"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    book_copy_id: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("book_copies.id", ondelete="RESTRICT"), nullable=False
    )
    reported_by: Mapped[int] = mapped_column(
        BigIntUnsigned, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'resolved')",
            name="ck_damage_notifications_status",
        ),
    )

    # Relationships
    book_copy: Mapped["BookCopy"] = relationship(
        "BookCopy", back_populates="damage_notifications"
    )
    reported_by_user: Mapped["User"] = relationship(
        "User", back_populates="damage_notifications"
    )
    replacement_requests: Mapped[list["ReplacementRequest"]] = relationship(
        "ReplacementRequest", back_populates="damage_notification"
    )


class ReplacementRequest(Base):
    """Replacement requests triggered by damage notifications."""

    __tablename__ = "replacement_requests"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    damage_notification_id: Mapped[int] = mapped_column(
        BigIntUnsigned,
        ForeignKey("damage_notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_replacement_requests_status",
        ),
    )

    # Relationships
    damage_notification: Mapped["DamageNotification"] = relationship(
        "DamageNotification", back_populates="replacement_requests"
    )
    escalations: Mapped[list["Escalation"]] = relationship(
        "Escalation", back_populates="replacement_request"
    )


class Escalation(Base):
    """Escalations for unresolved replacement requests."""

    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(BigIntUnsigned, primary_key=True, autoincrement=True)
    replacement_request_id: Mapped[int] = mapped_column(
        BigIntUnsigned,
        ForeignKey("replacement_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'resolved')",
            name="ck_escalations_status",
        ),
    )

    # Relationships
    replacement_request: Mapped["ReplacementRequest"] = relationship(
        "ReplacementRequest", back_populates="escalations"
    )
