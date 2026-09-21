from datetime import datetime

from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.models.city import City
from app.models.enums import ProblemStatus, ProblemType, RoadImportance, Severity
from app.models.location import Location
from app.models.problem import Problem
from app.risk.config import get_risk_weights
from app.risk.engine import compute_risk


def test_risk_weights_sum_to_one():
    weights = get_risk_weights()
    total = sum(weights.as_dict().values())
    assert 0.99 <= total <= 1.01


def _make_problem(db_session, *, severity, road_importance, near_infra, recurrence=1) -> Problem:
    city = City(name="Test City", slug=f"test-city-{datetime.utcnow().timestamp()}", state="West Bengal",
                center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.flush()

    location = Location(
        city_id=city.id, latitude=26.7271, longitude=88.3953,
        geom=from_shape(Point(88.3953, 26.7271), srid=4326),
        road_importance=road_importance, near_important_infrastructure=near_infra,
    )
    db_session.add(location)
    db_session.flush()

    problem = Problem(
        city_id=city.id, location_id=location.id, problem_type=ProblemType.POTHOLE,
        severity=severity, status=ProblemStatus.DETECTED, recurrence_count=recurrence,
    )
    db_session.add(problem)
    db_session.flush()
    db_session.refresh(problem)
    return problem


def test_critical_severity_scores_higher_than_low(db_session):
    low = _make_problem(db_session, severity=Severity.LOW, road_importance=RoadImportance.LOCAL, near_infra=False)
    critical = _make_problem(db_session, severity=Severity.CRITICAL, road_importance=RoadImportance.LOCAL, near_infra=False)

    low_result = compute_risk(db_session, low)
    critical_result = compute_risk(db_session, critical)

    assert critical_result.score > low_result.score


def test_score_is_bounded_0_to_100(db_session):
    problem = _make_problem(
        db_session, severity=Severity.CRITICAL, road_importance=RoadImportance.HIGHWAY,
        near_infra=True, recurrence=10,
    )
    result = compute_risk(db_session, problem)
    assert 0 <= result.score <= 100


def test_reasons_mention_high_severity(db_session):
    problem = _make_problem(db_session, severity=Severity.CRITICAL, road_importance=RoadImportance.LOCAL, near_infra=False)
    result = compute_risk(db_session, problem)
    assert any("severity" in r.lower() for r in result.reasons)


def test_components_sum_to_score(db_session):
    problem = _make_problem(db_session, severity=Severity.HIGH, road_importance=RoadImportance.ARTERIAL, near_infra=True)
    result = compute_risk(db_session, problem)
    total_contribution = sum(c["contribution"] for c in result.components.values())
    assert abs(total_contribution - result.score) < 0.1
