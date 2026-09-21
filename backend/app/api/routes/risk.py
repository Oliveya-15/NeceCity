from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import problem_service

router = APIRouter(prefix="/risk", tags=["risk"])


def _priority_item(p) -> dict:
    return {
        "id": p.id,
        "problem_type": p.problem_type.value,
        "severity": p.severity.value,
        "status": p.status.value,
        "latitude": p.location.latitude,
        "longitude": p.location.longitude,
        "road_name": p.location.road_name,
        "risk_score": p.risk_score.score if p.risk_score else 0,
        "recommended_action": p.risk_score.recommended_action if p.risk_score else None,
        "recurrence_count": p.recurrence_count,
    }


@router.get("/priorities")
def get_priorities(city_id: int, limit: int = 20, unresolved_only: bool = True, db: Session = Depends(get_db)):
    problems = problem_service.list_priorities(db, city_id, limit=limit, unresolved_only=unresolved_only)
    return [_priority_item(p) for p in problems]


@router.get("/{problem_id}")
def get_risk_detail(problem_id: int, db: Session = Depends(get_db)):
    problem = problem_service.get_problem_detail(db, problem_id)
    if problem is None or problem.risk_score is None:
        raise HTTPException(status_code=404, detail="Risk score not found for this problem.")
    return {
        "problem_id": problem.id,
        "score": problem.risk_score.score,
        "components": problem.risk_score.components,
        "reasons": problem.risk_score.reasons,
        "weights_version": problem.risk_score.weights_version,
        "recommended_action": problem.risk_score.recommended_action,
    }
