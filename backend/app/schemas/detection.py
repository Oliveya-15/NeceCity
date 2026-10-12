from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    # "model" = produced by YOLO, "user" = region drawn by the reporter.
    source: str = "model"
    # True when the model is unsure (below MODEL_CONFIDENCE_THRESHOLD) - the UI
    # asks the reviewer to double-check these.
    low_confidence: bool = False


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



class UserRegionRequest(BaseModel):
    """
    A region the reporter drew on the photo themselves (used when the model
    misses a problem, e.g. on a photo unlike its training data). Coordinates
    are normalized 0-1 relative to the image, same as model detections.
    """
    image_id: int
    problem_type: str
    severity: str
    x_min: float = Field(ge=0.0, le=1.0)
    y_min: float = Field(ge=0.0, le=1.0)
    x_max: float = Field(ge=0.0, le=1.0)
    y_max: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_box(self):
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("Region must have a positive width and height.")
        if (self.x_max - self.x_min) < 0.01 or (self.y_max - self.y_min) < 0.01:
            raise ValueError("Region is too small - draw a larger area around the problem.")
        return self
