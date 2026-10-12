"""
Detection service - the backbone of Report Problem.

Handles:
  1. Safely persisting an uploaded image to disk.
  2. Running it through the ML inference service and storing raw Detections.
  3. Turning a human-confirmed Detection (or a manually-logged one) into a
     Problem (with an explainable RiskScore attached, and a short
     human-readable summary - see app/services/chat_service.py
     generate_report_summary).
"""
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ml.inference import get_detector
from app.ml.preprocessing import ValidatedImage
from app.models.city import City
from app.models.detection import Detection
from app.models.enums import DetectionStatus, ImageSource, ProblemStatus, RoadImportance, Severity
from app.models.image import Image
from app.models.location import Location
from app.models.problem import Problem
from app.schemas.detection import DetectionVerifyRequest
from app.services.chat_service import generate_report_summary
from app.services.problem_service import find_recent_nearby_problem, recompute_and_store_risk

logger = get_logger(__name__)

# Stored in Detection.model_version for regions drawn by a person rather than
# predicted by YOLO. Also used to tell the two apart when exporting retraining data.
USER_MARKED_VERSION = "user-marked"

_CONTENT_TYPE_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def save_uploaded_image(db: Session, raw_bytes: bytes, validated: ValidatedImage, original_filename: str | None) -> Image:
    settings = get_settings()

    # Never trust the client-supplied filename for the on-disk path - we
    # generate our own random, extension-whitelisted name (path traversal
    # / unsafe filename protection).
    extension = _CONTENT_TYPE_EXTENSION.get(validated.content_type, ".jpg")
    safe_name = f"{uuid.uuid4().hex}{extension}"
    dest_path = settings.resolved_upload_dir / safe_name
    dest_path.write_bytes(raw_bytes)

    image = Image(
        file_path=str(dest_path),
        original_filename=(original_filename or "")[:255] or None,
        content_type=validated.content_type,
        file_size_bytes=len(raw_bytes),
        width=validated.width,
        height=validated.height,
        source=ImageSource.UPLOAD,
    )
    db.add(image)
    db.flush()  # assign image.id without committing the transaction yet
    return image


def run_inference_and_store(db: Session, image: Image):
    detector = get_detector()
    inference = detector.predict(image.file_path, image.width, image.height)

    stored: list[Detection] = []
    for det in inference.detections:
        row = Detection(
            image_id=image.id,
            problem_type=det.problem_type,
            confidence=det.confidence,
            bbox_x_min=det.bbox_x_min,
            bbox_y_min=det.bbox_y_min,
            bbox_x_max=det.bbox_x_max,
            bbox_y_max=det.bbox_y_max,
            model_version=inference.model_version or "unknown",
            severity_suggested=det.severity_suggested,
            status=DetectionStatus.PENDING_REVIEW,
        )
        db.add(row)
        stored.append(row)

    db.flush()
    return inference, stored


def create_user_marked_detection(
    db: Session,
    *,
    image: Image,
    problem_type,
    severity: Severity,
    x_min: float, y_min: float, x_max: float, y_max: float,
) -> Detection:
    """A region the reporter drew on the photo. Confidence is 1.0 by definition
    (a person asserted it) but is never shown as 'model confidence' - the
    frontend and report summary check `model_version`."""
    row = Detection(
        image_id=image.id,
        problem_type=problem_type,
        confidence=1.0,
        bbox_x_min=round(x_min, 4), bbox_y_min=round(y_min, 4),
        bbox_x_max=round(x_max, 4), bbox_y_max=round(y_max, 4),
        model_version=USER_MARKED_VERSION,
        severity_suggested=severity,
        status=DetectionStatus.PENDING_REVIEW,
    )
    db.add(row)
    db.flush()
    return row


def place_or_update_problem(
    db: Session,
    *,
    city_id: int,
    problem_type,
    severity: Severity,
    latitude: float,
    longitude: float,
    ward_id: int | None = None,
    road_name: str | None = None,
    road_importance: str = "local",
    near_important_infrastructure: bool = False,
    infrastructure_note: str | None = None,
    source_detection_id: int | None = None,
    confidence: float | None = None,
) -> Problem:
    """
    Shared by both the ML-confirmed path (`verify_detection`, below) and
    the manual-entry path (`app/api/routes/problems.py create_manual`),
    used by Report Problem when no trained model is configured, when the
    model found nothing, or when a user reports something the model
    missed (project rule: the app must stay fully usable without a
    model). `confidence` is the originating Detection's model confidence
    when there is one, and is only used for the human-readable summary
    below - it never affects severity or the risk score.

    De-duplicates against an existing unresolved Problem of the same type
    within 30m (incrementing recurrence) rather than always inserting a
    new row.
    """
    existing = find_recent_nearby_problem(db, city_id, problem_type, latitude, longitude)
    if existing:
        existing.recurrence_count += 1
        existing.last_detected_at = datetime.utcnow()
        severity_order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        if severity_order.index(severity) > severity_order.index(existing.severity):
            existing.severity = severity
        recompute_and_store_risk(db, existing)
        return existing

    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    location = Location(
        city_id=city_id,
        ward_id=ward_id,
        latitude=latitude,
        longitude=longitude,
        geom=from_shape(Point(longitude, latitude), srid=4326),
        road_name=road_name,
        road_importance=RoadImportance(road_importance),
        near_important_infrastructure=near_important_infrastructure,
        infrastructure_note=infrastructure_note,
    )
    db.add(location)
    db.flush()

    city = db.get(City, city_id)
    summary = generate_report_summary(
        city_name=city.name if city else "the city",
        problem_type=problem_type.value,
        severity=severity.value,
        road_name=road_name,
        confidence=confidence,
    )

    problem = Problem(
        city_id=city_id,
        ward_id=ward_id,
        location_id=location.id,
        source_detection_id=source_detection_id,
        problem_type=problem_type,
        severity=severity,
        # Starts VERIFIED, not DETECTED: reaching this function already
        # means a human reviewed the AI's suggestion (or entered it
        # manually themselves) and explicitly submitted it as a report -
        # that IS the verification step. DETECTED is reserved for a
        # possible future path where a problem is created without human
        # review (e.g. bulk-imported data); no such path exists yet, so
        # every report created today starts one step further along.
        status=ProblemStatus.VERIFIED,
        description=summary,
        recurrence_count=1,
        is_demo=False,
    )
    db.add(problem)
    db.flush()

    recompute_and_store_risk(db, problem)
    return problem


def verify_detection(db: Session, detection: Detection, payload: DetectionVerifyRequest) -> Problem | None:
    if payload.action == "reject":
        detection.status = DetectionStatus.REJECTED
        detection.reviewed_at = datetime.utcnow()
        return None

    if payload.action != "confirm":
        raise ValueError("action must be 'confirm' or 'reject'")

    final_severity = Severity(payload.final_severity) if payload.final_severity else detection.severity_suggested
    detection.status = DetectionStatus.CONFIRMED
    detection.reviewed_severity = final_severity
    detection.reviewed_at = datetime.utcnow()

    return place_or_update_problem(
        db,
        city_id=payload.city_id,
        problem_type=detection.problem_type,
        severity=final_severity,
        latitude=payload.latitude,
        longitude=payload.longitude,
        ward_id=payload.ward_id,
        road_name=payload.road_name,
        road_importance=payload.road_importance,
        near_important_infrastructure=payload.near_important_infrastructure,
        infrastructure_note=payload.infrastructure_note,
        source_detection_id=detection.id,
        # A user-drawn region has no model confidence; passing None makes the
        # report summary say it was reported manually instead of "100% confident".
        confidence=None if detection.model_version == USER_MARKED_VERSION else detection.confidence,
    )