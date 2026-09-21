from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.detection import Detection
from app.schemas.detection import DetectionVerifyRequest, DetectionVerifyResponse
from app.services.detection_service import verify_detection

router = APIRouter(prefix="/detections", tags=["detections"])


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
