import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import Job, JobSource
from app.normalize import extract_skills, make_dedup_key, parse_salary
from app.outbox import add_created_event

log = logging.getLogger("consumer")


async def upsert_job(session, msg: dict):
    p = msg["payload"]

    # 1. Đã thấy đúng (source, source_job_id) này rồi -> chỉ cập nhật last_seen
    src = await session.scalar(
        select(JobSource).where(
            JobSource.source == msg["source"],
            JobSource.source_job_id == msg["source_job_id"],
        )
    )
    if src:
        job = await session.get(Job, src.job_id)
        job.last_seen_at = func.now()
        return job.id, "seen_again"

    # 2. Cùng job nhưng từ nguồn khác -> gắn thêm source vào job cũ
    key = make_dedup_key(p["company"], p["title"], p.get("location"))
    job = await session.scalar(select(Job).where(Job.dedup_key == key))
    if job:
        job.last_seen_at = func.now()
        session.add(JobSource(job_id=job.id, source=msg["source"],
                              source_job_id=msg["source_job_id"], url=msg["url"]))
        return job.id, "new_source"

    # 3. Job mới hoàn toàn
    smin, smax, cur = parse_salary(p.get("salary_text"))
    job = Job(
        dedup_key=key,
        title=p["title"].strip(),
        company=p["company"].strip(),
        location=p.get("location"),
        salary_min=smin, salary_max=smax, salary_currency=cur,
        skills=extract_skills(p["title"], p.get("description")),
        description=p.get("description"),
    )
    session.add(job)
    await session.flush()
    session.add(JobSource(job_id=job.id, source=msg["source"],
                          source_job_id=msg["source_job_id"], url=msg["url"]))
    add_created_event(session, job)
    return job.id, "created"


async def run_consumer():
    consumer = AIOKafkaConsumer(
        "job.raw",
        bootstrap_servers=settings.kafka_bootstrap,
        group_id="job-service",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode()),
    )
    for _ in range(30):  # chờ Kafka sẵn sàng
        try:
            await consumer.start()
            break
        except Exception:
            await asyncio.sleep(2)
    else:
        log.error("cannot connect to kafka")
        return

    log.info("consumer started")
    try:
        async for record in consumer:
            try:
                async with SessionLocal() as session:
                    async with session.begin():
                        job_id, result = await upsert_job(session, record.value)
                log.info("offset=%s %s job=%s", record.offset, result, job_id)
            except Exception:
                log.exception("failed offset=%s", record.offset)
            await consumer.commit()
    finally:
        await consumer.stop()
