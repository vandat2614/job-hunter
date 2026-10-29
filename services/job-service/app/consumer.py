import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import Job, JobSource
from app.normalize import extract_skills, make_dedup_key, parse_salary
from app.outbox import add_created_event
from app.metrics import MESSAGES, PROCESS_SECONDS

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


MAX_RETRIES = 3
DLQ_TOPIC = "job.raw.dlq"
# Lỗi do dữ liệu: retry không giúp ích gì
NON_RETRYABLE = (ValueError, KeyError, TypeError)  # JSONDecodeError là con của ValueError


async def process(raw: bytes):
    msg = json.loads(raw)
    async with SessionLocal() as session:
        async with session.begin():
            return await upsert_job(session, msg)


async def send_to_dlq(dlq: AIOKafkaProducer, record, error: Exception):
    headers = [
        ("error", f"{type(error).__name__}: {error}".encode()[:500]),
        ("source_topic", record.topic.encode()),
        ("source_partition", str(record.partition).encode()),
        ("source_offset", str(record.offset).encode()),
    ]
    while True:  # không bỏ cuộc: chưa vào được DLQ thì chưa commit
        try:
            await dlq.send_and_wait(DLQ_TOPIC, value=record.value, key=record.key, headers=headers)
            return
        except Exception:
            log.exception("cannot send to DLQ, retrying")
            await asyncio.sleep(3)


async def handle(record, dlq: AIOKafkaProducer):
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with PROCESS_SECONDS.time():
                job_id, result = await process(record.value)
            MESSAGES.labels(result).inc()
            log.info("offset=%s %s job=%s", record.offset, result, job_id)
            return
        except NON_RETRYABLE as e:
            last_error = e
            break
        except Exception as e:
            last_error = e
            log.warning("offset=%s attempt %d/%d failed: %s", record.offset, attempt, MAX_RETRIES, e)
            await asyncio.sleep(2 ** attempt)
    log.error("offset=%s -> DLQ: %s", record.offset, last_error)
    MESSAGES.labels("dlq").inc()
    await send_to_dlq(dlq, record, last_error)


async def run_consumer():
    consumer = AIOKafkaConsumer(
        "job.raw",
        bootstrap_servers=settings.kafka_bootstrap,
        group_id="job-service",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    dlq = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap)

    for _ in range(30):  # chờ Kafka sẵn sàng
        try:
            await consumer.start()
            await dlq.start()
            break
        except Exception:
            await asyncio.sleep(2)
    else:
        log.error("cannot connect to kafka")
        return

    log.info("consumer started")
    try:
        async for record in consumer:
            await handle(record, dlq)
            await consumer.commit()
    finally:
        await consumer.stop()
        await dlq.stop()
