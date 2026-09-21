from pydantic import BaseModel, ConfigDict, Field


class BoundingBox(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float


class DetectionOut(BaseModel):
    id: int | None = None  # None until persisted
    problem_type: str
    confidence: float
    severity_suggested: str
    bbox: BoundingBox


class AnalyzeImageResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    image_id: int
    model_available: bool
    model_version: str | None
    message: str | None = None
    training_data_warning: str | None = None
    image_width: int | None
    image_height: int | None
    detections: list[DetectionOut]


class DetectionVerifyRequest(BaseModel):
    action: str = Field(description="one of: confirm, reject")
    final_severity: str | None = Field(default=None, description="required when action=confirm")
    latitude: float
    longitude: float
    city_id: int
    ward_id: int | None = None
    road_name: str | None = None
    road_importance: str = "local"
    near_important_infrastructure: bool = False
    infrastructure_note: str | None = None


class DetectionVerifyResponse(BaseModel):
    detection_id: int
    status: str
    problem_id: int | None = None


class ManualProblemRequest(BaseModel):
    """
    Used by Inspect & Analyze's manual-entry fallback: lets a user log a
    problem directly (with problem type + severity they select themselves)
    when no trained ML model is configured yet, or when they want to
    record something the model didn't catch. Optionally links the
    already-uploaded image for reference.
    """
    problem_type: str
    severity: str
    latitude: float
    longitude: float
    city_id: int
    ward_id: int | None = None
    road_name: str | None = None
    road_importance: str = "local"
    near_important_infrastructure: bool = False
    infrastructure_note: str | None = None
    image_id: int | None = None


class ManualProblemResponse(BaseModel):
    problem_id: int
