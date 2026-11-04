import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from .config import get_settings
from .db import SessionLocal
from .models import BackgroundJob
from .api import (
    alerts,
    analytics,
    auth,
    followups,
    handovers,
    imports,
    media,
    organization,
    platform,
    reports,
    tasks,
    workforce,
    workspace,
)

settings = get_settings()
logger = logging.getLogger("shiftproof")
app = FastAPI(
    title="ShiftProof API",
    version="1.0.0",
    description="Organization-isolated operational handovers. All timestamps are UTC; business actions require server-side authorization.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Account-ID", "X-User-Activity", "Idempotency-Key"],
)


@app.middleware("http")
async def request_boundary(request: Request, call_next):
    request_id = str(uuid4())
    started = time.monotonic()
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in settings.allowed_origins:
        return JSONResponse({"detail": "This request origin is not allowed."}, status_code=403)
    try:
        response = await call_next(request)
    except Exception:
        logger.error("request_failed id=%s method=%s path=%s", request_id, request.method, request.url.path)
        return JSONResponse(
            {"detail": "We couldn’t complete the request. Please try again.", "request_id": request_id},
            status_code=500,
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    logger.info(
        "request id=%s method=%s path=%s status=%s ms=%d",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_request, error):
    # Never reflect passwords, PINs, tokens, recordings or submitted report text in errors.
    return JSONResponse(
        {
            "detail": [
                {"loc": item["loc"], "msg": item["msg"], "type": item["type"]} for item in error.errors()
            ]
        },
        status_code=422,
    )


@app.exception_handler(IntegrityError)
async def integrity_error(_request, _error):
    return JSONResponse(
        {"detail": "These details conflict with an existing record. Refresh and check for duplicates."},
        status_code=409,
    )


@app.exception_handler(StaleDataError)
async def concurrent_error(_request, _error):
    return JSONResponse(
        {"detail": "This record changed while you were working. Refresh before trying again."},
        status_code=409,
    )


@app.get("/api/v1/health", tags=["Platform"])
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            failed = db.scalar(
                select(func.count()).select_from(BackgroundJob).where(BackgroundJob.status == "failed")
            )
        return {
            "status": "ok",
            "database": "connected",
            "failed_jobs": failed,
            "providers": {
                "gnani_prisma": bool(settings.gnani_api_key),
                "gnani_timbre": bool(settings.gnani_api_key),
                "gemini": bool(settings.gemini_api_key),
            },
        }
    except SQLAlchemyError:
        return JSONResponse({"status": "unavailable", "database": "unavailable"}, status_code=503)


for router in [
    auth.router,
    organization.router,
    workforce.router,
    tasks.router,
    reports.router,
    alerts.router,
    handovers.router,
    media.router,
    imports.router,
    platform.router,
    analytics.router,
    followups.router,
    workspace.router,
]:
    app.include_router(router, prefix="/api/v1")
