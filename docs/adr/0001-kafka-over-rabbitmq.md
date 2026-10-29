# ADR-0001: Use Kafka as the message broker

**Status:** Accepted
**Deciders:** Project owner

## Context
The crawler and job-service must communicate asynchronously. Later, several services (matching, notification) will need to read `job.created` events independently. When the normalization logic changes, old data must be reprocessable without crawling again.

## Decision
Use Apache Kafka (KRaft mode, a single broker for development).

## Options Considered

### Option A: Kafka
| Dimension | Assessment |
|---|---|
| Complexity | Higher than RabbitMQ |
| Cost | Heavier to run locally |
| Scalability | Very good |
| Team familiarity | High (existing experience) |

**Pros:** durable log enables replay; independent consumer groups; ordering guaranteed per partition key.
**Cons:** heavier to operate; overkill for a simple task queue.

### Option B: RabbitMQ
| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Cost | Light |
| Scalability | Sufficient for this scale |
| Team familiarity | Low |

**Pros:** easy to set up, flexible routing.
**Cons:** messages are removed once consumed, so no replay.

## Trade-off Analysis
Replay and independent consumers are real requirements of this pipeline, so the higher operational cost of Kafka is accepted.

## Consequences
- Easier: adding new consumers, reprocessing old data.
- Harder: heavier compose setup, topic and partition management.
- To revisit: partition count and replication factor when moving to a multi-broker cluster.
