from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RiskScore(Base):
    """
    The explainable risk/priority score for a Problem, normalized to 0-100.

    `components` stores the *weighted contribution* of each factor
    (severity, recurrence, density, road importance, infrastructure
    proximity) as JSON, e.g.:

        {
          "severity":        {"raw": 0.75, "weight": 0.35, "contribution": 26.25},
          "recurrence":      {"raw": 0.40, "weight": 0.20, "contribution": 8.0},
          "density":         {"raw": 0.60, "weight": 0.20, "contribution": 12.0},
          "road_importance": {"raw": 1.00, "weight": 0.15, "contribution": 15.0},
          "infrastructure":  {"raw": 0.00, "weight": 0.10, "contribution": 0.0}
        }

    This is the one place in the schema where JSON is used deliberately
    (per project rule: JSON only where it genuinely makes sense) because
    the exact factor breakdown is inherently a flexible, self-describing
    structure that the UI renders directly as "why is this high priority".

    `reasons` is the plain-English explanation list derived from those
    same components at computation time (see app/risk/engine.py
    `_reasons`) - stored rather than recomputed on every read, since
    recomputing it would require re-running the density spatial query.
    """
    __tablename__ = "risk_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), unique=True, index=True)

    score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100
    components: Mapped[dict] = mapped_column(JSON, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    weights_version: Mapped[str] = mapped_column(String(20), nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(300), nullable=False)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    problem: Mapped["Problem"] = relationship(back_populates="risk_score")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RiskScore problem={self.problem_id} score={self.score:.1f}>"
