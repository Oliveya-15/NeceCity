"""
NeceCity demo/seed data generator.

Populates the database with:
  - All 8 configured West Bengal cities (so the "add a new city without
    rewriting code" architecture claim is demonstrable).
  - Realistic ward/area names for the two demo-rich cities (Siliguri,
    Kolkata) so City Monitor's ward filter and Insights' area breakdown
    have something meaningful to show.
  - A deterministic (seeded) set of demo Problems across all 6 classes,
    all 4 severities, all 4 lifecycle statuses, spread over the last 60
    days, including some recurring problems and some near "important
    infrastructure" - specifically so every Command Center / City Monitor
    / Insights / Action Center widget has non-empty, varied data to show
    in a live demo.

Every row created here has `is_demo=True` (problems) or `source=DEMO`
(images) so the UI can clearly label it and it can be trivially wiped and
replaced with real data later (see docs/dataset.md).

Run with:  python -m app.seed.seed_data [--reset]
"""
import argparse
import random
from datetime import datetime, timedelta

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal, engine
from app.models.city import City
from app.models.enums import ProblemStatus, ProblemType, RoadImportance, Severity
from app.models.location import Location
from app.models.problem import Problem
from app.models.resolution import Resolution
from app.models.ward import Ward
from app.services.problem_service import recompute_and_store_risk

logger = get_logger(__name__)

RNG_SEED = 42

# name, state, lat, lng, default_zoom
CITIES = [
    ("Siliguri", "West Bengal", 26.7271, 88.3953, 13),
    ("Kolkata", "West Bengal", 22.5726, 88.3639, 12),
    ("Asansol", "West Bengal", 23.6739, 86.9524, 13),
    ("Durgapur", "West Bengal", 23.5204, 87.3119, 13),
    ("Howrah", "West Bengal", 22.5958, 88.2636, 13),
    ("Kharagpur", "West Bengal", 22.3460, 87.2320, 13),
    ("Bardhaman", "West Bengal", 23.2324, 87.8615, 13),
    ("Jalpaiguri", "West Bengal", 26.5416, 88.7195, 13),
]

WARDS_BY_CITY = {
    "siliguri": ["Hakimpara", "Pradhan Nagar", "Bidhannagar", "Champasari", "Matigara", "Venus More", "Khalpara", "Ashram Para"],
    "kolkata": ["Park Street", "Salt Lake", "Behala", "Gariahat", "Esplanade", "Jadavpur", "Dum Dum", "Tollygunge"],
}

INFRASTRUCTURE_NOTES = [
    "District Hospital", "Government School", "City Bus Terminus", "Railway Station Approach", "Municipal Market",
]

# Roughly how common each problem type is in a typical mid-sized Indian city dataset.
PROBLEM_TYPE_WEIGHTS = {
    ProblemType.POTHOLE: 30,
    ProblemType.ROAD_DAMAGE: 20,
    ProblemType.GARBAGE: 20,
    ProblemType.WATERLOGGING: 12,
    ProblemType.OPEN_DRAIN: 10,
    ProblemType.DAMAGED_ROAD_SIGN: 8,
}
SEVERITY_WEIGHTS = {Severity.LOW: 25, Severity.MEDIUM: 35, Severity.HIGH: 25, Severity.CRITICAL: 15}
STATUS_WEIGHTS = {
    ProblemStatus.DETECTED: 35, ProblemStatus.VERIFIED: 20,
    ProblemStatus.IN_PROGRESS: 15, ProblemStatus.RESOLVED: 30,
}
ROAD_IMPORTANCE_WEIGHTS = {RoadImportance.LOCAL: 55, RoadImportance.ARTERIAL: 35, RoadImportance.HIGHWAY: 10}


def _weighted_choice(rng: random.Random, weights: dict):
    items = list(weights.keys())
    probs = list(weights.values())
    return rng.choices(items, weights=probs, k=1)[0]


def _random_point_near(rng: random.Random, lat: float, lng: float, radius_km: float = 6.0) -> tuple[float, float]:
    # Uniform-ish random offset within a small square (good enough for demo
    # data - not intended to be a precise areal sampling method).
    delta_lat = (rng.uniform(-1, 1)) * (radius_km / 111.0)
    delta_lng = (rng.uniform(-1, 1)) * (radius_km / (111.0 * 0.9))
    return round(lat + delta_lat, 6), round(lng + delta_lng, 6)


def _reset(db: Session) -> None:
    logger.warning("Resetting all demo/application data (--reset).")
    db.query(Resolution).delete()
    from app.models.risk_score import RiskScore
    from app.models.detection import Detection
    from app.models.image import Image
    db.query(RiskScore).delete()
    db.query(Problem).delete()
    db.query(Detection).delete()
    db.query(Image).delete()
    db.query(Location).delete()
    db.query(Ward).delete()
    db.query(City).delete()
    db.commit()


def seed_cities(db: Session) -> dict[str, City]:
    cities = {}
    for name, state, lat, lng, zoom in CITIES:
        slug = name.lower().replace(" ", "-")
        existing = db.query(City).filter_by(slug=slug).one_or_none()
        if existing:
            cities[slug] = existing
            continue
        city = City(name=name, slug=slug, state=state, center_latitude=lat, center_longitude=lng, default_zoom=zoom)
        db.add(city)
        cities[slug] = city
    db.flush()
    return cities


def seed_wards(db: Session, cities: dict[str, City]) -> dict[str, list[Ward]]:
    wards_by_city = {}
    for slug, ward_names in WARDS_BY_CITY.items():
        city = cities[slug]
        wards = []
        for name in ward_names:
            w = Ward(city_id=city.id, name=name)
            db.add(w)
            wards.append(w)
        wards_by_city[slug] = wards
    db.flush()
    return wards_by_city


def _jitter_point(rng: random.Random, lat: float, lng: float, max_meters: float) -> tuple[float, float]:
    """Small random offset in metres, converted to degrees - used to keep
    hotspot-cluster points close together but not perfectly identical."""
    delta_lat = rng.uniform(-max_meters, max_meters) / 111_000
    delta_lng = rng.uniform(-max_meters, max_meters) / (111_000 * 0.9)
    return round(lat + delta_lat, 6), round(lng + delta_lng, 6)


def seed_problems(db: Session, rng: random.Random, city: City, wards: list[Ward], count: int) -> None:
    now = datetime.utcnow()

    # A handful of fixed "hotspot" centres per city: real-world recurring
    # problem areas (e.g. a chronically flooding junction, a market with
    # persistent garbage) tend to cluster tightly rather than being
    # uniformly scattered. ~30% of demo problems land near one of these
    # centres (jittered by up to 60m) so DBSCAN hotspot detection and the
    # "recurring problem" insight both have something real to find; the
    # rest are scattered city-wide as background "noise" points.
    hotspot_centers = [_random_point_near(rng, city.center_latitude, city.center_longitude, radius_km=4.0) for _ in range(5)]

    for i in range(count):
        use_hotspot = rng.random() < 0.30
        if use_hotspot:
            center_lat, center_lng = rng.choice(hotspot_centers)
            lat, lng = _jitter_point(rng, center_lat, center_lng, max_meters=60)
            ptype = _weighted_choice(rng, PROBLEM_TYPE_WEIGHTS)
        else:
            lat, lng = _random_point_near(rng, city.center_latitude, city.center_longitude)
            ptype = _weighted_choice(rng, PROBLEM_TYPE_WEIGHTS)

        ward = rng.choice(wards) if wards and rng.random() < 0.85 else None
        road_importance = _weighted_choice(rng, ROAD_IMPORTANCE_WEIGHTS)
        near_infra = rng.random() < 0.15

        location = Location(
            city_id=city.id,
            ward_id=ward.id if ward else None,
            latitude=lat,
            longitude=lng,
            geom=from_shape(Point(lng, lat), srid=4326),
            road_name=f"{rng.choice(['MG Road', 'Station Road', 'Hill Cart Road', 'Sevoke Road', 'Bypass Road', 'Ward Lane'])} #{i+1}",
            road_importance=road_importance,
            near_important_infrastructure=near_infra,
            infrastructure_note=rng.choice(INFRASTRUCTURE_NOTES) if near_infra else None,
        )
        db.add(location)
        db.flush()

        severity = _weighted_choice(rng, SEVERITY_WEIGHTS)
        status = _weighted_choice(rng, STATUS_WEIGHTS)
        days_ago = rng.randint(0, 60)
        first_detected = now - timedelta(days=days_ago, hours=rng.randint(0, 23))
        # Hotspot-cluster problems are more likely to represent a recurring
        # issue at that location.
        recurrence = rng.choice([2, 3, 4, 5]) if use_hotspot and rng.random() < 0.5 else 1

        problem = Problem(
            city_id=city.id,
            ward_id=ward.id if ward else None,
            location_id=location.id,
            problem_type=ptype,
            severity=severity,
            status=status,
            recurrence_count=recurrence,
            is_demo=True,
            first_detected_at=first_detected,
            last_detected_at=first_detected + timedelta(days=rng.randint(0, min(days_ago, 5))),
        )
        db.add(problem)
        db.flush()

        if status in (ProblemStatus.IN_PROGRESS, ProblemStatus.RESOLVED):
            started = first_detected + timedelta(days=rng.randint(1, 5))
            resolution = Resolution(problem_id=problem.id, started_at=started)
            if status == ProblemStatus.RESOLVED:
                resolution.resolved_at = started + timedelta(hours=rng.randint(4, 96))
                resolution.notes = "Resolved by municipal maintenance crew (demo record)."
            db.add(resolution)

        db.flush()
        recompute_and_store_risk(db, problem)


def run_seed(reset: bool = False) -> None:
    rng = random.Random(RNG_SEED)
    db = SessionLocal()
    try:
        if reset:
            _reset(db)

        cities = seed_cities(db)
        wards_by_city = seed_wards(db, cities)
        db.commit()

        existing_problem_count = db.query(Problem).count()
        if existing_problem_count > 0:
            logger.info("Problems already seeded (%d rows) - skipping. Use --reset to regenerate.", existing_problem_count)
            return

        seed_problems(db, rng, cities["siliguri"], wards_by_city["siliguri"], count=55)
        seed_problems(db, rng, cities["kolkata"], wards_by_city["kolkata"], count=45)
        db.commit()

        logger.info("Demo data seeded: %d cities, %d problems.", len(cities), db.query(Problem).count())
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed NeceCity demo data.")
    parser.add_argument("--reset", action="store_true", help="Wipe existing data before seeding.")
    args = parser.parse_args()

    configure_logging("development")
    run_seed(reset=args.reset)
