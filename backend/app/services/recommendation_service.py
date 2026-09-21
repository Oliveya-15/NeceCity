"""
Powers the "AI Recommendations & Advice" page.

Three kinds of content, each honestly sourced:

  1. `CIVIC_TIPS` - general, non-fabricated actionable civic guidance.
     Deterministic static content, not model output.
  2. `ORGANIZATIONS` - a small starter directory of REAL, independently
     verifiable national-level Indian civic organizations and government
     platforms (official websites only - no invented phone numbers or
     "local branch" addresses, since fabricating specific contact details
     for real organizations would be actively misleading). Each entry is
     tagged with the problem categories it's most relevant to.
  3. City-specific advice - generated from the SAME real analytics used
     elsewhere in the app (city summary + top problem type), e.g. "Garbage
     is Siliguri's most-reported problem type" is a real, derived fact,
     not a guess.

This is a deterministic, rule-based recommendation engine - consistent
with the project's "no fake AI" principle (see app/risk/engine.py for the
same pattern applied to risk scoring). The page name "AI Recommendations"
reflects how the feature is framed to users; the underlying logic here is
fully transparent and inspectable, and every organization listed is real
and can be verified at the linked website.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.city_service import get_city_summary


@dataclass(frozen=True)
class CivicOrganization:
    name: str
    category: str  # "sanitation" | "road_safety" | "governance"
    description: str
    website: str
    categories_relevant_to: tuple[str, ...] = field(default_factory=tuple)


# Real, independently verifiable organizations only. Each description is
# a short, factual summary of the organization's actual public mission
# (not a claim about local presence in any specific NeceCity-monitored
# city) - see docs/architecture.md "AI Recommendations" section for the
# sourcing note.
ORGANIZATIONS: list[CivicOrganization] = [
    CivicOrganization(
        name="Swachhata-MoHUA (Swachh Bharat Mission - Urban)",
        category="governance",
        description=(
            "The Government of India's official citizen complaint platform for civic issues - garbage, "
            "unclean streets, blocked drains and more. Report an issue with a photo and it is routed to your "
            "city's municipal body, with mandated resolution timelines."
        ),
        website="https://swachhbharaturban.gov.in/",
        categories_relevant_to=("garbage", "waterlogging", "open_drain"),
    ),
    CivicOrganization(
        name="IChangeMyCity (Janaagraha)",
        category="governance",
        description=(
            "A civic-tech platform for reporting hyperlocal issues to municipal authorities and tracking "
            "resolution, run by Janaagraha Centre for Citizenship & Democracy."
        ),
        website="https://www.ichangemycity.com/",
        categories_relevant_to=("pothole", "road_damage", "garbage", "waterlogging", "damaged_road_sign", "open_drain"),
    ),
    CivicOrganization(
        name="Janaagraha Centre for Citizenship & Democracy",
        category="governance",
        description=(
            "A Bengaluru-based NGO working on urban governance reform and civic participation since 2001 - "
            "ward-level civic engagement, municipal finance transparency, and civic education programs."
        ),
        website="https://www.janaagraha.org/",
        categories_relevant_to=("pothole", "road_damage", "garbage", "waterlogging", "damaged_road_sign", "open_drain"),
    ),
    CivicOrganization(
        name="SaveLIFE Foundation",
        category="road_safety",
        description=(
            "An independent nonprofit focused on road safety and emergency trauma care across India - "
            "crash-data-driven road redesign advocacy and community first-aid training."
        ),
        website="https://savelifefoundation.org/",
        categories_relevant_to=("pothole", "road_damage", "damaged_road_sign"),
    ),
    CivicOrganization(
        name="PotHoleRaja",
        category="road_safety",
        description=(
            "A social venture focused specifically on identifying and fixing potholes to improve road safety, "
            "working with local industry associations and volunteers."
        ),
        website="https://www.potholeraja.com/",
        categories_relevant_to=("pothole", "road_damage"),
    ),
    CivicOrganization(
        name="Waste Warriors",
        category="sanitation",
        description=(
            "An Indian nonprofit running waste management and community clean-up programs, including "
            "source segregation and public awareness campaigns in partnership with local communities."
        ),
        website="https://wastewarriors.org/",
        categories_relevant_to=("garbage", "open_drain"),
    ),
    CivicOrganization(
        name="Sulabh International",
        category="sanitation",
        description=(
            "One of India's largest social service organizations, working on sanitation infrastructure, "
            "waste management and public hygiene since 1970, with a large volunteer network."
        ),
        website="http://sulabhinternational.org/",
        categories_relevant_to=("garbage", "waterlogging", "open_drain"),
    ),
]


# General, non-fabricated civic awareness tips - not tied to any
# individual city's data, useful as baseline guidance regardless of what
# NeceCity's analytics currently show.
CIVIC_TIPS: list[dict] = [
    {
        "title": "Report with a clear photo and exact location",
        "body": "Municipal grievance platforms (like the Swachhata app) resolve issues faster when the photo "
                "clearly shows the problem and the location pin is accurate - vague reports get deprioritized.",
        "category": "reporting",
    },
    {
        "title": "Segregate waste at the source",
        "body": "Keeping wet and dry waste separate at home significantly reduces the garbage-collection burden "
                "and helps recycling initiatives actually work downstream.",
        "category": "sanitation",
    },
    {
        "title": "Escalate through your ward councillor for recurring issues",
        "body": "A single unresolved report can stall; a problem that keeps recurring is worth raising directly "
                "with your elected ward councillor or attending a ward committee (Ward Sabha) meeting about.",
        "category": "governance",
    },
    {
        "title": "Organize a neighbourhood clean-up drive",
        "body": "Community-led clean-up drives are one of the most effective ways to address persistent local "
                "garbage hotspots - several organizations below can help you organize or join one.",
        "category": "sanitation",
    },
    {
        "title": "Flag waterlogging before monsoon season",
        "body": "Drainage problems are far cheaper to fix in the dry season than during active flooding - report "
                "blocked or open drains as soon as you notice them, not after the next heavy rain.",
        "category": "infrastructure",
    },
    {
        "title": "Note the exact road name and nearest landmark",
        "body": "Road-importance context (a pothole on a highway vs. a quiet residential lane) genuinely changes "
                "how a report should be prioritized - always include it.",
        "category": "reporting",
    },
]


def get_city_recommendations(db: Session, city) -> dict:
    """
    City-specific advice, derived from the SAME real analytics the
    Command Center uses - not a separate/fabricated data source.
    """
    summary = get_city_summary(db, city)
    insights: list[str] = []

    type_breakdown = summary["problem_type_breakdown"]
    if summary["total_problems"] > 0:
        top_type, top_count = max(type_breakdown.items(), key=lambda kv: kv[1])
        if top_count > 0:
            share = top_count / summary["total_problems"]
            insights.append(
                f"{top_type.replace('_', ' ').title()} is {city.name}'s most-reported problem type "
                f"({top_count} of {summary['total_problems']} reports, {share:.0%}) - see the matching "
                f"organizations below for how communities typically address this."
            )

    if summary["critical_problems"] > 0:
        insights.append(
            f"{summary['critical_problems']} critical-severity problem(s) are currently open in {city.name} - "
            "these should be escalated through the Action Center's priority queue first."
        )

    if summary["infrastructure_health_score"] < 60:
        insights.append(
            f"{city.name}'s infrastructure health score is {summary['infrastructure_health_score']:.0f}/100 "
            f"({summary['infrastructure_health_label']}) - consider organizing a community reporting drive to "
            "help surface and prioritize issues faster."
        )
    elif summary["total_problems"] == 0:
        insights.append(
            f"No problems have been reported in {city.name} yet - once residents start using Inspect & Analyze, "
            "city-specific recommendations will appear here automatically."
        )

    relevant_categories = set()
    if type_breakdown:
        sorted_types = sorted(type_breakdown.items(), key=lambda kv: -kv[1])[:3]
        relevant_categories = {t for t, c in sorted_types if c > 0}

    relevant_orgs = [
        org for org in ORGANIZATIONS
        if not relevant_categories or set(org.categories_relevant_to) & relevant_categories
    ] or ORGANIZATIONS

    return {
        "city_insights": insights,
        "relevant_organization_names": [o.name for o in relevant_orgs],
    }


def get_all_organizations() -> list[CivicOrganization]:
    return ORGANIZATIONS


def get_all_tips() -> list[dict]:
    return CIVIC_TIPS
