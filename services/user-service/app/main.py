import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth_router, sub_router
from app.outbox import run_publisher

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_publisher())
    yield
    task.cancel()


app = FastAPI(title="user-service", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(sub_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
