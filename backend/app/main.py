from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    batches,
    capture,
    contents,
    documents,
    exports,
    folders,
    jobs,
    processing,
    review,
    schedules,
    settings as settings_api,
    tags,
)
from app.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: ensure directories and database tables exist
    settings.ensure_directories()
    init_db()
    yield
    # Shutdown


app = FastAPI(
    title="Paperless API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Enable CORS for frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers under /api/v1
from fastapi import APIRouter
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(documents.router)
api_v1.include_router(contents.router)
api_v1.include_router(batches.router)
api_v1.include_router(processing.router)
api_v1.include_router(tags.router)
api_v1.include_router(folders.router)
api_v1.include_router(capture.router)
api_v1.include_router(review.router)
api_v1.include_router(schedules.router)
api_v1.include_router(settings_api.router)
api_v1.include_router(jobs.router)
api_v1.include_router(exports.router)

app.include_router(api_v1)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
