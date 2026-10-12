"""
NeceCity ML inference service.

Loads the project's own trained YOLO weights (see ml/weights/README.md)
and runs local inference - there is no external AI API call anywhere in
this module.

Per project rule 29 ("model failure handling"), if `ultralytics`/`torch`
are not installed, or the weights file at `settings.MODEL_PATH` does not
exist, the detector simply reports itself as unavailable instead of
raising on import or crashing the application. `Inspect & Analyze` then
shows "ML model is not configured..." while the rest of the app (Command
Center, City Monitor, Insights, Action Center) continues to work off
existing database/demo data.

It also reads an optional provenance sidecar file
(`<weights>.meta.json`, written by `ml/training/train.py`) so the app can
honestly warn when a loaded model was trained only on the bundled
SYNTHETIC placeholder dataset (`ml/data/demo_dataset`) - such a model
loads and runs successfully, but will not meaningfully detect real-world
problems in real photos, because it never saw one during training. This
is not a bug to "fix" in code; it is a training-data limitation the app
should explain rather than hide.
"""
import json
from pathlib import Path
from threading import Lock

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ml.classes import load_class_index
from app.ml.postprocessing import score_detections
from app.ml.schema import InferenceResponse, RawDetection

logger = get_logger(__name__)

try:
    from ultralytics import YOLO  # heavy import: torch + ultralytics
    _ULTRALYTICS_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when torch/ultralytics aren't installed
    _ULTRALYTICS_AVAILABLE = False

# Lightweight torch-free backend, used when MODEL_PATH points to a .onnx file
# (this is what the free-hosting deployment uses - see DEPLOYMENT.md).
from app.ml.onnx_runtime import ONNX_AVAILABLE as _ONNX_AVAILABLE, OnnxYolo


class NeceCityDetector:
    """
    Thin, lazily-initialized wrapper around an Ultralytics YOLO model.
    A single process-wide instance is created via `get_detector()` so the
    (potentially large) model is loaded into memory only once.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._lock = Lock()
        self._model = None
        self._class_index = load_class_index()
        self._unavailable_reason: str | None = None
        self._training_data_warning: str | None = None
        self._load()

    def _load_provenance_warning(self, weights_path: Path) -> str | None:
        # nececity_yolo.pt -> nececity_yolo.meta.json (sits alongside the weights)
        meta_path = weights_path.parent / f"{weights_path.stem}.meta.json"

        if not meta_path.exists():
            return (
                "No training-data provenance metadata found for this model (expected at "
                f"'{meta_path.name}'). If it was trained on the bundled synthetic demo "
                "dataset, real-world detection will be very unreliable - retrain with the "
                "current ml/training/train.py to get this check automatically, or see "
                "ml/data/README.md."
            )

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read model provenance metadata: %s", exc)
            return None

        if meta.get("is_bundled_demo_dataset"):
            return (
                "This model was trained only on the bundled SYNTHETIC placeholder dataset "
                "(programmatically-drawn shapes, not real photos) - see ml/data/README.md. "
                "It will not reliably detect real-world infrastructure problems. Train on a "
                "real annotated dataset for usable detections."
            )
        return None

    def _load(self) -> None:
        weights_path: Path = self._settings.resolved_model_path
        self._use_onnx = weights_path.suffix.lower() == ".onnx"

        if self._use_onnx:
            if not _ONNX_AVAILABLE:
                self._unavailable_reason = "The 'onnxruntime' package is not installed in this environment."
                logger.warning("ML model not loaded: %s", self._unavailable_reason)
                return
        elif not _ULTRALYTICS_AVAILABLE:
            self._unavailable_reason = (
                "The 'ultralytics'/'torch' packages are not installed in this environment."
            )
            logger.warning("ML model not loaded: %s", self._unavailable_reason)
            return

        if not weights_path.exists():
            self._unavailable_reason = (
                f"Model weights not found at '{weights_path}'. "
                "Train the model (see ml/training/train.py) or place the "
                "provided weights file there, then set MODEL_PATH."
            )
            logger.warning("ML model not loaded: %s", self._unavailable_reason)
            return

        try:
            self._model = OnnxYolo(str(weights_path)) if self._use_onnx else YOLO(str(weights_path))
            self._training_data_warning = self._load_provenance_warning(weights_path)
            logger.info("NeceCity YOLO model loaded from %s", weights_path)
            if self._training_data_warning:
                logger.warning("Model provenance warning: %s", self._training_data_warning)
        except Exception as exc:  # noqa: BLE001 - any load failure must degrade gracefully
            self._unavailable_reason = f"Failed to load model weights: {exc}"
            logger.error("ML model failed to load: %s", exc)
            self._model = None

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def unavailable_reason(self) -> str | None:
        return self._unavailable_reason

    @property
    def training_data_warning(self) -> str | None:
        return self._training_data_warning

    @property
    def model_version(self) -> str:
        return self._settings.resolved_model_path.stem

    def predict(self, image_path: str, image_width: int, image_height: int) -> InferenceResponse:
        if not self.is_ready:
            return InferenceResponse(
                model_available=False,
                model_version=None,
                image_width=image_width,
                image_height=image_height,
                detections=[],
                message=self._unavailable_reason
                or "ML model is not configured. Add the trained NeceCity model weights and configure MODEL_PATH.",
            )

        if self._use_onnx:
            return self._predict_onnx(image_path, image_width, image_height)

        with self._lock:  # ultralytics models are not guaranteed thread-safe
            # Use the LOW floor here, not MODEL_CONFIDENCE_THRESHOLD: the API layer
            # flags anything under the threshold as "low confidence" so the user
            # can still review it (see app/api/routes/analyze.py).
            results = self._model.predict(
                source=image_path,
                conf=min(self._settings.MODEL_MIN_CONFIDENCE, self._settings.MODEL_CONFIDENCE_THRESHOLD),
                iou=self._settings.MODEL_IOU_THRESHOLD,
                imgsz=self._settings.MODEL_IMAGE_SIZE,
                max_det=self._settings.MODEL_MAX_DETECTIONS,
                augment=self._settings.MODEL_USE_TTA,
                verbose=False,
            )

        raw_detections: list[RawDetection] = []
        if results:
            result = results[0]
            for box in result.boxes:
                class_id = int(box.cls.item())
                problem_type = self._class_index.get(class_id)
                if problem_type is None:
                    logger.warning("Unknown class id %s returned by model; skipping detection.", class_id)
                    continue
                x_min, y_min, x_max, y_max = box.xyxyn[0].tolist()  # normalized coords
                raw_detections.append(
                    RawDetection(
                        problem_type=problem_type,
                        confidence=round(float(box.conf.item()), 4),
                        bbox_x_min=round(x_min, 4),
                        bbox_y_min=round(y_min, 4),
                        bbox_x_max=round(x_max, 4),
                        bbox_y_max=round(y_max, 4),
                    )
                )

        return InferenceResponse(
            model_available=True,
            model_version=self.model_version,
            image_width=image_width,
            image_height=image_height,
            detections=score_detections(raw_detections),
            training_data_warning=self._training_data_warning,
        )


    def _predict_onnx(self, image_path: str, image_width: int, image_height: int) -> InferenceResponse:
        with self._lock:
            boxes = self._model.predict(
                image_path,
                conf=min(self._settings.MODEL_MIN_CONFIDENCE, self._settings.MODEL_CONFIDENCE_THRESHOLD),
                iou=self._settings.MODEL_IOU_THRESHOLD,
                imgsz=self._settings.MODEL_IMAGE_SIZE,
                max_det=self._settings.MODEL_MAX_DETECTIONS,
            )  # note: test-time augmentation (MODEL_USE_TTA) is not available in the ONNX backend

        raw_detections: list[RawDetection] = []
        for box in boxes:
            problem_type = self._class_index.get(box.class_id)
            if problem_type is None:
                logger.warning("Unknown class id %s returned by model; skipping detection.", box.class_id)
                continue
            raw_detections.append(
                RawDetection(
                    problem_type=problem_type,
                    confidence=round(box.confidence, 4),
                    bbox_x_min=round(box.x_min, 4),
                    bbox_y_min=round(box.y_min, 4),
                    bbox_x_max=round(box.x_max, 4),
                    bbox_y_max=round(box.y_max, 4),
                )
            )
        return InferenceResponse(
            model_available=True,
            model_version=self.model_version,
            image_width=image_width,
            image_height=image_height,
            detections=score_detections(raw_detections),
            training_data_warning=self._training_data_warning,
        )


_detector_instance: NeceCityDetector | None = None
_detector_lock = Lock()


def get_detector() -> NeceCityDetector:
    """Process-wide singleton accessor (FastAPI dependency-friendly)."""
    global _detector_instance
    if _detector_instance is None:
        with _detector_lock:
            if _detector_instance is None:
                _detector_instance = NeceCityDetector()
    return _detector_instance
