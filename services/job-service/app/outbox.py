import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import Outbox
from app.metrics import EVENTS_PUBLISHED

log = logging.getLogger("outbox")


def add_created_event(session, job, url):
    """Write the event to the outbox, in the same transaction as the job."""
    oid = uuid.uuid4()
    session.add(Outbox(
        id=oid,
        topic="job.created",
        key=str(job.id),
        payload={
            "event_id": str(oid),
            "job_id": str(job.id),
            "url": url,
            "description": (job.description or "")[:4000],
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "salary_currency": job.salary_currency,
            "skills": job.skills,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    ))


async def run_publisher():
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap,
        key_serializer=lambda k: k.encode(),
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    for _ in range(30):
        try:
            await producer.start()
            break
        except Exception:
            await asyncio.sleep(2)
    else:
        log.error("publisher cannot connect to kafka")
        return

    log.info("publisher started")
    try:
        while True:
            rows = []
            try:
                async with SessionLocal() as session:
                    async with session.begin():
                        rows = (await session.scalars(
                            select(Outbox)
                            .where(Outbox.published_at.is_(None))
                            .order_by(Outbox.created_at)
                            .limit(100)
                            .with_for_update(skip_locked=True)
                        )).all()
                        for r in rows:
                            await producer.send_and_wait(r.topic, value=r.payload, key=r.key)
                            r.published_at = func.now()
                            log.info("published %s -> %s", r.id, r.topic)
                            EVENTS_PUBLISHED.labels(r.topic).inc()
            except Exception:
                log.exception("publisher error")
                await asyncio.sleep(3)
            if not rows:
                await asyncio.sleep(1)
    finally:
        await producer.stop()
