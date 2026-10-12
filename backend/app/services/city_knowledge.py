"""
Gives the AI Recommendations assistant full knowledge of the selected city.

Two pieces, both computed live from the database on every question (nothing
is hard-coded or cached between questions):

  1. `build_city_snapshot()` - a compact, always-included briefing: status /
     severity / type totals, a ward-by-ward table, the roads with the most open
     problems, EVERY open critical problem with its road, ward, risk score and
     age, the top open high-severity and highest-risk problems, recurring
     problems and the latest reports. With this the assistant can answer
     "what are the critical issues?" with real locations instead of only a count.

  2. `retrieve_matching_problems()` - question-driven retrieval. If the message
     mentions a severity ("critical"), type ("potholes"), status ("in progress"),
     ward, or "recurring", the matching problems are queried and handed to the
     assistant in full (up to a cap), so questions like "which potholes are still
     open in Park Street?" are answered from exact rows.

The same data is used to write a readable answer when no LLM is configured.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.logging import get_logger
from app.models.city import City
from app.models.enums import ProblemStatus, ProblemType, Severity
from app.models.problem import Problem
from app.services.area_service import normalize, strip_demo_suffix

logger = get_logger(__name__)

_MAX_PROBLEMS_SCANNED = 5000
CRITICAL_LIST_CAP = 25
HIGH_LIST_CAP = 12
TOP_RISK_CAP = 10
RECURRING_CAP = 8
RECENT_CAP = 6
TOP_ROADS_CAP = 8
MATCH_CAP = 25

# Phrase -> enum value. These map *vocabulary* to the app's own enums (the same
# enums used by the database); they are not data.
_SEVERITY_WORDS = {
    "critical": "critical", "urgent": "critical", "emergency": "critical", "severe": "critical",
    "high": "high", "serious": "high",
    "medium": "medium", "moderate": "medium",
    "low": "low", "minor": "low",
}
_TYPE_PATTERNS = {
    "pothole": r"\bpot ?holes?\b",
    "road_damage": r"\broad damage\b|\bdamaged roads?\b|\bbroken roads?\b|\bcracks?\b",
    "garbage": r"\bgarbage\b|\bwaste\b|\btrash\b|\blitter\b|\bdump",
    "waterlogging": r"\bwater ?logg|\bflood",
    "damaged_road_sign": r"\b(?:road |traffic )?signs?\b|\bsignboards?\b",
    "open_drain": r"\bopen drains?\b|\bdrains?\b|\bsewage\b|\bmanholes?\b",
}
_STATUS_PATTERNS = {
    "resolved": r"\bresolved\b|\bfixed\b|\bcompleted?\b|\bclosed\b",
    "in_progress": r"\bin progress\b|\bongoing\b|\bbeing fixed\b|\bunder repair\b|\bwork started\b",
    "detected": r"\bdetected\b|\bawaiting verification\b|\bunverified\b",
    "verified": r"\bverified\b",
}
_OPEN_WORDS = re.compile(r"\bunresolved\b|\bopen\b|\bpending\b|\bnot (?:yet )?(?:fixed|resolved)\b|\boutstanding\b|\bstill\b")
_RECURRING_WORDS = re.compile(r"\brecurr|\brepeat|\bagain and again\b|\bkeeps? (?:happening|coming)\b|\bchronic")
_OLDEST_WORDS = re.compile(r"\boldest\b|\blongest\b|\bpending the longest\b|\bdelayed\b|\boverdue\b")
_NEWEST_WORDS = re.compile(r"\blatest\b|\bnewest\b|\brecent(?:ly)?\b|\blast (?:few )?(?:days?|week)\b")


@dataclass
class Filters:
    severities: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    open_only: bool = False
    recurring: bool = False
    ward_id: int | None = None
    ward_name: str | None = None
    sort: str = "risk"  # risk | oldest | newest

    @property
    def active(self) -> bool:
        return bool(self.severities or self.types or self.statuses or self.open_only or self.recurring or self.ward_id)

    def describe(self) -> str:
        bits = []
        if self.severities:
            bits.append("/".join(self.severities) + " severity")
        if self.types:
            bits.append("/".join(t.replace("_", " ") for t in self.types))
        if self.statuses:
            bits.append("status " + "/".join(s.replace("_", " ") for s in self.statuses))
        elif self.open_only:
            bits.append("unresolved")
        if self.recurring:
            bits.append("recurring")
        if self.ward_name:
            bits.append(f"in {self.ward_name}")
        return ", ".join(bits) or "all"


# --------------------------------------------------------------------------- #
# Parsing (pure - unit tested)
# --------------------------------------------------------------------------- #
def parse_filters(message: str, ward_names: dict[str, int] | None = None) -> Filters:
    text = normalize(message)  # also turns non-breaking hyphens etc. into spaces
    f = Filters()

    for word, sev in _SEVERITY_WORDS.items():
        if re.search(rf"\b{word}\b", text) and sev not in f.severities:
            f.severities.append(sev)
    for ptype, pattern in _TYPE_PATTERNS.items():
        if re.search(pattern, text):
            f.types.append(ptype)
    for status, pattern in _STATUS_PATTERNS.items():
        if re.search(pattern, text):
            f.statuses.append(status)
    # "verified" also matches inside "awaiting verification"/"unverified" handling above; keep distinct
    if "detected" in f.statuses and "verified" in f.statuses and re.search(r"\bunverified\b|\bawaiting verification\b", text):
        f.statuses.remove("verified")

    f.open_only = bool(_OPEN_WORDS.search(text)) and not f.statuses
    f.recurring = bool(_RECURRING_WORDS.search(text))
    if _OLDEST_WORDS.search(text):
        f.sort = "oldest"
    elif _NEWEST_WORDS.search(text):
        f.sort = "newest"

    if ward_names:
        for name, wid in sorted(ward_names.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text):
                f.ward_id, f.ward_name = wid, name.title()
                break
    return f


# --------------------------------------------------------------------------- #
# Data loading / formatting
# --------------------------------------------------------------------------- #
def _load_problems(db: Session, city: City) -> list[Problem]:
    stmt = (
        select(Problem)
        .options(joinedload(Problem.location), joinedload(Problem.risk_score), joinedload(Problem.ward))
        .where(Problem.city_id == city.id)
        .limit(_MAX_PROBLEMS_SCANNED)
    )
    return list(db.execute(stmt).unique().scalars().all())


def _age_days(p: Problem) -> int | None:
    ts = p.first_detected_at
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - ts).days, 0)


def _risk(p: Problem) -> float:
    return p.risk_score.score if p.risk_score else 0.0


def _is_open(p: Problem) -> bool:
    return p.status != ProblemStatus.RESOLVED


def problem_line(p: Problem) -> str:
    """One compact, self-contained line describing a problem."""
    loc = p.location
    road = strip_demo_suffix(loc.road_name) if loc and loc.road_name else "road not named"
    where = road + (f", {p.ward.name} ward" if p.ward else "")
    bits = [
        f"#{p.id}",
        p.problem_type.value.replace("_", " "),
        p.severity.value,
        p.status.value.replace("_", " "),
        where,
    ]
    if p.risk_score:
        bits.append(f"risk {p.risk_score.score:.0f}/100")
    age = _age_days(p)
    if age is not None:
        bits.append(f"{age}d old")
    if p.recurrence_count and p.recurrence_count > 1:
        bits.append(f"recurred {p.recurrence_count}x")
    if loc and loc.near_important_infrastructure:
        bits.append("near " + (loc.infrastructure_note or "important infrastructure"))
    if loc and loc.road_importance and loc.road_importance.value != "local":
        bits.append(loc.road_importance.value + " road")
    return " | ".join(bits)


def _counts(items) -> str:
    c = Counter(items)
    return ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in c.most_common()) or "none"


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #
def build_city_snapshot(db: Session, city: City, problems: list[Problem] | None = None) -> str:
    problems = problems if problems is not None else _load_problems(db, city)
    if not problems:
        return f"No problems have been reported in {city.name} yet."

    open_p = [p for p in problems if _is_open(p)]
    resolved = len(problems) - len(open_p)
    lines = [
        f"Totals: {len(problems)} reported, {len(open_p)} unresolved, {resolved} resolved "
        f"({resolved / len(problems):.0%} resolution rate).",
        f"By status: {_counts(p.status.value for p in problems)}.",
        f"By severity (all): {_counts(p.severity.value for p in problems)}.",
        f"By severity (unresolved): {_counts(p.severity.value for p in open_p)}.",
        f"By type (all): {_counts(p.problem_type.value for p in problems)}.",
        f"By type (unresolved): {_counts(p.problem_type.value for p in open_p)}.",
    ]

    # Ward table
    by_ward: dict[str, list[Problem]] = {}
    for p in problems:
        by_ward.setdefault(p.ward.name if p.ward else "(no ward recorded)", []).append(p)
    ward_rows = []
    for name, items in sorted(by_ward.items(), key=lambda kv: -sum(_is_open(p) for p in kv[1])):
        o = [p for p in items if _is_open(p)]
        crit = sum(p.severity == Severity.CRITICAL for p in o)
        ward_rows.append(f"{name}: {len(items)} total, {len(o)} open, {crit} critical open")
    lines.append("Wards (most open problems first): " + "; ".join(ward_rows) + ".")

    # Roads
    road_open: Counter = Counter()
    for p in open_p:
        if p.location and p.location.road_name:
            road_open[strip_demo_suffix(p.location.road_name)] += 1
    if road_open:
        lines.append(
            "Roads with the most open problems: "
            + "; ".join(f"{r} {n}" for r, n in road_open.most_common(TOP_ROADS_CAP)) + "."
        )

    crit = sorted((p for p in open_p if p.severity == Severity.CRITICAL), key=_risk, reverse=True)
    lines.append(f"\nALL open CRITICAL problems ({len(crit)}):")
    lines += [f"- {problem_line(p)}" for p in crit[:CRITICAL_LIST_CAP]] or ["- none"]
    if len(crit) > CRITICAL_LIST_CAP:
        lines.append(f"- ...and {len(crit) - CRITICAL_LIST_CAP} more")

    high = sorted((p for p in open_p if p.severity == Severity.HIGH), key=_risk, reverse=True)
    lines.append(f"\nOpen HIGH-severity problems ({len(high)}), top {min(len(high), HIGH_LIST_CAP)} by risk:")
    lines += [f"- {problem_line(p)}" for p in high[:HIGH_LIST_CAP]] or ["- none"]

    top = sorted(open_p, key=_risk, reverse=True)[:TOP_RISK_CAP]
    lines.append(f"\nTop {len(top)} open problems by risk score (the Action Center priority queue):")
    lines += [f"- {problem_line(p)}" for p in top]

    rec = sorted((p for p in open_p if p.recurrence_count and p.recurrence_count > 1),
                 key=lambda p: p.recurrence_count, reverse=True)[:RECURRING_CAP]
    if rec:
        lines.append("\nRecurring open problems (same issue re-reported at the same spot):")
        lines += [f"- {problem_line(p)}" for p in rec]

    recent = sorted(problems, key=lambda p: p.first_detected_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:RECENT_CAP]
    lines.append("\nMost recent reports:")
    lines += [f"- {problem_line(p)}" for p in recent]

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Question-driven retrieval
# --------------------------------------------------------------------------- #
@dataclass
class Matches:
    filters: Filters
    total: int
    problems: list[Problem]

    @property
    def active(self) -> bool:
        return self.filters.active


def retrieve_matching_problems(
    db: Session, city: City, message: str, ward_names: dict[str, int] | None = None,
    problems: list[Problem] | None = None,
) -> Matches:
    f = parse_filters(message, ward_names)
    if not f.active:
        return Matches(f, 0, [])

    problems = problems if problems is not None else _load_problems(db, city)
    out = problems
    if f.severities:
        out = [p for p in out if p.severity.value in f.severities]
    if f.types:
        out = [p for p in out if p.problem_type.value in f.types]
    if f.statuses:
        out = [p for p in out if p.status.value in f.statuses]
    elif f.open_only:
        out = [p for p in out if _is_open(p)]
    elif not f.statuses and (f.severities or f.types or f.ward_id):
        # "critical issues" means what still needs attention, unless they asked for resolved ones
        out = [p for p in out if _is_open(p)]
    if f.recurring:
        out = [p for p in out if p.recurrence_count and p.recurrence_count > 1]
    if f.ward_id:
        out = [p for p in out if p.ward_id == f.ward_id]

    if f.sort == "oldest":
        out = sorted(out, key=lambda p: _age_days(p) or 0, reverse=True)
    elif f.sort == "newest":
        out = sorted(out, key=lambda p: _age_days(p) if _age_days(p) is not None else 10**6)
    else:
        out = sorted(out, key=_risk, reverse=True)
    return Matches(f, len(out), out[:MATCH_CAP])


def matches_context_for_prompt(m: Matches) -> str:
    if not m.active:
        return ""
    head = f"MATCHING PROBLEMS for this question (filter: {m.filters.describe()}; {m.total} found"
    head += f", showing {len(m.problems)}):" if m.total > len(m.problems) else "):"
    if not m.problems:
        return head + "\n- none. Say clearly that no reported problems match."
    return head + "\n" + "\n".join(f"- {problem_line(p)}" for p in m.problems)


def matches_reply_text(city: City, m: Matches) -> str:
    """Plain-markdown reply (no tables, no HTML) used when no LLM is available."""
    f = m.filters
    if m.total == 0:
        return f"No reported problems in {city.name} match: {f.describe()}."
    sev_counts = _counts(p.severity.value for p in m.problems)
    parts = [
        f"**{m.total} problem{'s' if m.total != 1 else ''} in {city.name}** match ({f.describe()}).",
        f"Of the {len(m.problems)} shown: {sev_counts}.",
        "",
    ]
    for p in m.problems:
        loc = p.location
        road = strip_demo_suffix(loc.road_name) if loc and loc.road_name else "road not named"
        where = road + (f", {p.ward.name}" if p.ward else "")
        extra = []
        if p.risk_score:
            extra.append(f"risk {p.risk_score.score:.0f}/100")
        age = _age_days(p)
        if age is not None:
            extra.append(f"{age} days old")
        if p.recurrence_count and p.recurrence_count > 1:
            extra.append(f"recurred {p.recurrence_count}x")
        parts.append(
            f"- **{p.problem_type.value.replace('_', ' ').title()}** ({p.severity.value}, "
            f"{p.status.value.replace('_', ' ')}) at {where}" + (f" — {', '.join(extra)}" if extra else "")
        )
    if m.total > len(m.problems):
        parts.append(f"\n…and {m.total - len(m.problems)} more. Open the Action Center for the full priority queue.")
    else:
        parts.append("\nOpen the Action Center to assign or update these.")
    return "\n".join(parts)
