"""
Loads the detection class list from `ml/data/classes.yaml` - the single
source of truth shared between the training pipeline and this backend, so
class index 0 always means the same thing in both places.

Falls back to the `ProblemType` enum (in declared order) if the YAML file
is not reachable, e.g. in a minimal Docker image that ships the backend
without the `ml/` folder. Both lists are kept in sync by convention; a
mismatch would only matter if someone edits one without the other, which
the accompanying test (`tests/test_ml_inference.py`) guards against.
"""
from pathlib import Path

import yaml

from app.core.config import get_settings
from app.models.enums import ProblemType

_FALLBACK_ORDER = [
    ProblemType.POTHOLE,
    ProblemType.ROAD_DAMAGE,
    ProblemType.GARBAGE,
    ProblemType.WATERLOGGING,
    ProblemType.DAMAGED_ROAD_SIGN,
    ProblemType.OPEN_DRAIN,
]


def _classes_yaml_path() -> Path:
    settings = get_settings()
    # ml/ is a sibling of backend/, mirroring MODEL_PATH's resolution.
    return (Path(__file__).resolve().parent.parent.parent.parent / "ml" / "data" / "classes.yaml").resolve()


def load_class_index() -> dict[int, ProblemType]:
    path = _classes_yaml_path()
    if not path.exists():
        return {i: pt for i, pt in enumerate(_FALLBACK_ORDER)}

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    names = data.get("names", {})
    return {int(idx): ProblemType(name) for idx, name in names.items()}
