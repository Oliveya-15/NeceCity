from pydantic import BaseModel, ConfigDict


class CityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    state: str
    center_latitude: float
    center_longitude: float
    default_zoom: int
    is_active: bool


class SeverityBreakdown(BaseModel):
    low: int
    medium: int
    high: int
    critical: int


class StatusBreakdown(BaseModel):
    detected: int
    verified: int
    in_progress: int
    resolved: int


class CitySummaryOut(BaseModel):
    city: CityOut
    total_problems: int
    critical_problems: int
    high_priority_problems: int
    resolved_problems: int
    unresolved_problems: int
    severity_breakdown: SeverityBreakdown
    status_breakdown: StatusBreakdown
    problem_type_breakdown: dict[str, int]
    infrastructure_health_score: float  # 0-100, higher = healthier
    infrastructure_health_label: str
    has_demo_data: bool
