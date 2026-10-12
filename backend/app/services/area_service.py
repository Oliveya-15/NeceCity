"""
Area-level lookups for the AI Recommendations chat.

Question this answers: "does Kestopur have any infra issues?" / "what problems
are on Sevoke Road?". Nothing here is hard-coded - every answer is computed
from the problems actually stored in the database.

How a place in the user's message is resolved (in order):

  1. KNOWN NAMES (database): ward names and the road / address / landmark
     names stored with reported locations for the selected city. Matching is
     case-insensitive and typo-tolerant ("sevok road"). Demo roads are stored
     as "Sevoke Road #12"; the "#12" suffix is stripped so "Sevoke Road"
     matches all of them.
  2. GEOCODING: if the message names a place we have no stored name for
     (e.g. a neighbourhood nobody has reported in yet), the place is geocoded
     with OpenStreetMap Nominatim (free, no API key, configurable via
     GEOCODER_* settings) and we count reported problems within a radius of
     that point. Results far from the selected city are rejected.
  3. Otherwise nothing is resolved and the chat says so honestly, rather than
     answering with unrelated city-wide numbers.

The geocoder is optional: if it is disabled, offline or fails, step 2 is simply
skipped and the chat degrades gracefully (same pattern as the YOLO model).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.city import City
from app.models.enums import ProblemStatus
from app.models.location import Location
from app.models.problem import Problem
from app.models.ward import Ward

logger = get_logger(__name__)

_MAX_LOCATION_ROWS = 20000  # safety cap on rows scanned per question
_FUZZY_CUTOFF = 0.84

# Words that are never part of a place name. Used to trim phrases pulled out of
# a question ("does kestopur have any infra issues" -> "kestopur").
_STOPWORDS = {
    "a", "an", "the", "any", "some", "is", "are", "was", "were", "do", "does", "did", "has", "have", "had",
    "there", "here", "what", "which", "whats", "what's", "how", "many", "much", "tell", "me", "show", "give",
    "about", "of", "for", "in", "at", "on", "near", "around", "within", "nearby", "inside", "to", "from", "with",
    "and", "or", "my", "our", "your", "this", "that", "these", "those", "it", "its", "please", "can", "you",
    "issue", "issues", "problem", "problems", "infra", "infrastructure", "report", "reports", "reported",
    "complaint", "complaints", "damage", "damages", "condition", "conditions", "status", "currently", "now",
    "right", "today", "recent", "recently", "area", "areas", "locality", "neighbourhood", "neighborhood",
    "situation", "info", "information", "details", "detail", "get", "got", "facing", "face", "seen", "see",
    "pothole", "potholes", "garbage", "waterlogging", "drain", "drains", "sign", "signs", "road damage",
    "city", "town", "ward", "any?", "like", "be", "been", "being", "i", "we", "yes", "no",
    "who", "whom", "help", "helps", "helping", "biggest", "worst", "most", "common", "top", "main", "major",
    "collection", "contact", "organization", "organizations", "organisation", "organisations", "ngo", "ngos",
    "s", "t", "ll", "re", "ve", "how", "why", "when", "where", "should", "would", "could", "will", "may",
    "score", "scores", "risk", "priority", "work", "works", "tip", "tips", "advice", "stats", "statistics",
}

# Geocoding is only attempted when the message is plausibly about conditions
# in a place - otherwise "how do risk scores work" would trigger a map lookup.
_AREA_INTENT = re.compile(
    r"issue|problem|pothole|garbage|waste|trash|drain|flood|waterlog|damage|infra|road|street|lane|condition|"
    r"complain|report|status|safe|clean|broken|sign|hazard|risk",
    re.I,
)


def has_area_intent(message: str) -> bool:
    return bool(_AREA_INTENT.search(message))


_PLACE_PATTERNS = [
    # "does kestopur have any ...", "is salt lake facing ..."
    re.compile(r"\b(?:does|do|is|are|has|have|will)\s+(?:the\s+)?(?P<p>[a-z0-9][\w .'\-,/]{1,50}?)\s+(?:have|has|got|had|face|facing|suffer|suffering|need|show|report)\b", re.I),
    # "issues in/at/near/around sevoke road"
    re.compile(r"\b(?:in|at|near|around|within|nearby|inside|along|across|on|of|for|about)\s+(?:the\s+)?(?P<p>[a-z0-9][\w .'\-,/]{1,50})", re.I),
    # "sevoke road issues", "kestopur problems"
    re.compile(r"(?P<p>[a-z0-9][\w .'\-]{2,40}?)\s+(?:issues?|problems?|potholes?|garbage|waterlogging|complaints?)\b", re.I),
]


# --------------------------------------------------------------------------- #
# Data containers
# --------------------------------------------------------------------------- #
@dataclass
class AreaProblem:
    problem_type: str
    severity: str
    status: str
    road_name: str | None
    risk_score: float | None
    days_ago: int | None
    distance_m: int | None = None


@dataclass
class AreaSummary:
    label: str                    # what we resolved the user's words to
    method: str                   # "ward" | "road" | "geocoded"
    total: int
    unresolved: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    by_status: dict[str, int]
    top_problems: list[AreaProblem] = field(default_factory=list)
    radius_m: int | None = None   # only for geocoded areas
    geocoded_name: str | None = None


@dataclass
class AreaLookup:
    """Result of trying to interpret a place in the user's message."""
    summary: AreaSummary | None = None
    unresolved_phrase: str | None = None  # a place-like phrase we could not locate
    known_areas: list[str] = field(default_factory=list)  # real names from the DB, for suggestions


# --------------------------------------------------------------------------- #
# Text helpers (pure functions - easy to unit test)
# --------------------------------------------------------------------------- #
def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def strip_demo_suffix(name: str) -> str:
    """'Sevoke Road #12' -> 'Sevoke Road'."""
    return re.sub(r"\s*#\s*\d+\s*$", "", name).strip()


def name_variants(raw: str | None) -> list[str]:
    """
    Searchable variants of a stored name: the whole thing plus each comma
    segment, e.g. 'Sevoke Road, near City Bus Terminus' ->
    ['sevoke road near city bus terminus', 'sevoke road', 'near city bus terminus'].
    """
    if not raw:
        return []
    cleaned = strip_demo_suffix(raw)
    variants = {normalize(cleaned)}
    for seg in re.split(r"[,;/|]", cleaned):
        seg = normalize(re.sub(r"^\s*(?:near|opp\.?|opposite|beside|behind|next to)\s+", "", seg, flags=re.I))
        if len(seg) >= 3:
            variants.add(seg)
    return [v for v in variants if len(v) >= 3]


def _trim_phrase(phrase: str) -> str:
    words = normalize(phrase).split()
    while words and words[0] in _STOPWORDS:
        words.pop(0)
    while words and words[-1] in _STOPWORDS:
        words.pop()
    return " ".join(words)


def extract_place_candidates(message: str, city_name: str | None = None) -> list[str]:
    """
    Pull place-like phrases out of a question, best guess first. Purely
    syntactic ("does X have", "in X", "X issues") - no place names are
    hard-coded. A phrase equal to the city itself is dropped (that is a
    city-wide question, answered from city statistics).
    """
    city_norm = normalize(city_name) if city_name else ""
    seen: list[str] = []
    for pattern in _PLACE_PATTERNS:
        for m in pattern.finditer(message):
            phrase = _trim_phrase(m.group("p"))
            if not phrase or len(phrase) < 3 or len(phrase.split()) > 5:
                continue
            if phrase == city_norm or phrase in {"my city", "city", "town"}:
                continue
            if phrase not in seen:
                seen.append(phrase)
    return seen


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _ngrams(tokens: list[str], max_n: int = 4):
    for n in range(min(max_n, len(tokens)), 0, -1):
        for i in range(len(tokens) - n + 1):
            yield " ".join(tokens[i:i + n])


def match_known_name(message: str, known: dict[str, object]) -> str | None:
    """
    Find which known (normalized) name the message refers to. Exact word-
    boundary match first (longest name wins), then typo-tolerant match on
    word n-grams. Returns the matching key of `known`, or None.
    """
    msg = normalize(message)
    if not msg:
        return None

    exact = [k for k in known if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", msg)]
    if exact:
        return max(exact, key=len)

    tokens = [t for t in msg.split() if t not in _STOPWORDS]
    best_key, best_ratio = None, 0.0
    for gram in _ngrams(tokens):
        if len(gram) < 4:
            continue
        for k in known:
            if abs(len(k) - len(gram)) > 3:
                continue
            ratio = SequenceMatcher(None, gram, k).ratio()
            if ratio >= _FUZZY_CUTOFF and ratio > best_ratio:
                best_key, best_ratio = k, ratio
    return best_key


# --------------------------------------------------------------------------- #
# Geocoding (optional)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=256)
def _geocode_cached(query: str, viewbox: str | None) -> tuple | None:
    settings = get_settings()
    params = {"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "in", "addressdetails": 0}
    if viewbox:
        params["viewbox"] = viewbox
    try:
        resp = httpx.get(
            settings.GEOCODER_URL,
            params=params,
            headers={"User-Agent": settings.GEOCODER_USER_AGENT, "Accept-Language": "en"},
            timeout=settings.GEOCODER_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        results = resp.json()
    except Exception as exc:  # noqa: BLE001 - geocoding must never break the chat
        logger.warning("Geocoding failed for %r: %s", query, exc)
        return None
    if not results:
        return None
    r = results[0]
    try:
        south, north, west, east = (float(x) for x in r["boundingbox"])
    except (KeyError, ValueError, TypeError):
        south = north = float(r["lat"])
        west = east = float(r["lon"])
    return float(r["lat"]), float(r["lon"]), r.get("display_name", query), (south, north, west, east)


def geocode_place(phrase: str, city: City) -> tuple[float, float, str, int] | None:
    """Returns (lat, lon, display_name, suggested_radius_m) for a place inside the city, or None."""
    settings = get_settings()
    if not settings.GEOCODER_ENABLED:
        return None
    pad = 0.35  # ~35 km bias box around the city centre
    viewbox = (
        f"{city.center_longitude - pad},{city.center_latitude + pad},"
        f"{city.center_longitude + pad},{city.center_latitude - pad}"
    )
    hit = _geocode_cached(f"{phrase}, {city.name}, {city.state}, India", viewbox)
    if hit is None:
        return None
    lat, lon, display, (south, north, west, east) = hit

    dist_km = haversine_m(city.center_latitude, city.center_longitude, lat, lon) / 1000
    if dist_km > settings.AREA_MAX_DISTANCE_FROM_CITY_KM:
        logger.info("Geocoded %r is %.0f km from %s - rejected.", phrase, dist_km, city.name)
        return None

    half_diag = haversine_m(south, west, north, east) / 2
    radius = int(min(max(half_diag, settings.AREA_MIN_RADIUS_M), settings.AREA_MAX_RADIUS_M))
    return lat, lon, display, radius


# --------------------------------------------------------------------------- #
# Database queries
# --------------------------------------------------------------------------- #
def _load_known_names(db: Session, city: City) -> tuple[dict[str, set[int]], dict[str, int], list[str]]:
    """
    Returns (road_names, ward_names, display_names):
      road_names:  normalized name variant -> set of location ids
      ward_names:  normalized ward name -> ward id
      display_names: human-readable distinct names for suggestions
    """
    road_names: dict[str, set[int]] = {}
    display: dict[str, str] = {}

    rows = db.execute(
        select(Location.id, Location.road_name, Location.address_text, Location.infrastructure_note)
        .where(Location.city_id == city.id)
        .limit(_MAX_LOCATION_ROWS)
    ).all()
    for loc_id, road, addr, infra in rows:
        for raw in (road, addr, infra):
            for variant in name_variants(raw):
                road_names.setdefault(variant, set()).add(loc_id)
            if raw:
                clean = strip_demo_suffix(raw)
                display.setdefault(normalize(clean), clean)

    ward_names: dict[str, int] = {}
    for ward in db.execute(select(Ward).where(Ward.city_id == city.id)).scalars():
        ward_names[normalize(ward.name)] = ward.id
        display.setdefault(normalize(ward.name), ward.name)

    return road_names, ward_names, sorted(display.values(), key=str.lower)


def _summarize(problems: list[Problem], *, label: str, method: str, radius_m=None, geocoded_name=None,
               distances: dict[int, float] | None = None) -> AreaSummary:
    settings = get_settings()
    now = datetime.now(timezone.utc)

    def days_ago(p: Problem) -> int | None:
        ts = p.first_detected_at
        if ts is None:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max((now - ts).days, 0)

    unresolved = [p for p in problems if p.status != ProblemStatus.RESOLVED]
    ranked = sorted(
        unresolved,
        key=lambda p: (p.risk_score.score if p.risk_score else 0.0),
        reverse=True,
    )[: settings.AREA_MAX_PROBLEMS_LISTED]

    return AreaSummary(
        label=label,
        method=method,
        total=len(problems),
        unresolved=len(unresolved),
        by_type=dict(Counter(p.problem_type.value for p in problems)),
        by_severity=dict(Counter(p.severity.value for p in problems)),
        by_status=dict(Counter(p.status.value for p in problems)),
        top_problems=[
            AreaProblem(
                problem_type=p.problem_type.value,
                severity=p.severity.value,
                status=p.status.value,
                road_name=strip_demo_suffix(p.location.road_name) if p.location and p.location.road_name else None,
                risk_score=round(p.risk_score.score, 1) if p.risk_score else None,
                days_ago=days_ago(p),
                distance_m=int(distances[p.id]) if distances and p.id in distances else None,
            )
            for p in ranked
        ],
        radius_m=radius_m,
        geocoded_name=geocoded_name,
    )


def _problems_for_locations(db: Session, city: City, location_ids: set[int]) -> list[Problem]:
    if not location_ids:
        return []
    stmt = (
        select(Problem)
        .options(joinedload(Problem.location), joinedload(Problem.risk_score))
        .where(Problem.city_id == city.id, Problem.location_id.in_(location_ids))
    )
    return list(db.execute(stmt).unique().scalars().all())


def _problems_for_ward(db: Session, city: City, ward_id: int) -> list[Problem]:
    stmt = (
        select(Problem)
        .options(joinedload(Problem.location), joinedload(Problem.risk_score))
        .where(Problem.city_id == city.id, Problem.ward_id == ward_id)
    )
    return list(db.execute(stmt).unique().scalars().all())


def _problems_near(db: Session, city: City, lat: float, lon: float, radius_m: int) -> tuple[list[Problem], dict[int, float]]:
    # Cheap bounding-box prefilter in SQL, exact haversine filter in Python.
    dlat = radius_m / 111_000.0
    dlon = radius_m / (111_000.0 * max(math.cos(math.radians(lat)), 0.01))
    stmt = (
        select(Problem)
        .join(Location, Problem.location_id == Location.id)
        .options(joinedload(Problem.location), joinedload(Problem.risk_score))
        .where(
            Problem.city_id == city.id,
            Location.latitude.between(lat - dlat, lat + dlat),
            Location.longitude.between(lon - dlon, lon + dlon),
        )
    )
    found, distances = [], {}
    for p in db.execute(stmt).unique().scalars().all():
        d = haversine_m(lat, lon, p.location.latitude, p.location.longitude)
        if d <= radius_m:
            found.append(p)
            distances[p.id] = d
    return found, distances


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def lookup_area(
    db: Session,
    city: City,
    message: str,
    *,
    previous_user_messages: list[str] | None = None,
    llm_place_extractor: Callable[[str], str | None] | None = None,
) -> AreaLookup:
    """
    Try to interpret a place in `message` and summarise the problems there.
    `previous_user_messages` lets a short follow-up ("and how severe are
    they?") reuse the place from an earlier question (database names only -
    no geocoding for history, to avoid repeated network calls).
    `llm_place_extractor` is an optional second chance for phrasings the
    syntactic extractor misses; it receives the message and returns a place
    name or None.
    """
    road_names, ward_names, display_names = _load_known_names(db, city)
    lookup = AreaLookup(known_areas=display_names)

    # 1) Known names stored in the database
    known_all: dict[str, tuple[str, object]] = {k: ("ward", v) for k, v in ward_names.items()}
    for k, v in road_names.items():
        known_all.setdefault(k, ("road", v))

    def resolve_known(text: str) -> AreaSummary | None:
        key = match_known_name(text, known_all)
        if key is None:
            return None
        kind, payload = known_all[key]
        if kind == "ward":
            problems = _problems_for_ward(db, city, payload)  # type: ignore[arg-type]
        else:
            problems = _problems_for_locations(db, city, payload)  # type: ignore[arg-type]
        label = next((n for n in display_names if normalize(n) == key), key.title())
        return _summarize(problems, label=label, method=kind)

    summary = resolve_known(message)
    if summary:
        lookup.summary = summary
        return lookup

    # 2) Geocode a place-like phrase from the question
    if not has_area_intent(message):
        return lookup
    candidates = extract_place_candidates(message, city.name)
    if not candidates and llm_place_extractor is not None:
        try:
            extracted = llm_place_extractor(message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM place extraction failed: %s", exc)
            extracted = None
        if extracted:
            candidates = extract_place_candidates(f"in {extracted}", city.name) or [normalize(extracted)]

    for phrase in candidates[:3]:
        hit = geocode_place(phrase, city)
        if hit is None:
            continue
        lat, lon, display, radius = hit
        problems, distances = _problems_near(db, city, lat, lon, radius)
        lookup.summary = _summarize(
            problems, label=phrase.title(), method="geocoded",
            radius_m=radius, geocoded_name=display, distances=distances,
        )
        return lookup

    # 3) Short follow-up: reuse a place from a recent user message (DB names only)
    if not candidates:
        for prev in reversed((previous_user_messages or [])[-3:]):
            summary = resolve_known(prev)
            if summary:
                lookup.summary = summary
                return lookup

    if candidates:
        lookup.unresolved_phrase = candidates[0]
    return lookup


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def _fmt_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))


def _scope_text(s: AreaSummary) -> str:
    if s.method == "geocoded":
        return f"within about {s.radius_m} m of {s.label}"
    if s.method == "ward":
        return f"in the {s.label} ward"
    return f"on or around {s.label}"


def area_context_for_prompt(lookup: AreaLookup) -> str:
    """Plain-text block injected into the LLM system prompt."""
    if lookup.summary is None:
        if lookup.unresolved_phrase:
            sample = ", ".join(lookup.known_areas[:15]) or "none yet"
            return (
                f"The user asked about '{lookup.unresolved_phrase}', but it could not be matched to a ward/road "
                f"stored in the platform or located on the map. Say you could not locate it, do NOT guess or "
                f"substitute city-wide numbers as if they were local, and ask for a nearby landmark or an area "
                f"name. Areas that do have reports include: {sample}."
            )
        return ""

    s = lookup.summary
    lines = [f"AREA DATA for '{s.label}' ({_scope_text(s)}), from the platform database:"]
    if s.total == 0:
        lines.append("- No problems have been reported there. Say that clearly, and note it only reflects reports "
                     "submitted to NeceCity, not a guarantee the area is issue-free.")
    else:
        lines.append(f"- {s.total} reported problem(s), {s.unresolved} still unresolved.")
        lines.append(f"- By type: {_fmt_counts(s.by_type)}.")
        lines.append(f"- By severity: {_fmt_counts(s.by_severity)}.")
        lines.append(f"- By status: {_fmt_counts(s.by_status)}.")
        if s.top_problems:
            lines.append("- Highest-risk unresolved problems:")
            for p in s.top_problems:
                bits = [p.problem_type.replace("_", " "), p.severity]
                if p.road_name:
                    bits.append(p.road_name)
                if p.risk_score is not None:
                    bits.append(f"risk {p.risk_score}/100")
                if p.days_ago is not None:
                    bits.append(f"reported {p.days_ago}d ago")
                if p.distance_m is not None:
                    bits.append(f"{p.distance_m} m away")
                lines.append("  * " + ", ".join(bits))
    return "\n".join(lines)


def area_reply_text(city: City, lookup: AreaLookup) -> str:
    """Deterministic reply used when no LLM is configured (or it fails)."""
    s = lookup.summary
    if s is None:
        sample = ", ".join(lookup.known_areas[:8])
        hint = f" Areas that currently have reports include: {sample}." if sample else ""
        return (
            f"I couldn't locate **{lookup.unresolved_phrase}** in {city.name}, so I can't say what's reported there. "
            f"Try the ward or road name as it appears in the system, or a nearby landmark.{hint}"
        )

    if s.total == 0:
        return (
            f"No problems have been reported {_scope_text(s)} in {city.name}. "
            "That only reflects reports submitted to NeceCity - it doesn't guarantee the area is issue-free. "
            "If you've seen something, you can add it from Report Problem."
        )

    parts = [
        f"**{s.label}** — {s.total} reported problem{'s' if s.total != 1 else ''} {_scope_text(s)}, "
        f"{s.unresolved} still unresolved.",
        f"- Types: {_fmt_counts(s.by_type)}",
        f"- Severity: {_fmt_counts(s.by_severity)}",
        f"- Status: {_fmt_counts(s.by_status)}",
    ]
    if s.top_problems:
        parts.append("\nHighest-risk open problems:")
        for p in s.top_problems:
            bits = [f"{p.problem_type.replace('_', ' ')} ({p.severity})"]
            if p.road_name:
                bits.append(f"on {p.road_name}")
            if p.risk_score is not None:
                bits.append(f"risk {p.risk_score}/100")
            if p.days_ago is not None:
                bits.append(f"{p.days_ago}d ago")
            parts.append("- " + ", ".join(bits))
    if s.method == "geocoded" and s.geocoded_name:
        parts.append(f"\n(Located as: {s.geocoded_name})")
    return "\n".join(parts)
