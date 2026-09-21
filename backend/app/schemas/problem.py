from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    latitude: float
    longitude: float
    address_text: str | None
    road_name: str | None
    road_importance: str
    ward_id: int | None


class RiskComponentOut(BaseModel):
    raw: float
    weight: float
    contribution: float


class RiskScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float
    components: dict[str, RiskComponentOut]
    weights_version: str
    recommended_action: str
    reasons: list[str] = []


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    source: str


class ProblemListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    problem_type: str
    severity: str
    status: str
    latitude: float
    longitude: float
    ward_id: int | None
    road_name: str | None
    recurrence_count: int
    is_demo: bool
    risk_score: float | None
    first_detected_at: datetime
    last_detected_at: datetime


class ProblemDetailOut(BaseModel):
    id: int
    problem_type: str
    severity: str
    status: str
    description: str | None
    recurrence_count: int
    is_demo: bool
    location: LocationOut
    risk: RiskScoreOut | None
    image: ImageOut | None
    confidence: float | None = None
    first_detected_at: datetime
    last_detected_at: datetime
    resolution: "ResolutionOut | None" = None


class ResolutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    started_at: datetime | None
    resolved_at: datetime | None
    resolution_time_hours: float | None
    notes: str | None
    before_image_id: int | None
    after_image_id: int | None


class ProblemStatusUpdate(BaseModel):
    status: str
    notes: str | None = None


class PaginatedProblems(BaseModel):
    items: list[ProblemListItemOut]
    total: int
    page: int
    page_size: int
