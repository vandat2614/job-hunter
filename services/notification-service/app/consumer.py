import asyncio
import json
import logging
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from app.config import settings
from app.db import SessionLocal
from app.formatter import format_message
from app.models import SentNotification
from app.telegram import PermanentError, send_message

log = logging.getLogger("consumer")

MAX_RETRIES = 3
DLQ_TOPIC = "notification.dlq"
# Data or permanent errors: retrying will not help
NON_RETRYABLE = (ValueError, KeyError, TypeError, PermanentError)


async def process(record) -> str:
    event = json.loads(record.value)
    event_id = uuid.UUID(event["event_id"])

    async with SessionLocal() as session:
        if await session.get(SentNotification, event_id):
            return "duplicate_skipped"

    chat_id = event.get("telegram_chat_id")
    if not chat_id:
        status = "skipped_no_chat_id"
    else:
        status = await send_message(chat_id, format_message(event))

    # If the process dies right here the message may be sent twice: at-least-once delivery
    async with SessionLocal() as session:
        async with session.begin():
            session.add(SentNotification(event_id=event_id, status=status))
    return status


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
            log.info("offset=%s %s", record.offset, result)
            return
        except NON_RETRYABLE as e:
            last_error = e
            break
        except Exception as e:
            last_error = e
            log.warning("offset=%s attempt %d/%d failed: %s", record.offset, attempt, MAX_RETRIES, e)
            await asyncio.sleep(2 ** attempt)
    log.error("offset=%s -> DLQ: %s", record.offset, last_error)
    await send_to_dlq(dlq, record, last_error)


async def run_consumer():
    consumer = AIOKafkaConsumer(
        "job.scored",
        bootstrap_servers=settings.kafka_bootstrap,
        group_id="notification-service",
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

    mode = "live" if settings.telegram_bot_token else "dry-run"
    log.info("consumer started (%s mode)", mode)
    try:
        async for record in consumer:
            await handle(record, dlq)
            await consumer.commit()
    finally:
        await consumer.stop()
        await dlq.stop()
