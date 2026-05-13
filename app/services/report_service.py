import io
from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.database import (
    Book,
    BookAllocation,
    BookCopy,
    DamageNotification,
    Department,
    Grade,
    Learner,
    School,
)
from app.utils.logger import logger


REPORT_TYPES = [
    "allocations",
    "book_inventory",
    "book_conditions",
    "damage_reports",
    "returns",
    "school_summary",
]


def _filter_by_date_range(query, date_column, start_date: Optional[date], end_date: Optional[date]):
    if start_date:
        query = query.filter(date_column >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(date_column <= datetime.combine(end_date, datetime.max.time()))
    return query


def generate_allocations_report(
    db: Session,
    school_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    query = db.query(
        BookAllocation.id,
        BookAllocation.book_copy_id,
        BookAllocation.learner_id,
        BookAllocation.status,
        BookAllocation.allocation_date,
        BookAllocation.return_date,
        BookAllocation.ai_condition,
        BookAllocation.ai_quality_score,
        Learner.first_name,
        Learner.last_name,
        BookCopy.qr_code,
        Book.title.label("book_title"),
        School.name.label("school_name"),
    ).join(
        Learner, BookAllocation.learner_id == Learner.id
    ).join(
        BookCopy, BookAllocation.book_copy_id == BookCopy.id
    ).join(
        Book, BookCopy.book_id == Book.id
    ).join(
        Grade, Learner.grade_id == Grade.id
    ).join(
        School, Grade.school_id == School.id
    )

    if school_id:
        query = query.filter(School.id == school_id)
    if status:
        query = query.filter(BookAllocation.status == status)
    query = _filter_by_date_range(query, BookAllocation.allocation_date, start_date, end_date)

    rows = query.all()
    df = pd.DataFrame(rows, columns=[
        "ID", "Book Copy ID", "Learner ID", "Status", "Allocation Date",
        "Return Date", "AI Condition", "AI Quality Score",
        "First Name", "Last Name", "QR Code", "Book Title", "School Name",
    ])
    return df


def generate_book_inventory_report(
    db: Session,
    school_id: Optional[int] = None,
    condition: Optional[str] = None,
) -> pd.DataFrame:
    query = db.query(
        BookCopy.id,
        BookCopy.qr_code,
        BookCopy.condition,
        Book.title.label("book_title"),
        Book.isbn,
        School.name.label("school_name"),
    ).join(
        Book, BookCopy.book_id == Book.id
    ).join(
        School, BookCopy.school_id == School.id
    )

    if school_id:
        query = query.filter(BookCopy.school_id == school_id)
    if condition:
        query = query.filter(BookCopy.condition == condition)

    rows = query.all()
    df = pd.DataFrame(rows, columns=[
        "ID", "QR Code", "Condition", "Book Title", "ISBN", "School Name",
    ])
    return df


def generate_book_conditions_report(
    db: Session,
    school_id: Optional[int] = None,
) -> pd.DataFrame:
    query = db.query(
        School.name.label("school_name"),
        BookCopy.condition,
    ).join(
        School, BookCopy.school_id == School.id
    )

    if school_id:
        query = query.filter(BookCopy.school_id == school_id)

    rows = query.all()
    df = pd.DataFrame(rows, columns=["School Name", "Condition"])

    if df.empty:
        return pd.DataFrame(columns=["School Name", "Excellent", "Good", "Fair", "Poor", "Unusable", "Total"])

    pivot = df.groupby(["School Name", "Condition"]).size().unstack(fill_value=0).reset_index()
    for col in ["excellent", "good", "fair", "poor", "unusable"]:
        if col not in pivot.columns:
            pivot[col] = 0
    pivot.columns = [c.title() if c != "School Name" else c for c in pivot.columns]
    pivot["Total"] = pivot.select_dtypes(include="number").sum(axis=1)
    return pivot


def generate_damage_reports(
    db: Session,
    school_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    query = db.query(
        DamageNotification.id,
        DamageNotification.book_copy_id,
        DamageNotification.damage_type,
        DamageNotification.description,
        DamageNotification.status,
        DamageNotification.created_at,
        BookCopy.qr_code,
        Book.title.label("book_title"),
        School.name.label("school_name"),
    ).join(
        BookCopy, DamageNotification.book_copy_id == BookCopy.id
    ).join(
        Book, BookCopy.book_id == Book.id
    ).join(
        School, BookCopy.school_id == School.id
    )

    if school_id:
        query = query.filter(School.id == school_id)
    if status:
        query = query.filter(DamageNotification.status == status)
    query = _filter_by_date_range(query, DamageNotification.created_at, start_date, end_date)

    rows = query.all()
    df = pd.DataFrame(rows, columns=[
        "ID", "Book Copy ID", "Damage Type", "Description", "Status",
        "Created At", "QR Code", "Book Title", "School Name",
    ])
    return df


def generate_returns_report(
    db: Session,
    school_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    query = db.query(
        BookAllocation.id,
        BookAllocation.book_copy_id,
        BookAllocation.learner_id,
        BookAllocation.allocation_date,
        BookAllocation.return_date,
        Learner.first_name,
        Learner.last_name,
        BookCopy.qr_code,
        Book.title.label("book_title"),
        School.name.label("school_name"),
    ).join(
        Learner, BookAllocation.learner_id == Learner.id
    ).join(
        BookCopy, BookAllocation.book_copy_id == BookCopy.id
    ).join(
        Book, BookCopy.book_id == Book.id
    ).join(
        Grade, Learner.grade_id == Grade.id
    ).join(
        School, Grade.school_id == School.id
    ).filter(
        BookAllocation.status == "returned"
    )

    if school_id:
        query = query.filter(School.id == school_id)
    query = _filter_by_date_range(query, BookAllocation.return_date, start_date, end_date)

    rows = query.all()
    df = pd.DataFrame(rows, columns=[
        "ID", "Book Copy ID", "Learner ID", "Allocation Date", "Return Date",
        "First Name", "Last Name", "QR Code", "Book Title", "School Name",
    ])
    return df


def generate_school_summary_report(
    db: Session,
    department_id: Optional[int] = None,
) -> pd.DataFrame:
    query = db.query(School)
    if department_id:
        query = query.filter(School.department_id == department_id)

    schools = query.all()
    rows = []
    for school in schools:
        total_copies = db.query(BookCopy).filter(BookCopy.school_id == school.id).count()
        active_allocations = (
            db.query(BookAllocation)
            .join(BookCopy, BookAllocation.book_copy_id == BookCopy.id)
            .filter(BookCopy.school_id == school.id, BookAllocation.status == "active")
            .count()
        )
        total_learners = (
            db.query(Learner)
            .join(Grade, Learner.grade_id == Grade.id)
            .filter(Grade.school_id == school.id)
            .count()
        )
        rows.append({
            "School Name": school.name,
            "City": school.city,
            "Total Book Copies": total_copies,
            "Active Allocations": active_allocations,
            "Total Learners": total_learners,
        })

    return pd.DataFrame(rows)


def generate_report(
    db: Session,
    report_type: str,
    school_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status: Optional[str] = None,
    condition: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    if report_type == "allocations":
        return generate_allocations_report(db, school_id, status, start_date, end_date)
    elif report_type == "book_inventory":
        return generate_book_inventory_report(db, school_id, condition)
    elif report_type == "book_conditions":
        return generate_book_conditions_report(db, school_id)
    elif report_type == "damage_reports":
        return generate_damage_reports(db, school_id, status, start_date, end_date)
    elif report_type == "returns":
        return generate_returns_report(db, school_id, start_date, end_date)
    elif report_type == "school_summary":
        return generate_school_summary_report(db, department_id)
    else:
        raise ValueError(f"Unknown report type: {report_type}")


def dataframe_to_excel(df: pd.DataFrame, sheet_name: str = "Report") -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def dataframe_to_pdf(df: pd.DataFrame, title: str = "Report") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4))
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Spacer(1, 20))

    if df.empty:
        elements.append(Paragraph("No data found for the selected filters.", styles["Normal"]))
        doc.build(elements)
        return output.getvalue()

    # Truncate long text columns
    display_df = df.copy()
    for col in display_df.columns:
        display_df[col] = display_df[col].astype(str).str[:40]

    data = [list(display_df.columns)] + display_df.values.tolist()

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D9E2F3")]),
    ]))

    elements.append(table)
    doc.build(elements)
    return output.getvalue()
