from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.detection import Detection
from app.models.enums import ProblemType, Severity
from app.models.image import Image
from app.schemas.detection import (
    BoundingBox, DetectionOut, DetectionVerifyRequest, DetectionVerifyResponse, UserRegionRequest,
)
from app.services.detection_service import create_user_marked_detection, verify_detection

router = APIRouter(prefix="/detections", tags=["detections"])


@router.post("/user-region", response_model=DetectionOut)
def add_user_region(payload: UserRegionRequest, db: Session = Depends(get_db)):
    """
    Lets the reporter mark a problem area on the uploaded photo themselves
    when the model missed it. Creates a pending Detection (source "user")
    that then goes through the normal verify/confirm flow, and is also saved
    as a labelled example the model can later be retrained on
    (see ml/training/export_feedback.py).
    """
    image = db.get(Image, payload.image_id)
    if image is None:
        raise HTTPException(status_code=404, detail=f"Image {payload.image_id} not found.")
    try:
        problem_type = ProblemType(payload.problem_type)
        severity = Severity(payload.severity)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    det = create_user_marked_detection(
        db, image=image, problem_type=problem_type, severity=severity,
        x_min=payload.x_min, y_min=payload.y_min, x_max=payload.x_max, y_max=payload.y_max,
    )
    db.commit()
    return DetectionOut(
        id=det.id,
        problem_type=det.problem_type.value,
        confidence=det.confidence,
        severity_suggested=det.severity_suggested.value,
        bbox=BoundingBox(x_min=det.bbox_x_min, y_min=det.bbox_y_min, x_max=det.bbox_x_max, y_max=det.bbox_y_max),
        source="user",
        low_confidence=False,
    )


@router.post("/{detection_id}/verify", response_model=DetectionVerifyResponse)
def verify(detection_id: int, payload: DetectionVerifyRequest, db: Session = Depends(get_db)):
    detection = db.get(Detection, detection_id)
    if detection is None:
        raise HTTPException(status_code=404, detail=f"Detection {detection_id} not found.")
    if detection.status.value != "pending_review":
        raise HTTPException(status_code=409, detail=f"Detection {detection_id} has already been reviewed.")

    try:
        problem = verify_detection(db, detection, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    db.commit()

    return DetectionVerifyResponse(
        detection_id=detection.id,
        status=detection.status.value,
        problem_id=problem.id if problem else None,
    )
