import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from app.api import router
from app.consumer import run_consumer
from app.outbox import run_publisher

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(run_consumer()), asyncio.create_task(run_publisher())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="job-service", lifespan=lifespan)
app.include_router(router)
app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health():
    return {"status": "ok"}
