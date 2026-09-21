from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import DetectionStatus, ProblemType, Severity


class Detection(Base):
    """
    A single raw prediction produced by the NeceCity YOLO model for one
    image (an image may contain multiple detections/bounding boxes).

    A Detection is *model output*: `confidence` is the model's own
    confidence for that bounding box. It is intentionally kept separate
    from model-level evaluation metrics (precision/recall/mAP), which live
    in `ml/evaluation` results, not on this row - the project explicitly
    requires keeping model evaluation info separate from individual
    prediction confidence.

    Detections start as `pending_review`. A human reviewer can
    confirm/reject/edit the severity in Inspect & Analyze; only a confirmed
    detection is promoted into a `Problem` record.
    """
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id", ondelete="CASCADE"), index=True)

    problem_type: Mapped[ProblemType] = mapped_column(Enum(ProblemType, name="problem_type"), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Bounding box in normalized [0, 1] coordinates (x_min, y_min, x_max, y_max)
    # relative to image width/height - resolution independent, so the
    # frontend can redraw boxes on any rendered image size.
    bbox_x_min: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y_min: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_x_max: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y_max: Mapped[float] = mapped_column(Float, nullable=False)

    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    severity_suggested: Mapped[Severity] = mapped_column(Enum(Severity, name="severity_suggested"), nullable=False)

    status: Mapped[DetectionStatus] = mapped_column(
        Enum(DetectionStatus, name="detection_status"), default=DetectionStatus.PENDING_REVIEW
    )
    reviewed_severity: Mapped[Severity | None] = mapped_column(Enum(Severity, name="severity_reviewed"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    image: Mapped["Image"] = relationship(back_populates="detections")
    problem: Mapped["Problem | None"] = relationship(back_populates="source_detection", uselist=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Detection {self.problem_type} conf={self.confidence:.2f}>"
