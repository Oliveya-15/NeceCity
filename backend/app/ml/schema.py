"""
Plain dataclasses describing the shape of ML inference output. Kept
separate from the Pydantic API schemas (app/schemas) because this is an
internal contract between app/ml/* modules, not a wire format.
"""
from dataclasses import dataclass

from app.models.enums import ProblemType, Severity


@dataclass
class RawDetection:
    """One bounding box exactly as produced by the YOLO model."""
    problem_type: ProblemType
    confidence: float
    bbox_x_min: float  # normalized 0-1
    bbox_y_min: float
    bbox_x_max: float
    bbox_y_max: float


@dataclass
class ScoredDetection(RawDetection):
    """A RawDetection enriched with the deterministic severity heuristic."""
    severity_suggested: Severity = Severity.LOW


@dataclass
class InferenceResponse:
    model_available: bool
    model_version: str | None
    image_width: int | None
    image_height: int | None
    detections: list[ScoredDetection]
    message: str | None = None  # populated when model_available is False
    training_data_warning: str | None = None  # populated when the loaded model's data provenance is questionable
