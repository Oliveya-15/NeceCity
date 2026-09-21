"""
Trend analytics: problem counts over time, grouped by week or month using
pandas, with a deterministic trend-direction insight.
"""
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.problem import Problem
from app.schemas.analytics import DataInsight, TrendPoint, TrendsAnalyticsOut

TREND_INCREASE_THRESHOLD = 0.20  # flag a >=20% change as a notable trend


def get_trends(db: Session, city_id: int, granularity: str = "week", periods: int = 12) -> TrendsAnalyticsOut:
    since = datetime.utcnow() - timedelta(weeks=periods if granularity == "week" else periods * 4)
    rows = db.execute(
        select(Problem.first_detected_at).where(Problem.city_id == city_id, Problem.first_detected_at >= since)
    ).scalars().all()

    if not rows:
        return TrendsAnalyticsOut(granularity=granularity, points=[], insights=[])

    df = pd.DataFrame({"detected_at": pd.to_datetime(rows)})
    freq = "W" if granularity == "week" else "M"
    grouped = df.set_index("detected_at").resample(freq).size()

    points = [
        TrendPoint(period=idx.strftime("%Y-%m-%d"), count=int(count))
        for idx, count in grouped.items()
    ]

    insights: list[DataInsight] = []
    if len(points) >= 2:
        recent = points[-1].count
        previous = points[-2].count
        if previous > 0:
            change = (recent - previous) / previous
            if abs(change) >= TREND_INCREASE_THRESHOLD:
                direction = "increased" if change > 0 else "decreased"
                insights.append(
                    DataInsight(
                        kind="trend",
                        text=(
                            f"Problem reports {direction} by {abs(change):.0%} in the most recent "
                            f"{granularity} compared to the previous one ({previous} to {recent})."
                        ),
                    )
                )

    return TrendsAnalyticsOut(granularity=granularity, points=points, insights=insights)
