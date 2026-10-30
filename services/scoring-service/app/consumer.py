import asyncio
import json
import logging
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.db import SessionLocal
from app.llm import OllamaClient
from app.models import CVCopy, ScoredMatch
from app.outbox import add_event
from app.scoring import score_match
from app.skills import extract_skills

log = logging.getLogger("consumer")

MAX_RETRIES = 3
DLQ_TOPIC = "scoring.dlq"
# Data errors: retrying will not help
NON_RETRYABLE = (ValueError, KeyError, TypeError)

llm = OllamaClient()


async def process_cv_event(record) -> str:
    msg = json.loads(record.value)
    event_type = msg["type"]
    if event_type not in ("cv.updated", "cv.deleted"):
        raise ValueError(f"unknown event type: {event_type}")
    user_id = uuid.UUID(msg["user_id"])

    async with SessionLocal() as session:
        async with session.begin():
            if event_type == "cv.deleted":
                await session.execute(delete(CVCopy).where(CVCopy.user_id == user_id))
                return "cv_deleted"
            text = msg["text"]
            skills = extract_skills(text)
            stmt = pg_insert(CVCopy).values(user_id=user_id, text=text, skills=skills)
            stmt = stmt.on_conflict_do_update(
                index_elements=[CVCopy.user_id],
                set_={"text": text, "skills": skills, "updated_at": func.now()},
            )
            await session.execute(stmt)
            return f"cv_stored skills={len(skills)}"


async def process_match_event(record) -> str:
    event = json.loads(record.value)
    job_id = uuid.UUID(event["job_id"])
    sub_id = uuid.UUID(event["subscription_id"])
    user_id = uuid.UUID(event["user_id"])

    async with SessionLocal() as session:
        if await session.get(ScoredMatch, (job_id, sub_id)):
            return "duplicate_skipped"
        cv = await session.get(CVCopy, user_id)

    # The slow LLM call happens outside any database transaction
    if cv is None:
        result = {"score": None, "basis": "no_cv", "matched_skills": [], "missing_skills": [],
                  "experience": None, "note": None, "llm": False}
    else:
        result = await score_match(cv.text, cv.skills, event, llm)

    data = {k: v for k, v in event.items() if k not in ("event_id", "occurred_at", "description")}
    data.update(result)

    async with SessionLocal() as session:
        async with session.begin():
            res = await session.execute(
                pg_insert(ScoredMatch)
                .values(job_id=job_id, subscription_id=sub_id)
                .on_conflict_do_nothing()
                .returning(ScoredMatch.job_id)
            )
            if res.scalar_one_or_none() is None:
                return "duplicate_skipped"
            add_event(session, "job.scored", f"{job_id}:{sub_id}", data)
    return f"scored score={result['score']} basis={result['basis']} llm={result['llm']}"


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


async def handle(record, dlq: AIOKafkaProducer, process):
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


async def run_consumer(topic: str, group_id: str, process):
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=settings.kafka_bootstrap,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        # one message can take minutes on a CPU-only LLM; the default (5 min) would kick us out of the group
        max_poll_interval_ms=1_200_000,
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

    log.info("consumer started: %s (group %s)", topic, group_id)
    try:
        async for record in consumer:
            await handle(record, dlq, process)
            await consumer.commit()
    finally:
        await consumer.stop()
        await dlq.stop()
