import asyncio
import logging

from app.consumer import run_consumer
from app.outbox import run_publisher

logging.basicConfig(level=logging.INFO)


async def main():
    await asyncio.gather(run_consumer(), run_publisher())


if __name__ == "__main__":
    asyncio.run(main())
