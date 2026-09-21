"""
Shared enumerations.

Kept in one place so the ML class list, the database, the risk engine and
the frontend badges all agree on the same vocabulary. Adding a new problem
type or status is a one-line change here rather than a search-and-replace
across the codebase (see project rule: city/class configuration must be
data-driven, not scattered through source files).
"""
import enum


class ProblemType(str, enum.Enum):
    POTHOLE = "pothole"
    ROAD_DAMAGE = "road_damage"
    GARBAGE = "garbage"
    WATERLOGGING = "waterlogging"
    DAMAGED_ROAD_SIGN = "damaged_road_sign"
    OPEN_DRAIN = "open_drain"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProblemStatus(str, enum.Enum):
    DETECTED = "detected"
    VERIFIED = "verified"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class DetectionStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class RoadImportance(str, enum.Enum):
    LOCAL = "local"        # residential / minor street
    ARTERIAL = "arterial"  # main city road
    HIGHWAY = "highway"    # national/state highway


class ImageSource(str, enum.Enum):
    UPLOAD = "upload"   # uploaded by a user through Inspect & Analyze
    DEMO = "demo"        # bundled demonstration/seed data


# Ordered lifecycle used by the Action Center to validate status transitions.
PROBLEM_STATUS_ORDER = [
    ProblemStatus.DETECTED,
    ProblemStatus.VERIFIED,
    ProblemStatus.IN_PROGRESS,
    ProblemStatus.RESOLVED,
]
