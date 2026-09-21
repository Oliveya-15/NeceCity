"""
Preprocessing and validation for images submitted to Inspect & Analyze.

Kept deliberately simple and dependency-light (Pillow only) so it also
works when the heavier OpenCV/YOLO stack is not installed - validation
should never depend on the ML model being available.
"""
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

MIN_DIMENSION_PX = 64
MAX_DIMENSION_PX = 8000


class ImageValidationError(ValueError):
    """Raised when an uploaded file fails validation (bad type/size/corrupt)."""


@dataclass
class ValidatedImage:
    width: int
    height: int
    content_type: str


def validate_image_upload(raw_bytes: bytes, declared_content_type: str) -> ValidatedImage:
    settings = get_settings()

    if declared_content_type not in settings.ALLOWED_IMAGE_TYPES:
        raise ImageValidationError(
            f"Unsupported file type '{declared_content_type}'. "
            f"Allowed types: {', '.join(settings.ALLOWED_IMAGE_TYPES)}."
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise ImageValidationError(f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB upload limit.")

    try:
        with Image.open(BytesIO(raw_bytes)) as img:
            img.verify()  # cheap structural check
        # Re-open after verify() (verify() leaves the file unusable for further reads).
        with Image.open(BytesIO(raw_bytes)) as img:
            width, height = img.size
            fmt = (img.format or "").upper()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageValidationError("The uploaded file is not a valid or is a corrupted image.") from exc

    if width < MIN_DIMENSION_PX or height < MIN_DIMENSION_PX:
        raise ImageValidationError(f"Image is too small (minimum {MIN_DIMENSION_PX}x{MIN_DIMENSION_PX}px).")
    if width > MAX_DIMENSION_PX or height > MAX_DIMENSION_PX:
        raise ImageValidationError(f"Image is too large (maximum {MAX_DIMENSION_PX}x{MAX_DIMENSION_PX}px).")

    return ValidatedImage(width=width, height=height, content_type=declared_content_type)
