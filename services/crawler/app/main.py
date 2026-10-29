import asyncio
import json
import logging

from aiokafka import AIOKafkaProducer
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.sources import remoteok

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("crawler")

SOURCES = [remoteok]


async def crawl_once(producer: AIOKafkaProducer):
    for src in SOURCES:
        try:
            messages = await src.fetch()
        except Exception:
            log.exception("source %s failed", src.SOURCE)
            continue
        for m in messages:
            await producer.send(
                "job.raw", value=m, key=f"{m['source']}:{m['source_job_id']}"
            )
        await producer.flush()
        log.info("source=%s sent=%d", src.SOURCE, len(messages))


async def main():
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
        raise SystemExit("cannot connect to kafka")

    await crawl_once(producer)  # chạy ngay một lần khi khởi động

    scheduler = AsyncIOScheduler()
    scheduler.add_job(crawl_once, "interval", minutes=settings.crawl_interval_minutes, args=[producer])
    scheduler.start()
    log.info("scheduler started, every %d min", settings.crawl_interval_minutes)

    await asyncio.Event().wait()  # giữ process sống


if __name__ == "__main__":
    asyncio.run(main())
