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
"""
import re

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.city import City
from app.schemas.chat import ChatMessage
from app.services.city_service import get_city_summary
from app.services.recommendation_service import ORGANIZATIONS, CIVIC_TIPS, get_city_recommendations

logger = get_logger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are the NeceCity AI Assistant, embedded in an urban infrastructure \
monitoring platform for {city_name}, {city_state}. You help residents understand civic issues in \
their city and connect them with the right resources to help resolve them.

Current real data for {city_name} (from the platform's own database - use these numbers, don't \
invent different ones):
- Total reported problems: {total_problems}
- Critical severity: {critical_problems}
- Infrastructure health score: {health_score}/100 ({health_label})
- Most-reported problem type breakdown: {type_breakdown}

Relevant real civic organizations you can recommend (only recommend organizations from this list -
never invent an organization name, address or phone number):
{organizations}

General civic tips available:
{tips}

Be concise, practical, and honest. If asked something outside this platform's scope (not about \
civic infrastructure, this city's data, or these organizations), say so briefly rather than \
guessing. Never invent statistics or organizations beyond what's given above."""


def _build_context(db: Session, city: City) -> dict:
    summary = get_city_summary(db, city)
    city_recs = get_city_recommendations(db, city)
    type_breakdown = ", ".join(
        f"{t.replace('_', ' ')}: {c}" for t, c in summary["problem_type_breakdown"].items() if c > 0
    ) or "no problems reported yet"

    return {
        "summary": summary,
        "city_insights": city_recs["city_insights"],
        "type_breakdown": type_breakdown,
    }


def _system_prompt(city: City, context: dict) -> str:
    summary = context["summary"]
    orgs_text = "\n".join(f"- {o.name} ({o.category}): {o.description} [{o.website}]" for o in ORGANIZATIONS)
    tips_text = "\n".join(f"- {t['title']}: {t['body']}" for t in CIVIC_TIPS)
    return SYSTEM_PROMPT_TEMPLATE.format(
        city_name=city.name,
        city_state=city.state,
        total_problems=summary["total_problems"],
        critical_problems=summary["critical_problems"],
        health_score=summary["infrastructure_health_score"],
        health_label=summary["infrastructure_health_label"],
        type_breakdown=context["type_breakdown"],
        organizations=orgs_text,
        tips=tips_text,
    )


def _call_llm(city: City, context: dict, message: str, history: list[ChatMessage]) -> str | None:
    settings = get_settings()
    if not settings.LLM_API_KEY:
        return None

    messages = [{"role": "system", "content": _system_prompt(city, context)}]
    for h in history[-10:]:  # keep the payload small - last 10 turns of context is plenty
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": message})

    try:
        resp = httpx.post(
            f"{settings.LLM_API_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"},
            json={"model": settings.LLM_MODEL, "messages": messages, "temperature": 0.4, "max_tokens": 500},
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001 - any LLM failure must fall back, never break the chat
        logger.warning("LLM chat call failed, falling back to rule-based assistant: %s", exc)
        return None


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
            "To report a problem: go to Inspect & Analyze, upload a street photo, and either let the model "
            "detect it or log it manually with the type and severity you observe. It'll show up immediately "
            "on City Monitor and in the Action Center's priority queue."
        )

    if matches("status", "track", "progress", "resolved"):
        return (
            "Problems move through Detected → Verified → In Progress → Resolved. You can track any problem's "
            "status on City Monitor (click a marker) or manage the whole queue in the Action Center."
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


def get_chat_reply(db: Session, city: City, message: str, history: list[ChatMessage]) -> tuple[str, str]:
    """Returns (reply, mode) where mode is 'llm' or 'rule_based'."""
    context = _build_context(db, city)

    llm_reply = _call_llm(city, context, message, history)
    if llm_reply:
        return llm_reply, "llm"

    return _rule_based_reply(db, city, message, context), "rule_based"
