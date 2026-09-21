def test_health_check(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_cities_empty_ok(client):
    resp = client.get("/api/v1/cities")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_city_summary_flow(client, db_session):
    from app.models.city import City

    city = City(name="Flowtown", slug="flowtown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.commit()

    resp = client.get(f"/api/v1/cities/{city.id}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["city"]["slug"] == "flowtown"
    assert data["total_problems"] == 0
    assert data["infrastructure_health_score"] == 100.0


def test_city_summary_404_for_unknown_city(client):
    resp = client.get("/api/v1/cities/999999/summary")
    assert resp.status_code == 404


def test_problems_list_filters_by_city(client, db_session):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    from app.models.city import City
    from app.models.enums import ProblemStatus, ProblemType, Severity
    from app.models.location import Location
    from app.models.problem import Problem

    city = City(name="Filtertown", slug="filtertown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.flush()

    location = Location(
        city_id=city.id, latitude=26.7, longitude=88.4,
        geom=from_shape(Point(88.4, 26.7), srid=4326),
    )
    db_session.add(location)
    db_session.flush()

    problem = Problem(
        city_id=city.id, location_id=location.id, problem_type=ProblemType.GARBAGE,
        severity=Severity.MEDIUM, status=ProblemStatus.DETECTED,
    )
    db_session.add(problem)
    db_session.commit()

    resp = client.get(f"/api/v1/problems?city_id={city.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["problem_type"] == "garbage"


def test_invalid_status_transition_rejected(client, db_session):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    from app.models.city import City
    from app.models.enums import ProblemStatus, ProblemType, Severity
    from app.models.location import Location
    from app.models.problem import Problem

    city = City(name="Statustown", slug="statustown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.flush()
    location = Location(city_id=city.id, latitude=26.7, longitude=88.4, geom=from_shape(Point(88.4, 26.7), srid=4326))
    db_session.add(location)
    db_session.flush()
    problem = Problem(
        city_id=city.id, location_id=location.id, problem_type=ProblemType.POTHOLE,
        severity=Severity.LOW, status=ProblemStatus.DETECTED,
    )
    db_session.add(problem)
    db_session.commit()

    # Jumping straight from 'detected' to 'resolved' skips verification/in-progress.
    resp = client.patch(f"/api/v1/problems/{problem.id}/status", json={"status": "resolved"})
    assert resp.status_code == 409


def test_manual_problem_creation_flow(client, db_session):
    """
    Covers the Inspect & Analyze manual-entry fallback: a problem can be
    logged directly (no Detection/ML involved) and immediately gets a
    computed, explainable risk score.
    """
    from app.models.city import City

    city = City(name="Manualtown", slug="manualtown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.commit()

    resp = client.post(
        "/api/v1/problems/manual",
        json={
            "problem_type": "pothole", "severity": "high",
            "latitude": 26.71, "longitude": 88.41, "city_id": city.id,
            "road_name": "Manual Test Road",
        },
    )
    assert resp.status_code == 200
    problem_id = resp.json()["problem_id"]

    detail = client.get(f"/api/v1/problems/{problem_id}").json()
    assert detail["problem_type"] == "pothole"
    assert detail["severity"] == "high"
    assert detail["risk"] is not None
    assert detail["risk"]["score"] > 0
    assert len(detail["risk"]["reasons"]) > 0


def test_manual_problem_rejects_invalid_type(client, db_session):
    from app.models.city import City

    city = City(name="Badtypetown", slug="badtypetown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.commit()

    resp = client.post(
        "/api/v1/problems/manual",
        json={"problem_type": "not_a_real_type", "severity": "high", "latitude": 26.7, "longitude": 88.4, "city_id": city.id},
    )
    assert resp.status_code == 422


def test_recommendations_returns_real_organizations_with_working_urls(client, db_session):
    """
    Every organization returned must have a name and an https(s) website -
    this is a starter directory of real, verifiable organizations, never
    fabricated contact details (see app/services/recommendation_service.py).
    """
    from app.models.city import City

    city = City(name="Advicetown", slug="advicetown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.commit()

    resp = client.get(f"/api/v1/recommendations?city_id={city.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["all_organizations"]) >= 5
    assert len(data["tips"]) >= 3
    for org in data["all_organizations"]:
        assert org["website"].startswith("http")
        assert len(org["name"]) > 0


def test_recommendations_city_insights_reflect_real_data(client, db_session):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    from app.models.city import City
    from app.models.enums import ProblemStatus, ProblemType, Severity
    from app.models.location import Location
    from app.models.problem import Problem

    city = City(name="Insighttown", slug="insighttown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db_session.add(city)
    db_session.flush()
    for _ in range(3):
        loc = Location(city_id=city.id, latitude=26.7, longitude=88.4, geom=from_shape(Point(88.4, 26.7), srid=4326))
        db_session.add(loc)
        db_session.flush()
        db_session.add(Problem(
            city_id=city.id, location_id=loc.id, problem_type=ProblemType.GARBAGE,
            severity=Severity.MEDIUM, status=ProblemStatus.DETECTED,
        ))
    db_session.commit()

    resp = client.get(f"/api/v1/recommendations?city_id={city.id}")
    data = resp.json()
    assert any("garbage" in insight.lower() for insight in data["city_insights"])
    org_names = [o["name"] for o in data["recommended_organizations"]]
    # A garbage-heavy city should surface sanitation-relevant organizations.
    assert any("Sulabh" in n or "Waste Warriors" in n for n in org_names)
