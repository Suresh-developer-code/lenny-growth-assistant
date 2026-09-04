import logging
import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, health, sessions
from app.config import get_settings

settings = get_settings()

logging.basicConfig(level=settings.log_level, format="%(message)s")
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Grounded assistant over Lenny's Podcast transcripts.",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://frontend-4wzk25sro-suresh-developer-code.vercel.app", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    with structlog.contextvars.bound_contextvars(request_id=request_id, path=request.url.path):
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info("request.completed", status_code=response.status_code, duration_ms=duration_ms)
        response.headers["X-Request-ID"] = request_id
        return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "type": "validation_error",
            "title": "Request validation failed",
            "detail": exc.errors(),
            "status": 422,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "type": "internal_error",
            "title": "Something went wrong",
            "detail": "An unexpected error occurred. Check server logs (request_id header) for detail.",
            "status": 500,
        },
    )


app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(health.router)


@app.get("/")
async def root():
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}
