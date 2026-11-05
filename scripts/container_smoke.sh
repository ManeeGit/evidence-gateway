#!/bin/sh
set -eu
docker build -t evidence-gateway:smoke .
# Disposable, synthetic-only database and locally generated credentials.
TOKEN=$(python -c 'import secrets; print(secrets.token_hex(24))')
AUDIT=$(python -c 'import secrets; print(secrets.token_hex(32))')
NAME="evidence-smoke-$$"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true; docker volume rm "$NAME" >/dev/null 2>&1 || true' EXIT
# Docker initializes a fresh named volume with /data ownership from the image.
docker volume create "$NAME" >/dev/null
docker run --rm -v "$NAME:/data" evidence-gateway:smoke python -m evidence_gateway ingest examples/documents.json --db /data/evidence.db
docker run -d --name "$NAME" -p 127.0.0.1::8080 -v "$NAME:/data" \
  -e "EVIDENCE_AUDIT_KEY=$AUDIT" -e "EVIDENCE_CREDENTIALS={\"$TOKEN\":\"acme\"}" evidence-gateway:smoke >/dev/null
PORT=$(docker port "$NAME" 8080/tcp | sed 's/.*://')
ATTEMPT=0
until curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null; do
  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -ge 30 ]; then exit 1; fi
  sleep 1
done
curl -fsS "http://127.0.0.1:$PORT/v1/query" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"question":"How long are backup snapshots retained?","request_id":"smoke"}' \
  | python -c 'import json,sys; r=json.load(sys.stdin); assert r["status"] == "answered" and "35 days" in r["answer"]'
echo 'Container health and authenticated query passed'
