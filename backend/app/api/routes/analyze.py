from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.ml.preprocessing import ImageValidationError, validate_image_upload
from app.schemas.detection import AnalyzeImageResponse, BoundingBox, DetectionOut
from app.services.detection_service import run_inference_and_store, save_uploaded_image

router = APIRouter(prefix="/analyze", tags=["analyze"])
logger = get_logger(__name__)


@router.post("/image", response_model=AnalyzeImageResponse)
async def analyze_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw_bytes = await file.read()

    try:
        validated = validate_image_upload(raw_bytes, file.content_type or "")
    except ImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    image = save_uploaded_image(db, raw_bytes, validated, file.filename)

    try:
        inference, stored_detections = run_inference_and_store(db, image)
    except Exception as exc:  # noqa: BLE001 - inference failures must not crash the API
        logger.error("Inference failed for image %s: %s", image.id, exc)
        db.commit()  # still keep the uploaded image record
        raise HTTPException(status_code=500, detail="Inference failed. The image was saved; please try again.")

    db.commit()

    low_conf_cutoff = get_settings().MODEL_CONFIDENCE_THRESHOLD

    return AnalyzeImageResponse(
        image_id=image.id,
        model_available=inference.model_available,
        model_version=inference.model_version,
        message=inference.message,
        training_data_warning=inference.training_data_warning,
        image_width=inference.image_width,
        image_height=inference.image_height,
        detections=[
            DetectionOut(
                id=stored.id,
                problem_type=stored.problem_type.value,
                confidence=stored.confidence,
                low_confidence=stored.confidence < low_conf_cutoff,
                severity_suggested=stored.severity_suggested.value,
                bbox=BoundingBox(
                    x_min=stored.bbox_x_min, y_min=stored.bbox_y_min,
                    x_max=stored.bbox_x_max, y_max=stored.bbox_y_max,
                ),
            )
            for stored in stored_detections
        ],
    )
