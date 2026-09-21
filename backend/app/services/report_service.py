"""
Reporting service backing `POST /reports`.

Produces a concise, professional PDF summary (not a meaningless 50-page
dump - project rule 30) using ReportLab, and a structured CSV export of
problem records for spreadsheet analysis.
"""
import csv
import io
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.analytics.recurring import get_recurring_problems
from app.models.city import City
from app.models.enums import ProblemStatus, Severity
from app.models.problem import Problem
from app.services.city_service import get_city_summary

NAVY = colors.HexColor("#0B2545")
ORANGE = colors.HexColor("#FD6001")
MUTED = colors.HexColor("#5B6472")


def _problems_in_window(db: Session, city_id: int, days: int) -> list[Problem]:
    since = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(Problem)
        .options(joinedload(Problem.location), joinedload(Problem.risk_score))
        .where(Problem.city_id == city_id, Problem.first_detected_at >= since)
        .order_by(Problem.first_detected_at.desc())
    )
    return list(db.execute(stmt).unique().scalars().all())


def generate_pdf_report(db: Session, city: City, days: int = 30) -> bytes:
    summary = get_city_summary(db, city)
    problems = _problems_in_window(db, city.id, days)
    recurring = get_recurring_problems(db, city.id, limit=10)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("NeceTitle", parent=styles["Title"], textColor=NAVY, fontSize=20)
    heading_style = ParagraphStyle("NeceHeading", parent=styles["Heading2"], textColor=NAVY, spaceBefore=14)
    body_style = ParagraphStyle("NeceBody", parent=styles["BodyText"], textColor=colors.HexColor("#1A1A1A"))
    muted_style = ParagraphStyle("NeceMuted", parent=styles["BodyText"], textColor=MUTED, fontSize=9)

    elements = [
        Paragraph("NeceCity Infrastructure Report", title_style),
        Paragraph(f"{city.name}, {city.state}", body_style),
        Paragraph(
            f"Reporting period: last {days} days &nbsp;&bull;&nbsp; Generated: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}",
            muted_style,
        ),
        Spacer(1, 10 * mm),
    ]

    overview_data = [
        ["Total problems (period)", str(len(problems))],
        ["Total problems (all time)", str(summary["total_problems"])],
        ["Critical", str(summary["critical_problems"])],
        ["High priority", str(summary["high_priority_problems"])],
        ["Resolved", str(summary["resolved_problems"])],
        ["Unresolved", str(summary["unresolved_problems"])],
        ["Infrastructure health", f"{summary['infrastructure_health_score']} / 100 ({summary['infrastructure_health_label']})"],
    ]
    elements.append(Paragraph("Overview", heading_style))
    t = Table(overview_data, colWidths=[80 * mm, 80 * mm])
    t.setStyle(_summary_table_style())
    elements.append(t)

    elements.append(Paragraph("Severity distribution", heading_style))
    sev_data = [["Severity", "Count"]] + [
        [s.value.title(), str(summary["severity_breakdown"][s.value])] for s in Severity
    ]
    t2 = Table(sev_data, colWidths=[80 * mm, 80 * mm])
    t2.setStyle(_header_table_style())
    elements.append(t2)

    elements.append(Paragraph("Major problem types", heading_style))
    type_rows = sorted(summary["problem_type_breakdown"].items(), key=lambda kv: -kv[1])[:6]
    type_data = [["Problem type", "Count"]] + [[t_.replace("_", " ").title(), str(c)] for t_, c in type_rows]
    t3 = Table(type_data, colWidths=[80 * mm, 80 * mm])
    t3.setStyle(_header_table_style())
    elements.append(t3)

    elements.append(Paragraph("Top priority locations", heading_style))
    top_priority = sorted(
        [p for p in problems if p.risk_score is not None], key=lambda p: -p.risk_score.score
    )[:8]
    if top_priority:
        pr_data = [["#", "Type", "Severity", "Risk score", "Road"]]
        for i, p in enumerate(top_priority, start=1):
            pr_data.append([
                str(i), p.problem_type.value.replace("_", " ").title(), p.severity.value.title(),
                f"{p.risk_score.score:.0f}", p.location.road_name or "-",
            ])
        t4 = Table(pr_data, colWidths=[10 * mm, 45 * mm, 30 * mm, 25 * mm, 50 * mm])
        t4.setStyle(_header_table_style())
        elements.append(t4)
    else:
        elements.append(Paragraph("No prioritized problems in this period.", body_style))

    elements.append(Paragraph("Recurring problems", heading_style))
    if recurring:
        rec_data = [["Type", "Recurrences", "Road"]] + [
            [r.problem_type.replace("_", " ").title(), str(r.recurrence_count), r.road_name or "-"]
            for r in recurring[:8]
        ]
        t5 = Table(rec_data, colWidths=[60 * mm, 30 * mm, 70 * mm])
        t5.setStyle(_header_table_style())
        elements.append(t5)
    else:
        elements.append(Paragraph("No recurring problems detected.", body_style))

    elements.append(Paragraph("Resolution statistics", heading_style))
    resolved_count = summary["resolved_problems"]
    total = summary["total_problems"]
    resolution_rate = (resolved_count / total * 100) if total else 0
    elements.append(Paragraph(f"Resolution rate: {resolution_rate:.0f}% ({resolved_count} of {total} problems resolved).", body_style))

    elements.append(Paragraph("Recommendations", heading_style))
    recs = _generate_recommendations(summary, recurring)
    for r in recs:
        elements.append(Paragraph(f"&bull; {r}", body_style))

    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph(
        "Generated by NeceCity - urban infrastructure monitoring & decision-support system. "
        "Demo/seed data is included where noted and should not be treated as official municipal records.",
        muted_style,
    ))

    doc.build(elements)
    return buffer.getvalue()


def _generate_recommendations(summary: dict, recurring: list) -> list[str]:
    recs = []
    if summary["critical_problems"] > 0:
        recs.append(f"Prioritize the {summary['critical_problems']} critical-severity problem(s) for immediate dispatch.")
    if recurring:
        recs.append(f"Investigate root causes at the {len(recurring)} recurring-problem location(s) rather than repeated point fixes.")
    if summary["infrastructure_health_score"] < 60:
        recs.append("Overall infrastructure health is below 'Fair' - consider increasing maintenance frequency.")
    if not recs:
        recs.append("No urgent action items - continue routine monitoring.")
    return recs


def _header_table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
    ])


def _summary_table_style() -> TableStyle:
    return TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
    ])


def generate_csv_export(db: Session, city_id: int, days: int = 30) -> str:
    problems = _problems_in_window(db, city_id, days)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "problem_type", "severity", "status", "latitude", "longitude", "road_name",
        "recurrence_count", "risk_score", "is_demo", "first_detected_at", "last_detected_at",
    ])
    for p in problems:
        writer.writerow([
            p.id, p.problem_type.value, p.severity.value, p.status.value,
            p.location.latitude, p.location.longitude, p.location.road_name or "",
            p.recurrence_count, p.risk_score.score if p.risk_score else "",
            p.is_demo, p.first_detected_at.isoformat(), p.last_detected_at.isoformat(),
        ])
    return output.getvalue()
