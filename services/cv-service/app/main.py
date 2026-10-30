import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.outbox import run_publisher

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_publisher())
    yield
    task.cancel()


app = FastAPI(
    title="cv-service",
    lifespan=lifespan,
    docs_url="/docs/cvs",
    openapi_url="/docs/cvs/openapi.json",
    redoc_url=None,
)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
