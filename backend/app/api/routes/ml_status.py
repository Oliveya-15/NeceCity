from fastapi import APIRouter

from app.ml.inference import get_detector

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/status")
def ml_status():
    detector = get_detector()
    return {
        "model_available": detector.is_ready,
        "model_version": detector.model_version if detector.is_ready else None,
        "unavailable_reason": detector.unavailable_reason,
        "training_data_warning": detector.training_data_warning,
    }
