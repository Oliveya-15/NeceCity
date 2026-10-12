from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import ProblemStatus, ProblemType, Severity
from app.models.image import Image
from app.schemas.detection import ManualProblemRequest, ManualProblemResponse
from app.schemas.problem import PaginatedProblems, ProblemDetailOut, ProblemStatusUpdate
from app.services import problem_service
from app.services.detection_service import place_or_update_problem

router = APIRouter(prefix="/problems", tags=["problems"])


def _to_list_item(p) -> dict:
    return {
        "id": p.id,
        "problem_type": p.problem_type.value,
        "severity": p.severity.value,
        "status": p.status.value,
        "latitude": p.location.latitude,
        "longitude": p.location.longitude,
        "ward_id": p.ward_id,
        "road_name": p.location.road_name,
        "recurrence_count": p.recurrence_count,
        "is_demo": p.is_demo,
        "risk_score": p.risk_score.score if p.risk_score else None,
        "first_detected_at": p.first_detected_at,
        "last_detected_at": p.last_detected_at,
    }


@router.get("", response_model=PaginatedProblems)
def list_problems(
    city_id: int | None = None,
    ward_id: int | None = None,
    problem_type: ProblemType | None = None,
    severity: Severity | None = None,
    status: ProblemStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    items, total = problem_service.list_problems(
        db, city_id=city_id, ward_id=ward_id, problem_type=problem_type, severity=severity,
        status=status, date_from=date_from, date_to=date_to, page=page, page_size=page_size,
    )
    return {"items": [_to_list_item(p) for p in items], "total": total, "page": page, "page_size": page_size}


@router.post("/manual", response_model=ManualProblemResponse)
def create_manual_problem(payload: ManualProblemRequest, db: Session = Depends(get_db)):
    """
    Inspect & Analyze's manual-entry fallback. Lets a user log a problem
    directly - with a type and severity they choose themselves - when no
    trained ML model is configured, or to record something the model
    missed. See app/services/detection_service.place_or_update_problem.
    """
    try:
        problem_type = ProblemType(payload.problem_type)
        severity = Severity(payload.severity)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    problem = place_or_update_problem(
        db,
        city_id=payload.city_id,
        problem_type=problem_type,
        severity=severity,
        latitude=payload.latitude,
        longitude=payload.longitude,
        ward_id=payload.ward_id,
        road_name=payload.road_name,
        road_importance=payload.road_importance,
        near_important_infrastructure=payload.near_important_infrastructure,
        infrastructure_note=payload.infrastructure_note,
        source_detection_id=None,
    )

    # Link the already-uploaded reference photo (if any) to this location
    # so it shows up in the problem's detail view / City Monitor panel.
    if payload.image_id is not None:
        image = db.get(Image, payload.image_id)
        if image is not None:
            image.location_id = problem.location_id

    db.commit()
    return ManualProblemResponse(problem_id=problem.id)


@router.get("/{problem_id}", response_model=ProblemDetailOut)
def get_problem(problem_id: int, db: Session = Depends(get_db)):
    problem = problem_service.get_problem_detail(db, problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail=f"Problem {problem_id} not found.")

    image_out = None
    if problem.source_detection and problem.source_detection.image:
        img = problem.source_detection.image
        image_out = {"id": img.id, "url": f"/uploads/{img.file_path.split('/')[-1]}", "source": img.source.value}
    else:
        # Manually-logged problems have no Detection, but may have a
        # reference photo linked directly via Image.location_id.
        linked_image = db.execute(
            select(Image).where(Image.location_id == problem.location_id).order_by(Image.uploaded_at.desc())
        ).scalars().first()
        if linked_image:
            image_out = {"id": linked_image.id, "url": f"/uploads/{linked_image.file_path.split('/')[-1]}", "source": linked_image.source.value}

    return {
        "id": problem.id,
        "problem_type": problem.problem_type.value,
        "severity": problem.severity.value,
        "status": problem.status.value,
        "description": problem.description,
        "recurrence_count": problem.recurrence_count,
        "is_demo": problem.is_demo,
        "location": problem.location,
        "risk": problem.risk_score,
        "image": image_out,
        "confidence": (
            problem.source_detection.confidence
            if problem.source_detection and problem.source_detection.model_version != "user-marked"
            else None
        ),
        "first_detected_at": problem.first_detected_at,
        "last_detected_at": problem.last_detected_at,
        "resolution": problem.resolution,
    }


@router.patch("/{problem_id}/status", response_model=ProblemDetailOut)
def update_status(problem_id: int, payload: ProblemStatusUpdate, db: Session = Depends(get_db)):
    problem = problem_service.get_problem_detail(db, problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail=f"Problem {problem_id} not found.")
    try:
        new_status = ProblemStatus(payload.status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status '{payload.status}'.")

    try:
        problem_service.update_problem_status(db, problem, new_status, payload.notes)
    except problem_service.InvalidStatusTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    db.commit()
    db.refresh(problem)
    return get_problem(problem_id, db)
