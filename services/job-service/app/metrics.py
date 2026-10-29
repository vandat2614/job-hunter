from prometheus_client import Counter, Histogram

MESSAGES = Counter(
    "jobhunter_messages_total", "Messages processed from job.raw", ["result"]
)
PROCESS_SECONDS = Histogram(
    "jobhunter_process_seconds", "Time to process one job.raw message"
)
EVENTS_PUBLISHED = Counter(
    "jobhunter_outbox_published_total", "Outbox events published to Kafka", ["topic"]
)
