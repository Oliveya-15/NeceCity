"""
Problem service: backs City Monitor's map/list filters, Action Center's
priority list, and the problem lifecycle (`PATCH /problems/{id}/status`).
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import PROBLEM_STATUS_ORDER, ProblemStatus, ProblemType, Severity
from app.models.image import Image
from app.models.problem import Problem
from app.models.resolution import Resolution
from app.models.risk_score import RiskScore
from app.risk.engine import compute_risk


class InvalidStatusTransition(ValueError):
    pass


def list_problems(
    db: Session,
    *,
    city_id: int | None = None,
    ward_id: int | None = None,
    problem_type: ProblemType | None = None,
    severity: Severity | None = None,
    status: ProblemStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Problem], int]:
    stmt = select(Problem).options(joinedload(Problem.location), joinedload(Problem.risk_score))

    if city_id is not None:
        stmt = stmt.where(Problem.city_id == city_id)
    if ward_id is not None:
        stmt = stmt.where(Problem.ward_id == ward_id)
    if problem_type is not None:
        stmt = stmt.where(Problem.problem_type == problem_type)
    if severity is not None:
        stmt = stmt.where(Problem.severity == severity)
    if status is not None:
        stmt = stmt.where(Problem.status == status)
    if date_from is not None:
        stmt = stmt.where(Problem.first_detected_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Problem.first_detected_at <= date_to)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.execute(count_stmt).scalar_one()

    stmt = stmt.order_by(Problem.first_detected_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = list(db.execute(stmt).unique().scalars().all())
    return items, total


def list_map_problems(
    db: Session,
    *,
    city_id: int,
    ward_id: int | None = None,
    problem_types: list[ProblemType] | None = None,
    severities: list[Severity] | None = None,
    statuses: list[ProblemStatus] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Problem]:
    """
    Used by City Monitor's map: supports multi-select checkbox filters
    (several types/severities/statuses at once) and returns every match
    unpaginated, since Leaflet renders markers client-side and the dataset
    size for a minor-project city stays small enough for this to be safe
    (see app/core/config MAX_PAGE_SIZE for the equivalent guard on the
    paginated /problems endpoint used elsewhere).
    """
    stmt = select(Problem).options(joinedload(Problem.location), joinedload(Problem.risk_score)).where(
        Problem.city_id == city_id
    )
    if ward_id is not None:
        stmt = stmt.where(Problem.ward_id == ward_id)
    if problem_types:
        stmt = stmt.where(Problem.problem_type.in_(problem_types))
    if severities:
        stmt = stmt.where(Problem.severity.in_(severities))
    if statuses:
        stmt = stmt.where(Problem.status.in_(statuses))
    if date_from is not None:
        stmt = stmt.where(Problem.first_detected_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Problem.first_detected_at <= date_to)

    return list(db.execute(stmt).unique().scalars().all())


def get_problem_detail(db: Session, problem_id: int) -> Problem | None:
    from app.models.detection import Detection

    stmt = (
        select(Problem)
        .where(Problem.id == problem_id)
        .options(
            joinedload(Problem.location),
            joinedload(Problem.risk_score),
            joinedload(Problem.resolution),
            joinedload(Problem.source_detection).joinedload(Detection.image),
        )
    )
    return db.execute(stmt).unique().scalar_one_or_none()


def recompute_and_store_risk(db: Session, problem: Problem) -> RiskScore:
    result = compute_risk(db, problem)
    if problem.risk_score is None:
        problem.risk_score = RiskScore(
            problem_id=problem.id,
            score=result.score,
            components=result.components,
            reasons=result.reasons,
            weights_version=result.weights_version,
            recommended_action=result.recommended_action,
        )
        db.add(problem.risk_score)
    else:
        problem.risk_score.score = result.score
        problem.risk_score.components = result.components
        problem.risk_score.reasons = result.reasons
        problem.risk_score.weights_version = result.weights_version
        problem.risk_score.recommended_action = result.recommended_action
    return problem.risk_score


def update_problem_status(db: Session, problem: Problem, new_status: ProblemStatus, notes: str | None = None) -> Problem:
    current_idx = PROBLEM_STATUS_ORDER.index(problem.status)
    new_idx = PROBLEM_STATUS_ORDER.index(new_status)

    # Allow moving exactly one step forward (progressing normally) or one
    # step backward (correcting an accidental click) - but not arbitrary
    # jumps like detected -> resolved without passing through
    # verification/in-progress.
    if abs(new_idx - current_idx) > 1:
        raise InvalidStatusTransition(
            f"Cannot move status from '{problem.status.value}' directly to '{new_status.value}'. "
            "Problems must progress through the lifecycle one step at a time."
        )

    problem.status = new_status

    if problem.resolution is None:
        problem.resolution = Resolution(problem_id=problem.id)
        db.add(problem.resolution)

    if new_status == ProblemStatus.IN_PROGRESS and problem.resolution.started_at is None:
        problem.resolution.started_at = datetime.utcnow()
    if new_status == ProblemStatus.RESOLVED and problem.resolution.resolved_at is None:
        problem.resolution.resolved_at = datetime.utcnow()
        if problem.resolution.started_at is None:
            problem.resolution.started_at = problem.first_detected_at

    if notes:
        problem.resolution.notes = notes

    return problem


def list_priorities(db: Session, city_id: int, limit: int = 20, unresolved_only: bool = True) -> list[Problem]:
    """Top problems ranked by risk score - powers Action Center's priority list."""
    from sqlalchemy import desc

    stmt = (
        select(Problem)
        .join(RiskScore, Problem.id == RiskScore.problem_id)
        .options(joinedload(Problem.location), joinedload(Problem.risk_score))
        .where(Problem.city_id == city_id)
    )
    if unresolved_only:
        stmt = stmt.where(Problem.status != ProblemStatus.RESOLVED)
    stmt = stmt.order_by(desc(RiskScore.score)).limit(limit)
    return list(db.execute(stmt).unique().scalars().all())


def find_recent_nearby_problem(
    db: Session, city_id: int, problem_type: ProblemType, latitude: float, longitude: float, radius_m: float = 30
) -> Problem | None:
    """
    Look for an existing *unresolved* problem of the same type within
    `radius_m` metres, so a repeated detection increments recurrence
    instead of creating a duplicate Problem row.
    """
    from sqlalchemy import func
    from geoalchemy2 import Geography

    from app.models.location import Location

    stmt = (
        select(Problem)
        .join(Location, Problem.location_id == Location.id)
        .where(
            Problem.city_id == city_id,
            Problem.problem_type == problem_type,
            Problem.status != ProblemStatus.RESOLVED,
            func.ST_DWithin(
                func.cast(Location.geom, Geography),
                func.cast(func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326), Geography),
                radius_m,
            ),
        )
        .order_by(Problem.last_detected_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
