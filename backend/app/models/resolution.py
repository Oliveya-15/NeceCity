from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Resolution(Base):
    """
    Tracks the resolution lifecycle of a Problem: when work started, when
    it finished, optional before/after evidence images and free-text notes.
    `resolution_time_hours` is derived (not stored) to avoid two sources of
    truth for the same fact.
    """
    __tablename__ = "resolutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), unique=True, index=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    before_image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id", ondelete="SET NULL"), nullable=True)
    after_image_id: Mapped[int | None] = mapped_column(ForeignKey("images.id", ondelete="SET NULL"), nullable=True)

    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    problem: Mapped["Problem"] = relationship(back_populates="resolution")

    @property
    def resolution_time_hours(self) -> float | None:
        if self.started_at and self.resolved_at:
            delta = self.resolved_at - self.started_at
            return round(delta.total_seconds() / 3600, 1)
        return None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Resolution problem={self.problem_id}>"
