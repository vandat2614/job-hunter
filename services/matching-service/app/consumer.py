import asyncio
import json
import logging
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.db import SessionLocal
from app.matcher import is_match
from app.models import Match, Subscription
from app.outbox import add_event

log = logging.getLogger("consumer")

MAX_RETRIES = 3
DLQ_TOPIC = "matching.dlq"
# Data errors: retrying will not help
NON_RETRYABLE = (ValueError, KeyError, TypeError)


async def apply_subscription_event(session, msg: dict):
    sub_id = uuid.UUID(msg["subscription_id"])
    if msg["type"] == "subscription.upserted":
        values = dict(
            id=sub_id,
            user_id=uuid.UUID(msg["user_id"]),
            skills=msg["skills"],
            location=msg.get("location"),
            min_salary=msg.get("min_salary"),
            currency=msg.get("currency"),
            telegram_chat_id=msg.get("telegram_chat_id"),
            active=msg["active"],
        )
        stmt = pg_insert(Subscription).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Subscription.id],
            set_={k: v for k, v in values.items() if k != "id"},
        )
        await session.execute(stmt)
        return "subscription_upserted"
    if msg["type"] == "subscription.deleted":
        await session.execute(delete(Subscription).where(Subscription.id == sub_id))
        return "subscription_deleted"
    raise ValueError(f"unknown event type: {msg['type']}")


async def match_job(session, job: dict):
    job_id = uuid.UUID(job["job_id"])
    subs = (await session.scalars(select(Subscription).where(Subscription.active.is_(True)))).all()
    matched = 0
    for sub in subs:
        if not is_match(job, sub):
            continue
        # Insert fails silently if this pair was already matched (duplicate event)
        res = await session.execute(
            pg_insert(Match)
            .values(job_id=job_id, subscription_id=sub.id)
            .on_conflict_do_nothing()
            .returning(Match.job_id)
        )
        if res.scalar_one_or_none() is None:
            continue
        add_event(session, "job.matched", f"{job_id}:{sub.id}", {
            "job_id": str(job_id),
            "subscription_id": str(sub.id),
            "user_id": str(sub.user_id),
            "telegram_chat_id": sub.telegram_chat_id,
            "title": job["title"],
            "company": job["company"],
            "location": job.get("location"),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "salary_currency": job.get("salary_currency"),
            "url": job.get("url"),
        })
        matched += 1
    return f"job_matched={matched}/{len(subs)}"


async def process(record):
    msg = json.loads(record.value)
    async with SessionLocal() as session:
        async with session.begin():
            if record.topic == "subscription.events":
                return await apply_subscription_event(session, msg)
            if record.topic == "job.created":
                return await match_job(session, msg)
            raise ValueError(f"unexpected topic: {record.topic}")


async def send_to_dlq(dlq: AIOKafkaProducer, record, error: Exception):
    headers = [
        ("error", f"{type(error).__name__}: {error}".encode()[:500]),
        ("source_topic", record.topic.encode()),
        ("source_partition", str(record.partition).encode()),
        ("source_offset", str(record.offset).encode()),
    ]
    while True:  # never give up: do not commit the offset until the message is in the DLQ
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
            result = await process(record)
            log.info("%s offset=%s %s", record.topic, record.offset, result)
            return
        except NON_RETRYABLE as e:
            last_error = e
            break
        except Exception as e:
            last_error = e
            log.warning("offset=%s attempt %d/%d failed: %s", record.offset, attempt, MAX_RETRIES, e)
            await asyncio.sleep(2 ** attempt)
    log.error("%s offset=%s -> DLQ: %s", record.topic, record.offset, last_error)
    await send_to_dlq(dlq, record, last_error)


async def run_consumer():
    consumer = AIOKafkaConsumer(
        "subscription.events",
        "job.created",
        bootstrap_servers=settings.kafka_bootstrap,
        group_id="matching-service",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    dlq = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap)

    for _ in range(30):  # wait for Kafka to be ready
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
