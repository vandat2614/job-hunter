#!/usr/bin/env bash
# Publish one fake job to job.raw so the whole pipeline can be shown live.
# Usage: scripts/inject-job.sh ["Job title"] ["skills text"]   (no double quotes inside the arguments)
set -euo pipefail

cd "$(dirname "$0")/.."
TITLE="${1:-Senior Python Engineer}"
SKILLS="${2:-Python, Kafka, Docker, AWS}"
ID="inject-$(date +%s)"

docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 --topic job.raw \
  --property parse.key=true --property key.separator='|' << MSG
inject:$ID|{"source":"inject","source_job_id":"$ID","url":"https://example.com/jobs/$ID","payload":{"title":"$TITLE","company":"Demo Co","location":"Remote","salary_text":"\$3000 - \$4000","description":"5+ years building distributed systems. $SKILLS. Mentor juniors."}}
MSG
echo "Injected job $ID"
