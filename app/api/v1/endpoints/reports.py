from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.database.session import get_db
from app.services.report_service import (
    REPORT_TYPES,
    dataframe_to_excel,
    dataframe_to_pdf,
    generate_report,
)

router = APIRouter(prefix="/reports", tags=["reports"])

VALID_FORMATS = ["pdf", "excel"]


@router.get("/types")
def get_report_types():
    return {
        "report_types": [
            {"type": "allocations", "description": "Book allocations with learner and book details"},
            {"type": "book_inventory", "description": "All book copies with condition and school"},
            {"type": "book_conditions", "description": "Book condition summary per school"},
            {"type": "damage_reports", "description": "Damage notifications with details"},
            {"type": "returns", "description": "Returned books with dates and learner info"},
            {"type": "school_summary", "description": "School overview with totals"},
        ],
        "formats": ["pdf", "excel"],
    }


@router.get("/generate")
def generate_report_endpoint(
    report_type: str = Query(..., description="Type of report to generate"),
    format: str = Query("excel", description="Output format: pdf or excel"),
    school_id: Optional[int] = Query(None, description="Filter by school"),
    department_id: Optional[int] = Query(None, description="Filter by department (school_summary only)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    condition: Optional[str] = Query(None, description="Filter by condition (book_inventory only)"),
    start_date: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    if report_type not in REPORT_TYPES:
        raise ValidationError(
            detail=f"Invalid report_type '{report_type}'. Valid types: {', '.join(REPORT_TYPES)}"
        )

    if format not in VALID_FORMATS:
        raise ValidationError(
            detail=f"Invalid format '{format}'. Valid formats: pdf, excel"
        )

    df = generate_report(
        db=db,
        report_type=report_type,
        school_id=school_id,
        department_id=department_id,
        status=status,
        condition=condition,
        start_date=start_date,
        end_date=end_date,
    )

    title = report_type.replace("_", " ").title()
    filename = f"{report_type}_{date.today().isoformat()}"

    if format == "excel":
        content = dataframe_to_excel(df, sheet_name=title)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"},
        )
    else:
        content = dataframe_to_pdf(df, title=title)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}.pdf"},
        )
