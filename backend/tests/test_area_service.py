"""
Tests for place resolution in the AI Recommendations chat.

The pure-function tests need no database. The DB-backed tests use the same
Postgres test database as the other API tests (see conftest.py) and disable
the geocoder so nothing touches the network.
"""
import pytest

from app.services import area_service as A


# ---- pure helpers -------------------------------------------------------- #
def test_strip_demo_suffix():
    assert A.strip_demo_suffix("Sevoke Road #12") == "Sevoke Road"
    assert A.strip_demo_suffix("Hill Cart Road") == "Hill Cart Road"


def test_name_variants_split_on_commas():
    v = A.name_variants("Sevoke Road, near City Bus Terminus")
    assert "sevoke road" in v and "city bus terminus" in v


@pytest.mark.parametrize("message,expected", [
    ("tell me does kestopur have any infra issues", "kestopur"),
    ("what issues are there in Sevoke Road?", "sevoke road"),
    ("potholes near Salt Lake Sector 5", "salt lake sector 5"),
    ("sevoke road problems", "sevoke road"),
])
def test_extract_place_candidates(message, expected):
    assert expected in A.extract_place_candidates(message, "Kolkata")


@pytest.mark.parametrize("message", [
    "what's the biggest problem in my city?",
    "who can help with garbage collection?",
    "How do I report a pothole?",
    "problems in Kolkata",
])
def test_city_wide_questions_yield_no_place(message):
    assert A.extract_place_candidates(message, "Kolkata") == []


def test_match_known_name_exact_and_typo():
    known = {"sevoke road": 1, "hill cart road": 2, "park street": 3}
    assert A.match_known_name("issues on sevoke road?", known) == "sevoke road"
    assert A.match_known_name("any problem at sevok road", known) == "sevoke road"
    assert A.match_known_name("how do risk scores work", known) is None


def test_longest_known_name_wins():
    known = {"station road": 1, "railway station road": 2}
    assert A.match_known_name("potholes on railway station road", known) == "railway station road"


def test_haversine_known_distance():
    # ~111.2 km per degree of latitude
    assert abs(A.haversine_m(22.0, 88.0, 23.0, 88.0) - 111_195) < 500


def test_area_intent_gate():
    assert A.has_area_intent("any potholes in Kestopur")
    assert not A.has_area_intent("hello there")


# ---- database-backed ------------------------------------------------------ #
def _make_city_with_problems(db):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    from app.models.city import City
    from app.models.enums import ProblemStatus, ProblemType, Severity
    from app.models.location import Location
    from app.models.problem import Problem
    from app.models.ward import Ward

    city = City(name="Areatown", slug="areatown", state="West Bengal", center_latitude=26.7, center_longitude=88.4)
    db.add(city)
    db.flush()
    ward = Ward(city_id=city.id, name="Kestopur")
    db.add(ward)
    db.flush()

    def add(lat, lon, road, ptype, sev, ward_id=None):
        loc = Location(city_id=city.id, ward_id=ward_id, latitude=lat, longitude=lon,
                       geom=from_shape(Point(lon, lat), srid=4326), road_name=road)
        db.add(loc)
        db.flush()
        db.add(Problem(city_id=city.id, ward_id=ward_id, location_id=loc.id, problem_type=ptype,
                       severity=sev, status=ProblemStatus.VERIFIED, is_demo=False))
        db.flush()

    add(26.700, 88.400, "Sevoke Road #1", ProblemType.POTHOLE, Severity.HIGH)
    add(26.701, 88.401, "Sevoke Road #2", ProblemType.GARBAGE, Severity.LOW)
    add(26.720, 88.420, "Other Road", ProblemType.OPEN_DRAIN, Severity.CRITICAL, ward_id=ward.id)
    db.commit()
    return city


def test_lookup_by_road_name(db_session, monkeypatch):
    monkeypatch.setattr(A, "geocode_place", lambda *a, **k: None)
    city = _make_city_with_problems(db_session)
    res = A.lookup_area(db_session, city, "what issues are there in sevoke road")
    assert res.summary is not None
    assert res.summary.total == 2
    assert res.summary.by_type == {"pothole": 1, "garbage": 1}


def test_lookup_by_ward_name(db_session, monkeypatch):
    monkeypatch.setattr(A, "geocode_place", lambda *a, **k: None)
    city = _make_city_with_problems(db_session)
    res = A.lookup_area(db_session, city, "does kestopur have any infra issues")
    assert res.summary is not None and res.summary.method == "ward"
    assert res.summary.total == 1 and res.summary.by_severity == {"critical": 1}


def test_lookup_geocoded_radius(db_session, monkeypatch):
    city = _make_city_with_problems(db_session)
    monkeypatch.setattr(A, "geocode_place", lambda phrase, c: (26.7005, 88.4005, "Somewhere", 1000))
    res = A.lookup_area(db_session, city, "any potholes near Unknownpara")
    assert res.summary is not None and res.summary.method == "geocoded"
    assert res.summary.total == 2  # the far-away drain is outside 1 km


def test_unlocatable_place_is_reported_honestly(db_session, monkeypatch):
    monkeypatch.setattr(A, "geocode_place", lambda *a, **k: None)
    city = _make_city_with_problems(db_session)
    res = A.lookup_area(db_session, city, "any issues in Nowhereville")
    assert res.summary is None and res.unresolved_phrase == "nowhereville"
    assert "couldn't locate" in A.area_reply_text(city, res)


def test_chat_endpoint_answers_area_question(client, db_session, monkeypatch):
    monkeypatch.setattr(A, "geocode_place", lambda *a, **k: None)
    city = _make_city_with_problems(db_session)
    resp = client.post("/api/v1/chat", json={"city_id": city.id, "message": "what issues are on sevoke road?", "history": []})
    assert resp.status_code == 200
    assert "2 reported problems" in resp.json()["reply"]


# ---- city knowledge / chat formatting ------------------------------------- #
from app.services import city_knowledge as K  # noqa: E402
from app.services.chat_service import clean_llm_text  # noqa: E402


def test_clean_llm_text_removes_html_breaks_and_odd_hyphens():
    out = clean_llm_text("• Road damage – 3  <br>• Garbage – 2<br/>Critical\u2011severity")
    assert "<br" not in out and "\u2011" not in out
    assert out.count("\n") == 2


def test_parse_filters_critical_with_nonbreaking_hyphen():
    f = K.parse_filters("what are the Critical\u2011severity issues")
    assert f.severities == ["critical"] and f.active


def test_parse_filters_type_status_ward_and_sort():
    f = K.parse_filters("oldest unresolved potholes in park street", {"park street": 7})
    assert f.types == ["pothole"] and f.open_only and f.ward_id == 7 and f.sort == "oldest"


def test_parse_filters_ignores_general_questions():
    assert not K.parse_filters("how do risk scores work").active
    assert not K.parse_filters("tell me about sevoke road").active


def test_snapshot_lists_critical_problems_with_locations(db_session, monkeypatch):
    city = _make_city_with_problems(db_session)
    snap = K.build_city_snapshot(db_session, city)
    assert "ALL open CRITICAL problems (1)" in snap
    assert "Other Road" in snap and "Kestopur" in snap


def test_retrieval_returns_matching_rows(db_session):
    city = _make_city_with_problems(db_session)
    m = K.retrieve_matching_problems(db_session, city, "show critical issues")
    assert m.total == 1 and m.problems[0].problem_type.value == "open_drain"
    assert "Other Road" in K.matches_reply_text(city, m)
