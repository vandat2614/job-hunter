import asyncio
import logging

from app.consumer import process_cv_event, process_match_event, run_consumer
from app.outbox import run_publisher

logging.basicConfig(level=logging.INFO)


async def main():
    await asyncio.gather(
        run_consumer("cv.events", "scoring-cv", process_cv_event),
        run_consumer("job.matched", "scoring-jobs", process_match_event),
        run_publisher(),
    )


if __name__ == "__main__":
    asyncio.run(main())
