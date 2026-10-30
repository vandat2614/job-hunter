#!/usr/bin/env bash
# End-to-end demo: register -> upload CV -> subscribe -> inject a matching job -> scored notification.
# Usage: scripts/demo.sh [telegram_chat_id]
# Without a chat id the notification-service only logs the outcome.
# Scoring runs a local LLM on CPU, so the last step can take a few minutes.
set -euo pipefail

cd "$(dirname "$0")/.."
CHAT_ID="${1:-}"
EMAIL="demo-$(date +%s)@example.com"
PASSWORD="demo-password-123"
JOB_ID="demo-$(date +%s)"
API="http://localhost"

echo "1. Registering $EMAIL"
curl -sf -X POST "$API/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" > /dev/null
TOKEN=$(curl -sf -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "2. Uploading a sample CV"
curl -sf -X PUT "$API/cvs/me" -H "Authorization: Bearer $TOKEN" \
  -F "file=@scripts/sample_cv.txt" > /dev/null

echo "3. Creating a subscription (python + kafka, remote, >= 1000 USD)"
CHAT_JSON="null"
[ -n "$CHAT_ID" ] && CHAT_JSON="\"$CHAT_ID\""
curl -sf -X POST "$API/subscriptions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"skills\":[\"python\",\"kafka\"],\"location\":\"remote\",\"min_salary\":1000,\"currency\":\"usd\",\"telegram_chat_id\":$CHAT_JSON}" > /dev/null

echo "   waiting for the CV and the subscription to reach the other services..."
sleep 8

BEFORE=$(docker compose logs notification-service 2>/dev/null | grep -c "offset=" || true)

echo "4. Injecting a matching job ($JOB_ID)"
docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 --topic job.raw \
  --property parse.key=true --property key.separator='|' << MSG
demo:$JOB_ID|{"source":"demo","source_job_id":"$JOB_ID","url":"https://example.com/jobs/$JOB_ID","payload":{"title":"Senior Python Engineer","company":"Demo Co","location":"Remote","salary_text":"\$3000 - \$4000","description":"5+ years building distributed systems. Python, Kafka, Docker, AWS. Mentor juniors."}}
MSG

echo "5. Waiting for scoring (up to 5 minutes)..."
for _ in $(seq 1 60); do
  NOW=$(docker compose logs notification-service 2>/dev/null | grep -c "offset=" || true)
  [ "$NOW" -gt "$BEFORE" ] && break
  sleep 5
done

echo "--- scoring-service log ---"
docker compose logs scoring-service --tail 4
echo "--- notification-service log ---"
docker compose logs notification-service --tail 12
