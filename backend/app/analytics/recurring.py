from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import ProblemStatus
from app.models.problem import Problem
from app.schemas.analytics import RecurringProblemOut

RECURRENCE_THRESHOLD = 2  # a problem detected 2+ times is "recurring"


def get_recurring_problems(db: Session, city_id: int, limit: int = 20) -> list[RecurringProblemOut]:
    rows = db.execute(
        select(Problem)
        .options(joinedload(Problem.location))
        .where(
            Problem.city_id == city_id,
            Problem.recurrence_count >= RECURRENCE_THRESHOLD,
            Problem.status != ProblemStatus.RESOLVED,
        )
        .order_by(Problem.recurrence_count.desc())
        .limit(limit)
    ).unique().scalars().all()

    return [
        RecurringProblemOut(
            problem_id=p.id,
            problem_type=p.problem_type.value,
            latitude=p.location.latitude,
            longitude=p.location.longitude,
            recurrence_count=p.recurrence_count,
            road_name=p.location.road_name,
        )
        for p in rows
    ]
