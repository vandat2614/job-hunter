#!/usr/bin/env bash
# Create all Kafka topics (idempotent). Requires the kafka container to be running.
set -euo pipefail

KAFKA="docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092"

for _ in $(seq 1 30); do
  $KAFKA --list > /dev/null 2>&1 && break
  sleep 2
done

create() {
  $KAFKA --create --if-not-exists --topic "$1" --partitions "$2" --replication-factor 1
}

create job.raw 3
create job.created 3
create job.matched 3
create job.scored 3
create subscription.events 3
create cv.events 3
create job.raw.dlq 1
create matching.dlq 1
create notification.dlq 1
create scoring.dlq 1
echo "Topics ready."
