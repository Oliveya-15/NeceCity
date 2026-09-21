"""
Verifies the ML model failure-handling requirement: when weights are
missing (or ultralytics/torch aren't installed), the detector must report
itself unavailable rather than raising - so the rest of the app keeps
working (see app/ml/inference.py docstring).
"""
from app.ml.inference import NeceCityDetector


def test_detector_degrades_gracefully_when_weights_missing():
    detector = NeceCityDetector()
    # In this test environment there is no trained weights file at
    # MODEL_PATH, so the detector must not be "ready" - but constructing
    # it must not raise.
    if not detector.is_ready:
        assert detector.unavailable_reason is not None


def test_predict_on_unavailable_model_returns_structured_response(tmp_path):
    detector = NeceCityDetector()
    if detector.is_ready:
        return  # a real model happens to be configured in this environment - nothing to test here
    response = detector.predict(str(tmp_path / "does_not_matter.jpg"), image_width=640, image_height=480)
    assert response.model_available is False
    assert response.detections == []
    assert response.message is not None
    assert "MODEL_PATH" in response.message or "ultralytics" in response.message or "torch" in response.message


def test_provenance_warning_flags_bundled_demo_dataset(tmp_path):
    """
    A model trained on the bundled synthetic demo dataset must produce a
    clear, honest warning - not silently pretend to be a real detector.
    """
    detector = NeceCityDetector()
    weights_path = tmp_path / "nececity_yolo.pt"
    meta_path = tmp_path / "nececity_yolo.meta.json"
    meta_path.write_text('{"is_bundled_demo_dataset": true, "dataset_path": "/x/ml/data/demo_dataset"}')

    warning = detector._load_provenance_warning(weights_path)
    assert warning is not None
    assert "synthetic" in warning.lower()


def test_provenance_warning_silent_for_real_dataset(tmp_path):
    detector = NeceCityDetector()
    weights_path = tmp_path / "nececity_yolo.pt"
    meta_path = tmp_path / "nececity_yolo.meta.json"
    meta_path.write_text('{"is_bundled_demo_dataset": false, "dataset_path": "/x/my_real_dataset"}')

    warning = detector._load_provenance_warning(weights_path)
    assert warning is None


def test_provenance_warning_when_metadata_missing(tmp_path):
    """Older weights trained before this feature existed have no sidecar
    file - the app should still say something useful, not crash."""
    detector = NeceCityDetector()
    weights_path = tmp_path / "nececity_yolo.pt"

    warning = detector._load_provenance_warning(weights_path)
    assert warning is not None
    assert "metadata" in warning.lower() or "provenance" in warning.lower()
