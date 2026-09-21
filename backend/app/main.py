"""
NeceCity backend entrypoint.

Wires together configuration, logging, CORS, static file serving for
uploaded images, and every route module. Route modules contain no
business logic themselves (see app/services, app/analytics, app/risk,
app/ml) - this keeps main.py and the route files small and focused.
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import analyze, analytics, chat, cities, detections, map as map_routes, ml_status, problems, recommendations, reports, risk
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.ENVIRONMENT)
logger = get_logger(__name__)

app = FastAPI(
    title="NeceCity API",
    description="AI-powered urban infrastructure monitoring & decision-support system.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error while processing %s %s", request.method, request.url.path)
        raise
    duration_ms = (time.time() - start) * 1000
    logger.info("%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak stack traces to the client, even in an unexpected failure.
    if settings.ENVIRONMENT == "development":
        logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


app.include_router(cities.router, prefix=settings.API_V1_PREFIX)
app.include_router(problems.router, prefix=settings.API_V1_PREFIX)
app.include_router(analyze.router, prefix=settings.API_V1_PREFIX)
app.include_router(detections.router, prefix=settings.API_V1_PREFIX)
app.include_router(map_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)
app.include_router(risk.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports.router, prefix=settings.API_V1_PREFIX)
app.include_router(recommendations.router, prefix=settings.API_V1_PREFIX)
app.include_router(chat.router, prefix=settings.API_V1_PREFIX)
app.include_router(ml_status.router, prefix=settings.API_V1_PREFIX)

# Serve uploaded/demo images directly (development convenience; a
# production deployment would typically front this with nginx/object
# storage, documented in docs/setup.md).
app.mount("/uploads", StaticFiles(directory=str(settings.resolved_upload_dir)), name="uploads")


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


@app.on_event("startup")
def on_startup():
    logger.info("%s backend starting up (environment=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    from app.ml.inference import get_detector
    detector = get_detector()
    if detector.is_ready:
        logger.info("ML model ready: %s", detector.model_version)
    else:
        logger.warning("ML model not ready: %s", detector.unavailable_reason)
