"""
Risk engine configuration.

Every weight/threshold the risk engine uses lives here, sourced from
`Settings` (which reads environment variables) with sane defaults - this is
the single place to tune the scoring formula instead of magic numbers
scattered across the codebase.

`WEIGHTS_VERSION` is stored on every computed RiskScore row so that if the
weights are ever changed, historical scores can still be understood in the
context of the formula that produced them.
"""
from dataclasses import dataclass

from app.core.config import get_settings
from app.models.enums import RoadImportance, Severity

WEIGHTS_VERSION = "v1"

# Distance (metres) within which nearby problems count toward the
# "density" / "multiple nearby problems" signal.
DENSITY_RADIUS_METERS = 150

# A location is considered "recurring" once this many confirmed detections
# have landed on/near it.
RECURRENCE_SATURATION_COUNT = 5

# Maps ordinal severity to a 0-1 raw score used as a risk factor input.
SEVERITY_RAW_SCORE = {
    Severity.LOW: 0.25,
    Severity.MEDIUM: 0.50,
    Severity.HIGH: 0.75,
    Severity.CRITICAL: 1.00,
}

# Maps road importance to a 0-1 raw score.
ROAD_IMPORTANCE_RAW_SCORE = {
    RoadImportance.LOCAL: 0.30,
    RoadImportance.ARTERIAL: 0.70,
    RoadImportance.HIGHWAY: 1.00,
}

# A location near critical infrastructure (hospital, school, major
# junction, ...) gets this raw score; otherwise 0.
INFRASTRUCTURE_PROXIMITY_RAW_SCORE = 1.0
INFRASTRUCTURE_NO_PROXIMITY_RAW_SCORE = 0.0

# How many nearby problems saturate the density factor at raw score 1.0.
DENSITY_SATURATION_COUNT = 6


@dataclass(frozen=True)
class RiskWeights:
    severity: float
    recurrence: float
    density: float
    road_importance: float
    infrastructure: float

    def as_dict(self) -> dict[str, float]:
        return {
            "severity": self.severity,
            "recurrence": self.recurrence,
            "density": self.density,
            "road_importance": self.road_importance,
            "infrastructure": self.infrastructure,
        }


def get_risk_weights() -> RiskWeights:
    s = get_settings()
    weights = RiskWeights(
        severity=s.RISK_WEIGHT_SEVERITY,
        recurrence=s.RISK_WEIGHT_RECURRENCE,
        density=s.RISK_WEIGHT_DENSITY,
        road_importance=s.RISK_WEIGHT_ROAD_IMPORTANCE,
        infrastructure=s.RISK_WEIGHT_INFRASTRUCTURE,
    )
    total = sum(weights.as_dict().values())
    if not (0.99 <= total <= 1.01):
        raise ValueError(
            f"Risk engine weights must sum to 1.0, got {total:.3f}. "
            "Check RISK_WEIGHT_* environment variables."
        )
    return weights
