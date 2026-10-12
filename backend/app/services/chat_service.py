"""
Powers the AI Recommendations chat page.

Two modes, chosen automatically (same graceful-degradation pattern as
the YOLO model in app/ml/inference.py):

  - "llm": if `LLM_API_KEY` is configured, calls an OpenAI-compatible
    `/chat/completions` endpoint (works with OpenAI, Groq, or any other
    provider/proxy implementing that same request shape - just change
    `LLM_API_BASE_URL`). The assistant is grounded with a system prompt
    built from the SAME real city data used elsewhere in the app (see
    `_build_context`), not left to hallucinate freely.
  - "rule_based": used whenever no key is configured, or the LLM call
    fails for any reason. This is not just a "sorry, unavailable" stub -
    it's a genuinely useful keyword-intent assistant that answers from
    real database-backed data (city stats, risk explanations, relevant
    organizations), so the chat page is fully functional even with zero
    external dependencies.

No API key is ever required to use this feature at a basic level; a key
only upgrades it to open-ended LLM conversation.

This module also provides `generate_report_summary()`, used by Report
Problem to turn a just-created report into a short readable sentence -
the same optional-LLM-with-deterministic-fallback pattern, reusing the
same HTTP call helper (`_call_llm_messages`).
"""
import re

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.city import City
from app.schemas.chat import ChatMessage
from app.services.area_service import (
    AreaLookup, area_context_for_prompt, area_reply_text, lookup_area, _load_known_names,
)
from app.services.city_knowledge import (
    Matches, build_city_snapshot, matches_context_for_prompt, matches_reply_text, retrieve_matching_problems,
    _load_problems,
)
from app.services.city_service import get_city_summary
from app.services.recommendation_service import ORGANIZATIONS, CIVIC_TIPS, get_city_recommendations

logger = get_logger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are the NeceCity AI Assistant, embedded in an urban infrastructure \
monitoring platform for {city_name}, {city_state}. You know this city's reported problems in detail and \
you give residents and officials specific, actionable answers and recommendations.

LIVE DATA FOR {city_name} (queried from the platform database a moment ago - this is the ONLY source of \
facts about problems; use these exact numbers, roads, wards, risk scores and ids, never invent others):
{city_snapshot}
{match_block}{area_block}
Relevant real civic organizations you may recommend (only these - never invent an organization, address \
or phone number):
{organizations}

General civic tips:
{tips}

Areas/roads/wards that have reports (real names from the database): {known_areas}

HOW TO ANSWER
- Answer the question that was asked, directly, using the data above. When asked about critical, high, \
recurring or old problems, name them: type, road, ward, severity, status, risk score, age and the \
#id (the id lets the person find it in the Action Center). Never reply that you "only have a count" when \
the list is above.
- If a MATCHING PROBLEMS or AREA DATA block is present, base the answer on it. If both are present and the \
question names a place, keep only the matching problems that are in that place.
- Always finish with practical recommendations tied to THESE problems: which to escalate first and why \
(risk score, severity, age, recurrence, nearby hospital/school/market), which status step comes next, and \
which listed organization or platform fits each problem type.
- If the data genuinely does not contain the answer (e.g. a road with no reports, or something the platform \
does not record such as repair costs or contractor names), say so in one sentence and offer the closest \
thing you do know. Do not guess.
- Out-of-scope questions (not about civic infrastructure or this platform): say so briefly.

FORMAT (the chat window renders simple Markdown)
- Use short paragraphs, "-" bullet lists, numbered lists and **bold**. A "###" heading is fine for \
longer answers.
- NEVER use Markdown tables, HTML tags (no <br>), or code blocks. Put each item on its own bullet line \
instead, e.g. "- **Pothole** (high, in progress) - Sevoke Road, Hakimpara ward - risk 62/100, 14 days old (#123)".
- Be complete but tight: normally under 300 words; list every item when the user asks for "all". Always \
finish your last sentence."""


def _build_context(db: Session, city: City, message: str = "") -> dict:
    summary = get_city_summary(db, city)
    city_recs = get_city_recommendations(db, city)
    type_breakdown = ", ".join(
        f"{t.replace('_', ' ')}: {c}" for t, c in summary["problem_type_breakdown"].items() if c > 0
    ) or "no problems reported yet"

    problems = _load_problems(db, city)  # loaded once, shared by the snapshot and the retrieval below
    _, ward_names, _ = _load_known_names(db, city)

    return {
        "summary": summary,
        "city_insights": city_recs["city_insights"],
        "type_breakdown": type_breakdown,
        "snapshot": build_city_snapshot(db, city, problems),
        "matches": retrieve_matching_problems(db, city, message, ward_names, problems),
    }


def _system_prompt(city: City, context: dict) -> str:
    lookup: AreaLookup | None = context.get("area")
    area_text = area_context_for_prompt(lookup) if lookup else ""
    known = ", ".join(lookup.known_areas[:40]) if lookup and lookup.known_areas else "none yet"
    summary = context["summary"]
    orgs_text = "\n".join(f"- {o.name} ({o.category}): {o.description} [{o.website}]" for o in ORGANIZATIONS)
    tips_text = "\n".join(f"- {t['title']}: {t['body']}" for t in CIVIC_TIPS)
    matches: Matches | None = context.get("matches")
    match_text = matches_context_for_prompt(matches) if matches else ""
    return SYSTEM_PROMPT_TEMPLATE.format(
        city_name=city.name,
        city_state=city.state,
        city_snapshot=(
            f"Infrastructure health score: {summary['infrastructure_health_score']}/100 "
            f"({summary['infrastructure_health_label']}).\n{context['snapshot']}"
        ),
        match_block=f"\n{match_text}\n" if match_text else "",
        organizations=orgs_text,
        tips=tips_text,
        known_areas=known,
        area_block=f"\n{area_text}\n" if area_text else "",
    )


_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def clean_llm_text(text: str) -> str:
    """
    Make model output safe for the chat window: models sometimes emit HTML line
    breaks (<br>) inside Markdown tables/lists, and non-breaking hyphens that
    render oddly. Convert breaks to newlines and drop any other HTML tags.
    """
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = _HTML_TAG.sub("", text)
    text = (text.replace("\u2011", "-").replace("\u2010", "-").replace("\u00a0", " ")
                .replace("\u202f", " ").replace("\u200b", ""))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _call_llm_messages(messages: list[dict], *, max_tokens: int | None = None, temperature: float = 0.4) -> str | None:
    """
    Shared low-level caller for any OpenAI-compatible /chat/completions
    request. Used by the AI Recommendations chat, place extraction and the
    Report Problem summary so the HTTP/error-handling logic exists once.

    Reasoning models spend part of max_tokens on hidden "thinking", which is
    why a small budget gave cut-off or empty answers. So: a generous default
    (LLM_MAX_TOKENS), and if the provider says the reply was cut off
    (finish_reason == "length") we retry once with double the budget.
    """
    settings = get_settings()
    if not settings.LLM_API_KEY:
        return None

    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
    }
    if settings.LLM_REASONING_EFFORT:
        payload["reasoning_effort"] = settings.LLM_REASONING_EFFORT

    try:
        content = ""
        for attempt in range(2):
            resp = httpx.post(
                f"{settings.LLM_API_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            choice = resp.json()["choices"][0]
            content = (choice["message"].get("content") or "").strip()
            if choice.get("finish_reason") == "length" and attempt == 0:
                logger.info("LLM reply hit max_tokens (%s); retrying with a larger budget.", payload["max_tokens"])
                payload["max_tokens"] = min(payload["max_tokens"] * 2, 8000)
                continue
            break
        return clean_llm_text(content) if content else None
    except Exception as exc:  # noqa: BLE001 - any LLM failure must fall back, never break the caller
        logger.warning("LLM call failed: %s", exc)
        return None


def _call_llm(city: City, context: dict, message: str, history: list[ChatMessage]) -> str | None:
    messages = [{"role": "system", "content": _system_prompt(city, context)}]
    for h in history[-10:]:  # keep the payload small - last 10 turns of context is plenty
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": message})
    return _call_llm_messages(messages)


REPORT_SUMMARY_SYSTEM_PROMPT = (
    "You write short, plain, factual one-to-two sentence summaries of civic infrastructure reports "
    "for a municipal monitoring dashboard. No marketing language, no exclamation points, no invented "
    "details - use only the facts given to you."
)


def generate_report_summary(
    *, city_name: str, problem_type: str, severity: str, road_name: str | None, confidence: float | None
) -> str:
    """
    Produces a short, human-readable synopsis of a newly created report,
    shown on the Report Problem success screen.

    This is a deliberately small, clearly-scoped LLM feature (project
    rule: Groq/an LLM may be used for turning a verified report into
    readable text, never for the detection or risk-scoring accuracy
    itself - those stay fully deterministic, see app/ml/inference.py and
    app/risk/engine.py). Falls back to a plain string-formatted template
    (not "AI-generated" - just Python string formatting) when no LLM key
    is configured, so the success screen is always populated either way.
    """
    problem_label = problem_type.replace("_", " ")
    location_label = road_name or city_name
    if confidence is not None:
        source_clause = f"detected by the NeceCity model with {confidence:.0%} confidence and confirmed by the reporting user"
    else:
        source_clause = "reported manually by a user, without model assistance"

    settings = get_settings()
    if settings.LLM_API_KEY:
        user_prompt = (
            f"Problem type: {problem_label}. Severity: {severity}. "
            f"Location: {location_label}, {city_name}. Source: {source_clause}. "
            "Write the 1-2 sentence summary now."
        )
        reply = _call_llm_messages(
            [
                {"role": "system", "content": REPORT_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=600,
            temperature=0.3,
        )
        if reply:
            return reply

    return f"A {severity.lower()}-severity {problem_label} was reported at {location_label}, {city_name}. It was {source_clause}."


# ---- Rule-based fallback: keyword-intent matching over real data ----

_PROBLEM_TYPE_KEYWORDS = {
    "pothole": "road_safety", "road": "road_safety", "sign": "road_safety",
    "garbage": "sanitation", "waste": "sanitation", "trash": "sanitation",
    "drain": "sanitation", "water": "sanitation", "flood": "sanitation",
}


def _relevant_orgs_for_message(message: str) -> list:
    lower = message.lower()
    matched_categories = {cat for kw, cat in _PROBLEM_TYPE_KEYWORDS.items() if kw in lower}
    if not matched_categories:
        return ORGANIZATIONS[:3]
    return [o for o in ORGANIZATIONS if o.category in matched_categories] or ORGANIZATIONS[:3]


def _rule_based_reply(db: Session, city: City, message: str, context: dict) -> str:
    lower = message.lower().strip()
    summary = context["summary"]

    def matches(*keywords: str) -> bool:
        return any(re.search(rf"\b{re.escape(k)}\b", lower) for k in keywords)

    area: AreaLookup | None = context.get("area")
    asks_for_orgs = matches("contact", "ngo", "volunteer", "organization", "organisation", "who can help", "help with")
    if area is not None and not asks_for_orgs:
        if area.summary is not None:
            return area_reply_text(city, area)
        if area.unresolved_phrase:
            return area_reply_text(city, area)

    found: Matches | None = context.get("matches")
    if found is not None and found.active and not asks_for_orgs:
        return matches_reply_text(city, found)

    if matches("hi", "hello", "hey", "namaste"):
        return (
            f"Hi! I'm the NeceCity assistant for {city.name}. I can tell you about {city.name}'s current "
            "problem statistics, explain how risk scores work, suggest organizations to contact for a specific "
            "issue, or share civic tips. What would you like to know?"
        )

    if matches("total", "how many", "stats", "overview", "summary"):
        return (
            f"{city.name} currently has {summary['total_problems']} reported problems: "
            f"{summary['critical_problems']} critical, {summary['high_priority_problems']} high priority, "
            f"{summary['resolved_problems']} resolved. Infrastructure health score: "
            f"{summary['infrastructure_health_score']}/100 ({summary['infrastructure_health_label']}). "
            "See the Command Center for the full breakdown."
        )

    if matches("biggest", "most common", "worst", "top issue", "top problem"):
        if context["city_insights"]:
            return context["city_insights"][0]
        return f"No problems have been reported in {city.name} yet, so there's no dominant issue to report."

    if matches("critical", "urgent", "emergency"):
        if summary["critical_problems"] > 0:
            return (
                f"{city.name} has {summary['critical_problems']} critical-severity problem(s) open right now. "
                "Check the Action Center's priority queue - it's sorted by risk score with the most urgent first."
            )
        return f"Good news - {city.name} has no critical-severity problems open right now."

    if matches("report", "upload", "submit", "log"):
        return (
            "To report a problem: go to Report Problem, upload a street photo, and either let the model "
            "detect it or log it manually with the type and severity you observe. It'll show up immediately "
            "on City Monitor and in the Action Center's priority queue."
        )

    if matches("status", "track", "progress", "resolved"):
        return (
            "A submitted report starts out Verified (you already reviewed it when you submitted it), then "
            "moves through In Progress → Resolved as work happens. You can track any problem's status on City "
            "Monitor (click a marker) or manage the whole queue in the Action Center."
        )

    if matches("risk", "priority", "why"):
        return (
            "Risk scores (0-100) are calculated from severity, how often a problem recurs, how many other "
            "problems are nearby, the importance of the road, and proximity to critical infrastructure - it's a "
            "transparent weighted formula, not a black box. Open any problem's detail panel to see the exact "
            "factor breakdown."
        )

    if matches("contact", "ngo", "volunteer", "organization", "organisation", "clean-up", "cleanup", "drive", "who can help", "help with"):
        orgs = _relevant_orgs_for_message(lower)
        lines = "\n".join(f"- {o.name} — {o.website}" for o in orgs)
        return f"A few real organizations that could help, depending on the issue:\n{lines}\n\nSee the reference panel for the full directory."

    if matches("tip", "tips", "advice", "what can i do", "how can i help"):
        tips = CIVIC_TIPS[:2]
        lines = "\n".join(f"- {t['title']}: {t['body']}" for t in tips)
        return f"A couple of tips:\n{lines}\n\nSee the reference panel below for more."

    return (
        "I can help with: current problem statistics for your city, explaining risk/priority scores, "
        "suggesting organizations to contact for a specific issue, and general civic tips. Try asking something "
        "like \"what's the biggest problem in my city?\" or \"who can help with garbage collection?\". "
        "(For open-ended conversation, an administrator can connect a real AI provider - see backend/.env.example.)"
    )


def _llm_extract_place(city: City, message: str) -> str | None:
    """Second-chance place extraction for phrasings the syntactic extractor misses."""
    reply = _call_llm_messages(
        [
            {"role": "system", "content": (
                "Extract the single place name (neighbourhood, ward, road, landmark) the user is asking about. "
                "Reply with ONLY the place name, or the word NONE if there is no specific place. "
                f"The user is in {city.name}, India. Do not answer the question."
            )},
            {"role": "user", "content": message},
        ],
        max_tokens=300,
        temperature=0.0,
    )
    if not reply:
        return None
    reply = reply.strip().strip(".\"'")
    return None if not reply or reply.upper() == "NONE" or len(reply) > 60 else reply


def get_chat_reply(db: Session, city: City, message: str, history: list[ChatMessage]) -> tuple[str, str]:
    """Returns (reply, mode) where mode is 'llm' or 'rule_based'."""
    context = _build_context(db, city, message)

    # Place-specific questions ("what issues are on Sevoke Road?", "does Kestopur
    # have infra issues?") are answered from real per-area data, not city totals.
    previous_user = [h.content for h in history if h.role == "user"]
    try:
        context["area"] = lookup_area(
            db, city, message,
            previous_user_messages=previous_user,
            llm_place_extractor=(lambda m: _llm_extract_place(city, m)) if get_settings().LLM_API_KEY else None,
        )
    except Exception as exc:  # noqa: BLE001 - an area-lookup failure must never break the chat
        logger.warning("Area lookup failed: %s", exc)
        context["area"] = None

    llm_reply = _call_llm(city, context, message, history)
    if llm_reply:
        return llm_reply, "llm"

    return _rule_based_reply(db, city, message, context), "rule_based"
