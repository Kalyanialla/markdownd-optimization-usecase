"""
FastAPI application initialization, middleware, error handling, and health endpoints.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is in sys.path so 'app.main' and 'backend.app...' work from any CWD
_workspace_root = str(Path(__file__).resolve().parents[2])
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)

from fastapi import FastAPI, Depends, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging import setup_logging, logger
from backend.app.core.exceptions import AppException
from backend.app.db.session import get_db, check_db_connectivity
from backend.app.api.v1.router import api_router

setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# Support standard /api/v1 prefix and reverse-proxy /markdown-optimizer/api/v1 prefix
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(api_router, prefix=f"/markdown-optimizer{settings.API_V1_PREFIX}")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_ORIGIN,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:9123",
        "http://127.0.0.1:9123",
        "http://localhost:9124",
        "http://127.0.0.1:9124",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.detail,
                "extra": exc.extra,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": request.url.path
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_messages = []
    for err in errors:
        loc = ".".join([str(l) for l in err.get("loc", []) if l != "body"])
        msg = err.get("msg", "Invalid value")
        error_messages.append(f"{loc}: {msg}" if loc else msg)
    combined_message = "; ".join(error_messages) or "Validation failed on request data."
    logger.warning(f"Validation error on {request.url.path}: {combined_message}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": combined_message,
                "extra": {"details": errors},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": request.url.path
            }
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail if isinstance(exc.detail, str) else "An HTTP error occurred.",
                "extra": {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": request.url.path
            }
        }
    )


@app.get("/health", tags=["System Health"])
@app.get("/markdown-optimizer/health", tags=["System Health"])
@app.get(f"{settings.API_V1_PREFIX}/health", tags=["System Health"])
@app.get(f"/markdown-optimizer{settings.API_V1_PREFIX}/health", tags=["System Health"])
@app.get(f"{settings.API_V1_PREFIX}/system/health", tags=["System Health"])
async def health_check():
    """
    Liveness probe: returns 200 if the FastAPI application process is up and running.
    """
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/ready", tags=["System Health"])
@app.get("/markdown-optimizer/ready", tags=["System Health"])
@app.get(f"{settings.API_V1_PREFIX}/ready", tags=["System Health"])
@app.get(f"/markdown-optimizer{settings.API_V1_PREFIX}/ready", tags=["System Health"])
@app.get(f"{settings.API_V1_PREFIX}/system/ready", tags=["System Health"])
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe: validates database connectivity.
    Returns 200 if DB accepts queries; 503 Service Unavailable if disconnected.
    """
    is_connected, msg = check_db_connectivity(db)
    timestamp = datetime.now(timezone.utc).isoformat()

    if not is_connected:
        logger.warning(f"Readiness check failed: {msg}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "error": msg,
                "timestamp": timestamp
            }
        )

    return {
        "status": "ready",
        "database": "connected",
        "timestamp": timestamp
    }
