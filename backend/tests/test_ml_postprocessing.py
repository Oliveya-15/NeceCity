from app.ml.classes import load_class_index
from app.ml.postprocessing import suggest_severity
from app.ml.schema import RawDetection
from app.models.enums import ProblemType, Severity


def test_class_index_has_six_classes():
    index = load_class_index()
    assert len(index) == 6
    assert index[0] == ProblemType.POTHOLE


def test_large_open_drain_box_suggests_high_severity():
    det = RawDetection(
        problem_type=ProblemType.OPEN_DRAIN, confidence=0.8,
        bbox_x_min=0.2, bbox_y_min=0.2, bbox_x_max=0.8, bbox_y_max=0.8,  # large box
    )
    severity = suggest_severity(det)
    assert severity in (Severity.HIGH, Severity.CRITICAL)


def test_small_damaged_sign_box_suggests_low_severity():
    det = RawDetection(
        problem_type=ProblemType.DAMAGED_ROAD_SIGN, confidence=0.5,
        bbox_x_min=0.45, bbox_y_min=0.45, bbox_x_max=0.52, bbox_y_max=0.52,  # tiny box
    )
    severity = suggest_severity(det)
    assert severity == Severity.LOW


def test_severity_is_deterministic():
    det = RawDetection(
        problem_type=ProblemType.POTHOLE, confidence=0.6,
        bbox_x_min=0.3, bbox_y_min=0.3, bbox_x_max=0.5, bbox_y_max=0.5,
    )
    assert suggest_severity(det) == suggest_severity(det)
