# ADR-0002: Transactional Outbox for the job.created event

**Status:** Accepted
**Deciders:** Project owner

## Context
When a new job is created, job-service must write to the database and publish a `job.created` event. These are two different systems, so a failure between the two steps either loses the event or publishes an event for a job that does not exist.

## Decision
Write the event to an `outbox` table in the same transaction as the job. A background publisher reads unpublished rows, sends them to Kafka, then sets `published_at`.

## Options Considered

### Option A: Transactional Outbox
**Pros:** no lost events; no distributed transaction needed.
**Cons:** one extra table and process; small latency (1 second poll interval); at-least-once delivery, so duplicates are possible.

### Option B: Write to the database, then publish to Kafka directly
**Pros:** simple.
**Cons:** the event is lost if the service crashes or Kafka is down between the two steps.

### Option C: Change Data Capture (e.g. Debezium)
**Pros:** no polling, low latency.
**Cons:** significant extra infrastructure, too heavy for the current scale.

## Trade-off Analysis
The outbox gives the desired reliability at low cost. CDC is the upgrade path if latency becomes a concern.

## Consequences
- Easier: guarantee that every created job has a corresponding event.
- Harder: consumers must tolerate duplicate events, hence the `event_id` on every event.
- To revisit: periodic cleanup of old outbox rows.
