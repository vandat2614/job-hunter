import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app import models  # noqa: F401
from app.api import router
from app.consumer import run_consumer
from app.db import Base, engine
from app.outbox import run_publisher

logging.basicConfig(level=logging.INFO)

# Tạm thời, sẽ chuyển sang Alembic: create_all không sửa bảng đã tồn tại
SEARCH_COL = (
    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS search_vector tsvector "
    "GENERATED ALWAYS AS (to_tsvector('simple', coalesce(title,'') || ' ' || "
    "coalesce(company,'') || ' ' || coalesce(description,''))) STORED"
)
INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_jobs_search ON jobs USING GIN (search_vector)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_skills ON jobs USING GIN (skills)",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(SEARCH_COL))
        for stmt in INDEXES:
            await conn.execute(text(stmt))
    tasks = [asyncio.create_task(run_consumer()), asyncio.create_task(run_publisher())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="job-service", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
