"""
City-level service functions. Backs `GET /cities` and `GET
/cities/{id}/summary` (the Command Center's primary data source).

All numbers here come from real SQL aggregate queries against the
database - nothing on the Command Center is hard-coded (project rule 4A).
"""
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.city import City
from app.models.enums import ProblemStatus, ProblemType, Severity
from app.models.problem import Problem

# Deterministic, documented penalty weights for the infrastructure health
# score - a weighted-scoring formula, not a random or fabricated number.
_SEVERITY_PENALTY = {
    Severity.LOW: 5,
    Severity.MEDIUM: 15,
    Severity.HIGH: 30,
    Severity.CRITICAL: 50,
}


def list_cities(db: Session, active_only: bool = True) -> list[City]:
    stmt = select(City)
    if active_only:
        stmt = stmt.where(City.is_active.is_(True))
    stmt = stmt.order_by(City.name)
    return list(db.execute(stmt).scalars().all())


def get_city(db: Session, city_id: int) -> City | None:
    return db.get(City, city_id)


def get_city_by_slug(db: Session, slug: str) -> City | None:
    return db.execute(select(City).where(City.slug == slug)).scalar_one_or_none()


def _health_label(score: float) -> str:
    if score >= 80:
        return "Good"
    if score >= 60:
        return "Fair"
    if score >= 40:
        return "Poor"
    return "Critical"


def get_city_summary(db: Session, city: City) -> dict:
    base = select(Problem).where(Problem.city_id == city.id)

    total_problems = db.execute(
        select(func.count(Problem.id)).where(Problem.city_id == city.id)
    ).scalar_one()

    severity_counts = dict(
        db.execute(
            select(Problem.severity, func.count(Problem.id))
            .where(Problem.city_id == city.id)
            .group_by(Problem.severity)
        ).all()
    )
    severity_breakdown = {
        s.value: severity_counts.get(s, 0) for s in Severity
    }

    status_counts = dict(
        db.execute(
            select(Problem.status, func.count(Problem.id))
            .where(Problem.city_id == city.id)
            .group_by(Problem.status)
        ).all()
    )
    status_breakdown = {s.value: status_counts.get(s, 0) for s in ProblemStatus}

    type_counts = dict(
        db.execute(
            select(Problem.problem_type, func.count(Problem.id))
            .where(Problem.city_id == city.id)
            .group_by(Problem.problem_type)
        ).all()
    )
    type_breakdown = {t.value: type_counts.get(t, 0) for t in ProblemType}

    resolved = status_breakdown[ProblemStatus.RESOLVED.value]
    unresolved = total_problems - resolved

    # Infrastructure health: 100 minus the average severity penalty across
    # currently unresolved problems. An empty city (no unresolved problems)
    # scores a perfect 100.
    unresolved_severity_rows = db.execute(
        select(Problem.severity)
        .where(Problem.city_id == city.id, Problem.status != ProblemStatus.RESOLVED)
    ).scalars().all()

    if unresolved_severity_rows:
        avg_penalty = sum(_SEVERITY_PENALTY[s] for s in unresolved_severity_rows) / len(unresolved_severity_rows)
        # Scale by how much of the city is affected, capped so one issue
        # in a huge city doesn't tank the score, and severity still matters
        # even for a small number of affected points.
        volume_factor = min(len(unresolved_severity_rows) / 25, 1.0)
        health_score = max(0.0, 100 - avg_penalty * (0.4 + 0.6 * volume_factor))
    else:
        health_score = 100.0

    has_demo_data = db.execute(
        select(func.count(Problem.id)).where(Problem.city_id == city.id, Problem.is_demo.is_(True))
    ).scalar_one() > 0

    return {
        "city": city,
        "total_problems": total_problems,
        "critical_problems": severity_breakdown[Severity.CRITICAL.value],
        "high_priority_problems": severity_breakdown[Severity.HIGH.value],
        "resolved_problems": resolved,
        "unresolved_problems": unresolved,
        "severity_breakdown": severity_breakdown,
        "status_breakdown": status_breakdown,
        "problem_type_breakdown": type_breakdown,
        "infrastructure_health_score": round(health_score, 1),
        "infrastructure_health_label": _health_label(health_score),
        "has_demo_data": has_demo_data,
    }
