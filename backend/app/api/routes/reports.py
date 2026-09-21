from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_city_or_404
from app.db.session import get_db
from app.models.city import City
from app.schemas.report import ReportRequest
from app.services.report_service import generate_csv_export, generate_pdf_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("")
def create_report(payload: ReportRequest, db: Session = Depends(get_db)):
    city = db.get(City, payload.city_id)
    if city is None:
        raise HTTPException(status_code=404, detail=f"City {payload.city_id} not found.")

    if payload.format == "pdf":
        pdf_bytes = generate_pdf_report(db, city, days=payload.days)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="nececity_{city.slug}_report.pdf"'},
        )
    elif payload.format == "csv":
        csv_text = generate_csv_export(db, city.id, days=payload.days)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="nececity_{city.slug}_problems.csv"'},
        )
    else:
        raise HTTPException(status_code=422, detail="format must be 'pdf' or 'csv'.")
