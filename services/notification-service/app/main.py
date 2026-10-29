import asyncio
import logging

from app.consumer import run_consumer

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    asyncio.run(run_consumer())
