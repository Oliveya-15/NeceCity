"""
Central configuration for the NeceCity backend.

Every environment-dependent value (database credentials, model path, upload
directory, CORS origins, risk weights, ...) is read from environment
variables through this single `Settings` object instead of being hard-coded
or scattered across the codebase (see project rule: "no magic numbers / no
hard-coded secrets scattered through the code").

In local development, values are loaded from a `.env` file (see
`.env.example` at the repository root for the full list of variables).
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- General ----
    APP_NAME: str = "NeceCity"
    ENVIRONMENT: str = "development"  # development | production | test
    API_V1_PREFIX: str = "/api/v1"

    # ---- Database ----
    # Full SQLAlchemy URL takes precedence when provided. Otherwise it is
    # assembled from the individual POSTGRES_* variables, which is more
    # convenient for Docker Compose service wiring.
    DATABASE_URL: str | None = None
    POSTGRES_USER: str = "nececity"
    POSTGRES_PASSWORD: str = "nececity"
    POSTGRES_DB: str = "nececity"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # ---- Uploads ----
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 8
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png", "image/webp"]

    # ---- ML model ----
    # Absolute or relative path to the trained NeceCity YOLO weights file
    # (see ml/weights/README.md). If the file does not exist, the
    # application must still start and run in "model not configured" mode
    # (see app/ml/inference.py).
    MODEL_PATH: str = "../ml/weights/nececity_yolo.pt"
    MODEL_CONFIDENCE_THRESHOLD: float = 0.35
    MODEL_IOU_THRESHOLD: float = 0.45
    MODEL_IMAGE_SIZE: int = 640
    # Detections between MODEL_MIN_CONFIDENCE and MODEL_CONFIDENCE_THRESHOLD are
    # still returned to the reviewer, flagged "low confidence - please verify".
    # A model trained on a small dataset is often unsure on photos it has never
    # seen; hiding every uncertain box makes it look like it found nothing, so
    # we surface them and let the human confirm or reject (nothing is stored as
    # a Problem until the user confirms).
    MODEL_MIN_CONFIDENCE: float = 0.10
    MODEL_MAX_DETECTIONS: int = 10
    # Test-time augmentation (multi-scale + flip). Slower (~2-3x) but noticeably
    # more robust on unseen photos.
    MODEL_USE_TTA: bool = True

    # ---- Area lookup for the AI Recommendations chat ----
    # When a user asks about a place ("Sevoke Road", "Kestopur") that is not a
    # stored ward/road name, the backend geocodes it (OpenStreetMap Nominatim by
    # default - free, no key) and counts reported problems within a radius.
    GEOCODER_ENABLED: bool = True
    GEOCODER_URL: str = "https://nominatim.openstreetmap.org/search"
    # Nominatim's usage policy requires an identifying User-Agent.
    GEOCODER_USER_AGENT: str = "NeceCity/0.1 (civic infrastructure monitoring project)"
    GEOCODER_TIMEOUT_SECONDS: float = 6.0
    # A geocoded place further than this from the selected city's centre is
    # rejected (prevents "Kestopur" resolving to an unrelated place elsewhere).
    AREA_MAX_DISTANCE_FROM_CITY_KM: float = 45.0
    AREA_MIN_RADIUS_M: int = 800
    AREA_MAX_RADIUS_M: int = 4000
    AREA_MAX_PROBLEMS_LISTED: int = 6

    # ---- CORS ----
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ---- Risk engine weights (must sum to 1.0, validated at startup) ----
    RISK_WEIGHT_SEVERITY: float = 0.35
    RISK_WEIGHT_RECURRENCE: float = 0.20
    RISK_WEIGHT_DENSITY: float = 0.20
    RISK_WEIGHT_ROAD_IMPORTANCE: float = 0.15
    RISK_WEIGHT_INFRASTRUCTURE: float = 0.10

    # ---- AI Recommendations chat (optional - bring your own key) ----
    # Uses the OpenAI-compatible /chat/completions request shape, so any
    # provider implementing that interface works by changing the base URL
    # (OpenAI itself, Groq, or a local OpenAI-compatible proxy such as
    # Ollama's /v1 endpoint). If LLM_API_KEY is unset, the chat endpoint
    # falls back to a rule-based assistant grounded in the same real city
    # data - see app/services/chat_service.py. This mirrors the same
    # graceful-degradation pattern used for the YOLO model.
    LLM_API_KEY: str = ""
    LLM_API_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_REQUEST_TIMEOUT_SECONDS: float = 45.0
    # Output budget for chat answers. Reasoning models (e.g. gpt-oss on Groq) spend
    # part of this budget "thinking" before they write the answer, so a small value
    # produces cut-off or empty replies. The caller also retries once with double
    # the budget if the provider reports the reply was cut off.
    LLM_MAX_TOKENS: int = 2500
    # Optional: "low" | "medium" | "high". Sent as `reasoning_effort` ONLY when set.
    # Recommended "low" for Groq's openai/gpt-oss-* models (faster, leaves more of
    # the budget for the answer). Leave blank for providers that don't support it.
    LLM_REASONING_EFFORT: str = ""

    # ---- Pagination ----
    DEFAULT_PAGE_SIZE: int = 25
    MAX_PAGE_SIZE: int = 200

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def resolved_model_path(self) -> Path:
        path = Path(self.MODEL_PATH)
        if not path.is_absolute():
            # Resolve relative to the backend/app directory so the same
            # relative path works both when run locally and inside Docker.
            path = (Path(__file__).resolve().parent.parent.parent / path).resolve()
        return path

    @property
    def resolved_upload_dir(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        if not path.is_absolute():
            path = (Path(__file__).resolve().parent.parent.parent / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Settings are cached so the .env file is parsed only once per process."""
    return Settings()
