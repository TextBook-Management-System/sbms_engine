"""Create all 22 SBMS tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

Creates all 22 tables for the School Book Management System with:
- BIGINT UNSIGNED primary keys and foreign keys
- Proper VARCHAR lengths matching model definitions
- Foreign key constraints with appropriate ON DELETE rules
- Unique constraints (email, ISBN, QR code, model_name+version)
- CHECK constraints for ENUM-like status fields
- Timestamps (created_at, updated_at, resolved_at) as DATETIME
- MySQL-compatible charset (utf8mb4)
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

# Helper type for MySQL BIGINT UNSIGNED
BigIntUnsigned = sa.BigInteger().with_variant(sa.BigInteger(), "mysql")


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. grade_levels
    # -----------------------------------------------------------------------
    op.create_table(
        "grade_levels",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 2. subjects
    # -----------------------------------------------------------------------
    op.create_table(
        "subjects",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 3. departments
    # -----------------------------------------------------------------------
    op.create_table(
        "departments",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 4. schools
    # -----------------------------------------------------------------------
    op.create_table(
        "schools",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("department_id", BigIntUnsigned, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("contact_person", sa.String(200), nullable=True),
        sa.Column("phone_number", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("total_students", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_teachers", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_schools_department_id",
            ondelete="RESTRICT",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 5. users
    # -----------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("department_id", BigIntUnsigned, nullable=True),
        sa.Column("school_id", BigIntUnsigned, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_users_department_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["schools.id"],
            name="fk_users_school_id",
            ondelete="SET NULL",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 6. user_roles
    # -----------------------------------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("user_id", BigIntUnsigned, nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_roles_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "role IN ('DeptAdmin', 'SchoolAdmin', 'Teacher', 'Parent')",
            name="ck_user_roles_role",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 7. grades
    # -----------------------------------------------------------------------
    op.create_table(
        "grades",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("school_id", BigIntUnsigned, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["schools.id"],
            name="fk_grades_school_id",
            ondelete="CASCADE",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 8. learners
    # -----------------------------------------------------------------------
    op.create_table(
        "learners",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("grade_id", BigIntUnsigned, nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["grade_id"],
            ["grades.id"],
            name="fk_learners_grade_id",
            ondelete="CASCADE",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 9. parent_learners
    # -----------------------------------------------------------------------
    op.create_table(
        "parent_learners",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("parent_id", BigIntUnsigned, nullable=False),
        sa.Column("learner_id", BigIntUnsigned, nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["users.id"],
            name="fk_parent_learners_parent_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_parent_learners_learner_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("parent_id", "learner_id", name="uq_parent_learner"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 10. books
    # -----------------------------------------------------------------------
    op.create_table(
        "books",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subject_id", BigIntUnsigned, nullable=False),
        sa.Column("grade_level_id", BigIntUnsigned, nullable=False),
        sa.Column("isbn", sa.String(50), nullable=True, unique=True),
        sa.Column("publisher", sa.String(200), nullable=True),
        sa.Column("author", sa.String(200), nullable=True),
        sa.Column("edition", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name="fk_books_subject_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["grade_level_id"],
            ["grade_levels.id"],
            name="fk_books_grade_level_id",
            ondelete="RESTRICT",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 11. school_books_inventory
    # -----------------------------------------------------------------------
    op.create_table(
        "school_books_inventory",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("school_id", BigIntUnsigned, nullable=False),
        sa.Column("book_id", BigIntUnsigned, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("grade_level", sa.String(100), nullable=False),
        sa.Column("condition_notes", sa.Text, nullable=True),
        sa.Column(
            "last_updated",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["schools.id"],
            name="fk_school_books_inventory_school_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["book_id"],
            ["books.id"],
            name="fk_school_books_inventory_book_id",
            ondelete="CASCADE",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 12. book_requests
    # -----------------------------------------------------------------------
    op.create_table(
        "book_requests",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("book_id", BigIntUnsigned, nullable=False),
        sa.Column("school_id", BigIntUnsigned, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="pending"
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["book_id"],
            ["books.id"],
            name="fk_book_requests_book_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["schools.id"],
            name="fk_book_requests_school_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_book_requests_status",
        ),
        sa.CheckConstraint(
            "quantity >= 1 AND quantity <= 10000",
            name="ck_book_requests_quantity",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 13. deliveries
    # -----------------------------------------------------------------------
    op.create_table(
        "deliveries",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("book_request_id", BigIntUnsigned, nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="pending"
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["book_request_id"],
            ["book_requests.id"],
            name="fk_deliveries_book_request_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_transit', 'delivered')",
            name="ck_deliveries_status",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 14. book_boxes
    # -----------------------------------------------------------------------
    op.create_table(
        "book_boxes",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("delivery_id", BigIntUnsigned, nullable=False),
        sa.Column("book_id", BigIntUnsigned, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["deliveries.id"],
            name="fk_book_boxes_delivery_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["book_id"],
            ["books.id"],
            name="fk_book_boxes_book_id",
            ondelete="RESTRICT",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 15. book_copies
    # -----------------------------------------------------------------------
    op.create_table(
        "book_copies",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("book_id", BigIntUnsigned, nullable=False),
        sa.Column("school_id", BigIntUnsigned, nullable=False),
        sa.Column("qr_code", sa.String(255), nullable=False, unique=True),
        sa.Column(
            "condition", sa.String(50), nullable=False, server_default="good"
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["book_id"],
            ["books.id"],
            name="fk_book_copies_book_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["schools.id"],
            name="fk_book_copies_school_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "`condition` IN ('excellent', 'good', 'fair', 'poor', 'unusable')",
            name="ck_book_copies_condition",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 16. ai_model_versions
    # -----------------------------------------------------------------------
    op.create_table(
        "ai_model_versions",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "model_name", "model_version", name="uq_ai_model_name_version"
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 17. book_condition_scans
    # -----------------------------------------------------------------------
    op.create_table(
        "book_condition_scans",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("book_copy_id", BigIntUnsigned, nullable=False),
        sa.Column("ai_model_id", BigIntUnsigned, nullable=False),
        sa.Column("condition", sa.String(50), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("verified_condition", sa.String(50), nullable=True),
        sa.Column("scan_image_path", sa.String(500), nullable=False),
        sa.Column(
            "scanned_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["book_copy_id"],
            ["book_copies.id"],
            name="fk_book_condition_scans_book_copy_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ai_model_id"],
            ["ai_model_versions.id"],
            name="fk_book_condition_scans_ai_model_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "`condition` IN ('excellent', 'good', 'fair', 'poor', 'unusable')",
            name="ck_book_condition_scans_condition",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 18. book_allocations
    # -----------------------------------------------------------------------
    op.create_table(
        "book_allocations",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("book_copy_id", BigIntUnsigned, nullable=False),
        sa.Column("learner_id", BigIntUnsigned, nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="active"
        ),
        sa.Column(
            "allocation_date",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("return_date", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(
            ["book_copy_id"],
            ["book_copies.id"],
            name="fk_book_allocations_book_copy_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"],
            ["learners.id"],
            name="fk_book_allocations_learner_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'returned')",
            name="ck_book_allocations_status",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 19. parent_acknowledgements
    # -----------------------------------------------------------------------
    op.create_table(
        "parent_acknowledgements",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("allocation_id", BigIntUnsigned, nullable=False),
        sa.Column("parent_id", BigIntUnsigned, nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="pending"
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["allocation_id"],
            ["book_allocations.id"],
            name="fk_parent_acknowledgements_allocation_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["users.id"],
            name="fk_parent_acknowledgements_parent_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_parent_acknowledgements_status",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 20. damage_notifications
    # -----------------------------------------------------------------------
    op.create_table(
        "damage_notifications",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("book_copy_id", BigIntUnsigned, nullable=False),
        sa.Column("reported_by", BigIntUnsigned, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="open"
        ),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(
            ["book_copy_id"],
            ["book_copies.id"],
            name="fk_damage_notifications_book_copy_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reported_by"],
            ["users.id"],
            name="fk_damage_notifications_reported_by",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')",
            name="ck_damage_notifications_status",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 21. replacement_requests
    # -----------------------------------------------------------------------
    op.create_table(
        "replacement_requests",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("damage_notification_id", BigIntUnsigned, nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="pending"
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["damage_notification_id"],
            ["damage_notifications.id"],
            name="fk_replacement_requests_damage_notification_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_replacement_requests_status",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # -----------------------------------------------------------------------
    # 22. escalations
    # -----------------------------------------------------------------------
    op.create_table(
        "escalations",
        sa.Column("id", BigIntUnsigned, primary_key=True, autoincrement=True),
        sa.Column("replacement_request_id", BigIntUnsigned, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column(
            "status", sa.String(50), nullable=False, server_default="open"
        ),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(
            ["replacement_request_id"],
            ["replacement_requests.id"],
            name="fk_escalations_replacement_request_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')",
            name="ck_escalations_status",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    # Drop tables in reverse order to respect foreign key dependencies
    op.drop_table("escalations")
    op.drop_table("replacement_requests")
    op.drop_table("damage_notifications")
    op.drop_table("parent_acknowledgements")
    op.drop_table("book_allocations")
    op.drop_table("book_condition_scans")
    op.drop_table("ai_model_versions")
    op.drop_table("book_copies")
    op.drop_table("book_boxes")
    op.drop_table("deliveries")
    op.drop_table("book_requests")
    op.drop_table("school_books_inventory")
    op.drop_table("books")
    op.drop_table("parent_learners")
    op.drop_table("learners")
    op.drop_table("grades")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("schools")
    op.drop_table("departments")
    op.drop_table("subjects")
    op.drop_table("grade_levels")
