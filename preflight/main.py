"""FastAPI entrypoint."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from preflight import __version__
from preflight.logging import configure_logging, get_logger
from preflight.routes import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger = get_logger(__name__)
    logger.info("preflight.startup", version=__version__)
    yield
    logger.info("preflight.shutdown")


app = FastAPI(
    title="Pre-Flight",
    version=__version__,
    description="Pre-launch quality gate for AI-generated research surveys",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
