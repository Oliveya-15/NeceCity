from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ProblemStatus, ProblemType, Severity


class Problem(Base):
    """
    A confirmed infrastructure problem: the central entity NeceCity
    monitors. Created either by confirming a Detection (Inspect & Analyze)
    or by the demo/seed data generator (`is_demo=True`).

    `recurrence_count` is incremented by the detection service whenever a
    new confirmed detection lands close to an existing open problem of the
    same type, rather than creating a duplicate row - this is what feeds
    the risk engine's "recurring issue" signal.
    """
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), index=True)
    ward_id: Mapped[int | None] = mapped_column(ForeignKey("wards.id", ondelete="SET NULL"), nullable=True, index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    source_detection_id: Mapped[int | None] = mapped_column(
        ForeignKey("detections.id", ondelete="SET NULL"), nullable=True, unique=True
    )

    problem_type: Mapped[ProblemType] = mapped_column(Enum(ProblemType, name="problem_type_main"), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="severity_main"), nullable=False)
    status: Mapped[ProblemStatus] = mapped_column(
        Enum(ProblemStatus, name="problem_status"), default=ProblemStatus.DETECTED, index=True
    )

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=1)

    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    city: Mapped["City"] = relationship(back_populates="problems")
    ward: Mapped["Ward | None"] = relationship(back_populates="problems")
    location: Mapped["Location"] = relationship(back_populates="problems")
    source_detection: Mapped["Detection | None"] = relationship(back_populates="problem")
    risk_score: Mapped["RiskScore | None"] = relationship(back_populates="problem", cascade="all, delete-orphan", uselist=False)
    resolution: Mapped["Resolution | None"] = relationship(back_populates="problem", cascade="all, delete-orphan", uselist=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Problem #{self.id} {self.problem_type}/{self.severity}/{self.status}>"
