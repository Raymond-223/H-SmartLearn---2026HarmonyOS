"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.api import learners, assessments, diagnosis, workflows, resources, admin, knowledge, benchmarks

logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    await init_db()
    yield
    logger.info("Shutting down")


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
_allowed_origins = ["*"] if settings.debug else [
    item.strip() for item in settings.cors_origins.split(",") if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for api_router in (learners.router, assessments.router, diagnosis.router, workflows.router,
                   resources.router, knowledge.router, benchmarks.router, admin.router):
    app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.app_version, "mode": "hybrid-agent-platform"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
