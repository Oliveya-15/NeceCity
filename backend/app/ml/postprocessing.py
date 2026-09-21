"""
Postprocessing turns raw YOLO bounding boxes into `ScoredDetection`s by
attaching a *suggested* severity.

This is a deliberately simple, deterministic, fully-documented heuristic -
NOT a second ML model and NOT the final word. It only pre-fills a sensible
default; the human reviewer in Inspect & Analyze can always override it
with [Edit Severity] before the detection becomes a stored Problem. This
keeps with the project's "no fake AI" rule: this function is explicitly
rule-based, not something that pretends to be learned.

Heuristic:
    severity_score = 0.6 * class_base_weight + 0.4 * relative_box_area
    (relative_box_area is clamped so a very large box cannot alone force
    "critical" for an inherently minor class like a damaged sign)
"""
from app.ml.schema import RawDetection, ScoredDetection
from app.models.enums import ProblemType, Severity

# How inherently disruptive each problem type tends to be, all else equal.
# Documented, tunable constants - not hidden magic numbers.
CLASS_BASE_WEIGHT: dict[ProblemType, float] = {
    ProblemType.POTHOLE: 0.65,
    ProblemType.ROAD_DAMAGE: 0.70,
    ProblemType.OPEN_DRAIN: 0.75,
    ProblemType.WATERLOGGING: 0.60,
    ProblemType.GARBAGE: 0.35,
    ProblemType.DAMAGED_ROAD_SIGN: 0.30,
}

_SEVERITY_BINS = [
    (0.75, Severity.CRITICAL),
    (0.55, Severity.HIGH),
    (0.35, Severity.MEDIUM),
    (0.0, Severity.LOW),
]


def _relative_area(det: RawDetection) -> float:
    width = max(det.bbox_x_max - det.bbox_x_min, 0.0)
    height = max(det.bbox_y_max - det.bbox_y_min, 0.0)
    area = width * height  # already normalized 0-1, since bbox coords are normalized
    return min(area * 6, 1.0)  # scale up: a box covering ~17% of the frame already reads as "large"


def suggest_severity(det: RawDetection) -> Severity:
    class_weight = CLASS_BASE_WEIGHT.get(det.problem_type, 0.5)
    area_score = _relative_area(det)
    severity_score = 0.6 * class_weight + 0.4 * area_score

    for threshold, severity in _SEVERITY_BINS:
        if severity_score >= threshold:
            return severity
    return Severity.LOW


def score_detections(raw_detections: list[RawDetection]) -> list[ScoredDetection]:
    scored: list[ScoredDetection] = []
    for det in raw_detections:
        severity = suggest_severity(det)
        scored.append(
            ScoredDetection(
                problem_type=det.problem_type,
                confidence=det.confidence,
                bbox_x_min=det.bbox_x_min,
                bbox_y_min=det.bbox_y_min,
                bbox_x_max=det.bbox_x_max,
                bbox_y_max=det.bbox_y_max,
                severity_suggested=severity,
            )
        )
    return scored
