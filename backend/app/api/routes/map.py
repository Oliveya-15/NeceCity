from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import ProblemStatus, ProblemType, Severity
from app.services import problem_service

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/problems")
def map_problems(
    city_id: int,
    ward_id: int | None = None,
    problem_type: list[ProblemType] | None = Query(default=None),
    severity: list[Severity] | None = Query(default=None),
    status: list[ProblemStatus] | None = Query(default=None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
):
    problems = problem_service.list_map_problems(
        db, city_id=city_id, ward_id=ward_id, problem_types=problem_type, severities=severity,
        statuses=status, date_from=date_from, date_to=date_to,
    )
    return [
        {
            "id": p.id,
            "problem_type": p.problem_type.value,
            "severity": p.severity.value,
            "status": p.status.value,
            "latitude": p.location.latitude,
            "longitude": p.location.longitude,
            "ward_id": p.ward_id,
            "road_name": p.location.road_name,
            "risk_score": p.risk_score.score if p.risk_score else None,
            "recurrence_count": p.recurrence_count,
            "last_detected_at": p.last_detected_at,
        }
        for p in problems
    ]
