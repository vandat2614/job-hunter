#!/usr/bin/env bash
# End-to-end demo: register -> subscribe -> inject a matching job -> notification.
# Usage: scripts/demo.sh [telegram_chat_id]
# Without a chat id the notification-service runs in dry-run mode and logs the message.
set -euo pipefail

CHAT_ID="${1:-}"
EMAIL="demo-$(date +%s)@example.com"
PASSWORD="demo-password-123"
JOB_ID="demo-$(date +%s)"
USER_API="http://localhost"

echo "1. Registering $EMAIL"
curl -sf -X POST "$USER_API/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" > /dev/null

TOKEN=$(curl -sf -X POST "$USER_API/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

echo "2. Creating a subscription (python + kafka, remote, >= 1000 USD)"
CHAT_JSON="null"
[ -n "$CHAT_ID" ] && CHAT_JSON="\"$CHAT_ID\""
curl -sf -X POST "$USER_API/subscriptions" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"skills\":[\"python\",\"kafka\"],\"location\":\"remote\",\"min_salary\":1000,\"currency\":\"usd\",\"telegram_chat_id\":$CHAT_JSON}" > /dev/null

echo "   waiting for the subscription to reach matching-service..."
sleep 5

echo "3. Injecting a matching job ($JOB_ID)"
docker compose exec -T kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 --topic job.raw \
  --property parse.key=true --property key.separator='|' << MSG
demo:$JOB_ID|{"source":"demo","source_job_id":"$JOB_ID","url":"https://example.com/jobs/$JOB_ID","payload":{"title":"Demo Python Engineer","company":"Demo Co","location":"Remote","salary_text":"\$3000 - \$4000","description":"Python, Kafka, Docker"}}
MSG

echo "4. Waiting for the pipeline..."
sleep 10

echo "--- notification-service log ---"
docker compose logs notification-service --tail 8
