"""
The NeceCity risk engine.

This is a **deterministic, weighted-scoring** model - not a machine-learning
model and not a random number. Every factor is documented, every weight is
configurable (see `app.risk.config`), and every computed score can be
traced back to exactly which factors drove it (see `RiskResult.components`).

Score = 100 * sum(weight_i * raw_score_i) for i in
    {severity, recurrence, density, road_importance, infrastructure}

Each raw_score_i is normalized to [0, 1] before weighting, so the final
score is naturally bounded to [0, 100].
"""
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from geoalchemy2 import Geography

from app.models.location import Location
from app.models.problem import Problem
from app.risk.config import (
    DENSITY_RADIUS_METERS,
    DENSITY_SATURATION_COUNT,
    INFRASTRUCTURE_NO_PROXIMITY_RAW_SCORE,
    INFRASTRUCTURE_PROXIMITY_RAW_SCORE,
    RECURRENCE_SATURATION_COUNT,
    ROAD_IMPORTANCE_RAW_SCORE,
    SEVERITY_RAW_SCORE,
    WEIGHTS_VERSION,
    get_risk_weights,
)


@dataclass
class RiskResult:
    score: float
    components: dict
    weights_version: str
    recommended_action: str
    reasons: list[str]


def _nearby_problem_count(db: Session, problem: Problem) -> int:
    """
    Count *other* open problems within DENSITY_RADIUS_METERS of this
    problem's location, using a real PostGIS geography distance query
    (ST_DWithin) rather than a naive lat/lng bounding box.
    """
    location = problem.location
    # Geometries are cast to `geography` so ST_DWithin measures real metres
    # on the earth's surface rather than raw coordinate degrees.
    nearby_stmt = (
        select(func.count(Problem.id))
        .join(Location, Problem.location_id == Location.id)
        .where(
            Problem.id != problem.id,
            Problem.city_id == problem.city_id,
            func.ST_DWithin(
                func.cast(Location.geom, Geography),
                func.cast(
                    func.ST_SetSRID(func.ST_MakePoint(location.longitude, location.latitude), 4326),
                    Geography,
                ),
                DENSITY_RADIUS_METERS,
            ),
        )
    )
    return db.execute(nearby_stmt).scalar_one()


def _recommended_action(score: float, problem: Problem) -> str:
    if score >= 80:
        urgency = "Immediate action required. Dispatch a repair crew within 24-48 hours."
    elif score >= 60:
        urgency = "High priority. Schedule repair within the next 7 days."
    elif score >= 40:
        urgency = "Moderate priority. Include in the next routine maintenance cycle (within 30 days)."
    else:
        urgency = "Low priority. Monitor; address during periodic maintenance."
    return urgency


def _reasons(components: dict, problem: Problem, nearby_count: int) -> list[str]:
    reasons: list[str] = []
    if components["severity"]["raw"] >= 0.75:
        reasons.append(f"High severity ({problem.severity.value}) issue.")
    if problem.recurrence_count >= 3:
        reasons.append(f"Recurring issue - detected {problem.recurrence_count} times at this location.")
    if nearby_count >= 2:
        reasons.append(f"{nearby_count} other unresolved problems within {DENSITY_RADIUS_METERS}m.")
    if components["road_importance"]["raw"] >= 0.70:
        reasons.append(f"Located on a {problem.location.road_importance.value} road.")
    if components["infrastructure"]["raw"] > 0:
        note = problem.location.infrastructure_note or "important infrastructure"
        reasons.append(f"Near {note}.")
    if not reasons:
        reasons.append("No elevated risk factors identified; routine-priority issue.")
    return reasons


def compute_risk(db: Session, problem: Problem) -> RiskResult:
    """
    Compute the explainable risk score for a single Problem. Requires
    `problem.location` to be loaded (it is a required FK, never null).
    """
    weights = get_risk_weights()
    location = problem.location

    severity_raw = SEVERITY_RAW_SCORE[problem.severity]
    recurrence_raw = min(problem.recurrence_count / RECURRENCE_SATURATION_COUNT, 1.0)
    nearby_count = _nearby_problem_count(db, problem)
    density_raw = min(nearby_count / DENSITY_SATURATION_COUNT, 1.0)
    road_importance_raw = ROAD_IMPORTANCE_RAW_SCORE[location.road_importance]
    infrastructure_raw = (
        INFRASTRUCTURE_PROXIMITY_RAW_SCORE
        if location.near_important_infrastructure
        else INFRASTRUCTURE_NO_PROXIMITY_RAW_SCORE
    )

    raw_scores = {
        "severity": severity_raw,
        "recurrence": recurrence_raw,
        "density": density_raw,
        "road_importance": road_importance_raw,
        "infrastructure": infrastructure_raw,
    }
    weight_map = weights.as_dict()

    components = {}
    total = 0.0
    for factor, raw in raw_scores.items():
        weight = weight_map[factor]
        contribution = round(raw * weight * 100, 2)
        components[factor] = {"raw": round(raw, 2), "weight": weight, "contribution": contribution}
        total += contribution

    score = round(min(total, 100.0), 1)
    reasons = _reasons(components, problem, nearby_count)

    return RiskResult(
        score=score,
        components=components,
        weights_version=WEIGHTS_VERSION,
        recommended_action=_recommended_action(score, problem),
        reasons=reasons,
    )
