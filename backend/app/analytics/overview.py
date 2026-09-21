"""
Overview analytics for the Insights page: distribution by type, severity
and area (ward), plus a handful of deterministic "Data Insight" statements.

Per project rule 4D / 36, insight text is generated from analytics rules,
never from an LLM, and is always traceable to the numbers it describes.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ProblemType, Severity
from app.models.problem import Problem
from app.models.ward import Ward
from app.schemas.analytics import AreaCount, DataInsight, OverviewAnalyticsOut, SeverityCount, TypeCount

# A ward's share of a problem type is flagged as a notable concentration
# once it exceeds the city-wide average share by this multiple.
CONCENTRATION_THRESHOLD_MULTIPLIER = 1.5
MIN_PROBLEMS_FOR_CONCENTRATION_INSIGHT = 3


def _by_type(db: Session, city_id: int) -> list[TypeCount]:
    rows = db.execute(
        select(Problem.problem_type, func.count(Problem.id))
        .where(Problem.city_id == city_id)
        .group_by(Problem.problem_type)
        .order_by(func.count(Problem.id).desc())
    ).all()
    return [TypeCount(problem_type=t.value, count=c) for t, c in rows]


def _by_severity(db: Session, city_id: int) -> list[SeverityCount]:
    rows = db.execute(
        select(Problem.severity, func.count(Problem.id))
        .where(Problem.city_id == city_id)
        .group_by(Problem.severity)
    ).all()
    order = {s: i for i, s in enumerate(Severity)}
    rows = sorted(rows, key=lambda r: order[r[0]])
    return [SeverityCount(severity=s.value, count=c) for s, c in rows]


def _by_area(db: Session, city_id: int) -> list[AreaCount]:
    rows = db.execute(
        select(Ward.id, Ward.name, func.count(Problem.id))
        .join(Problem, Problem.ward_id == Ward.id)
        .where(Ward.city_id == city_id)
        .group_by(Ward.id, Ward.name)
        .order_by(func.count(Problem.id).desc())
    ).all()
    unassigned = db.execute(
        select(func.count(Problem.id)).where(Problem.city_id == city_id, Problem.ward_id.is_(None))
    ).scalar_one()

    areas = [AreaCount(ward_id=w_id, ward_name=name, count=c) for w_id, name, c in rows]
    if unassigned:
        areas.append(AreaCount(ward_id=None, ward_name="Unassigned area", count=unassigned))
    return areas


def _concentration_insights(db: Session, city_id: int) -> list[DataInsight]:
    """
    'Area X contains a higher concentration of <type> problems than the
    city average.' - computed by comparing each ward's share of a problem
    type against the city-wide share of that same type.
    """
    total = db.execute(select(func.count(Problem.id)).where(Problem.city_id == city_id)).scalar_one()
    if total == 0:
        return []

    city_type_counts = dict(
        db.execute(
            select(Problem.problem_type, func.count(Problem.id))
            .where(Problem.city_id == city_id)
            .group_by(Problem.problem_type)
        ).all()
    )

    ward_type_rows = db.execute(
        select(Ward.name, Problem.problem_type, func.count(Problem.id))
        .join(Problem, Problem.ward_id == Ward.id)
        .where(Ward.city_id == city_id)
        .group_by(Ward.name, Problem.problem_type)
    ).all()

    ward_totals: dict[str, int] = {}
    for ward_name, _, count in ward_type_rows:
        ward_totals[ward_name] = ward_totals.get(ward_name, 0) + count

    insights: list[DataInsight] = []
    for ward_name, problem_type, count in ward_type_rows:
        if count < MIN_PROBLEMS_FOR_CONCENTRATION_INSIGHT:
            continue
        ward_share = count / ward_totals[ward_name]
        city_share = city_type_counts.get(problem_type, 0) / total
        if city_share <= 0:
            continue
        if ward_share >= city_share * CONCENTRATION_THRESHOLD_MULTIPLIER:
            insights.append(
                DataInsight(
                    kind="concentration",
                    text=(
                        f"{ward_name} contains a higher concentration of "
                        f"{problem_type.value.replace('_', ' ')} problems "
                        f"({ward_share:.0%} of its reports) than the city average ({city_share:.0%})."
                    ),
                )
            )
    return insights[:5]


def get_overview(db: Session, city_id: int) -> OverviewAnalyticsOut:
    insights = _concentration_insights(db, city_id)
    return OverviewAnalyticsOut(
        by_type=_by_type(db, city_id),
        by_severity=_by_severity(db, city_id),
        by_area=_by_area(db, city_id),
        insights=insights,
    )
