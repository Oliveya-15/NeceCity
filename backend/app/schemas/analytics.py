from pydantic import BaseModel


class TypeCount(BaseModel):
    problem_type: str
    count: int


class SeverityCount(BaseModel):
    severity: str
    count: int


class AreaCount(BaseModel):
    ward_id: int | None
    ward_name: str
    count: int
    problems_per_1000_sqm: float | None = None


class TrendPoint(BaseModel):
    period: str  # ISO week or month label, e.g. "2026-W35"
    count: int


class DataInsight(BaseModel):
    text: str
    kind: str  # e.g. "concentration", "recurrence", "trend"


class OverviewAnalyticsOut(BaseModel):
    by_type: list[TypeCount]
    by_severity: list[SeverityCount]
    by_area: list[AreaCount]
    insights: list[DataInsight]


class TrendsAnalyticsOut(BaseModel):
    granularity: str  # "week" | "month"
    points: list[TrendPoint]
    insights: list[DataInsight]


class HotspotOut(BaseModel):
    location_id: int
    latitude: float
    longitude: float
    problem_count: int
    dominant_type: str
    cluster_id: int


class HotspotsAnalyticsOut(BaseModel):
    algorithm: str
    hotspots: list[HotspotOut]
    insights: list[DataInsight]


class RecurringProblemOut(BaseModel):
    problem_id: int
    problem_type: str
    latitude: float
    longitude: float
    recurrence_count: int
    road_name: str | None
