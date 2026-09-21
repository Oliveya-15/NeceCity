"""
Logging configuration.

Per project requirement, we log application lifecycle events, model
loading, inference errors, API errors, database problems and report
generation errors -- but never secrets, passwords or personal data.
"""
import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(environment: str = "development") -> None:
    level = logging.DEBUG if environment == "development" else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers when Uvicorn's --reload re-imports the app.
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)

    # Quiet down noisy third-party loggers while keeping our own verbose.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
