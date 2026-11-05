# HTTP API

The WSGI factory is `evidence_gateway.api:from_environment`. `GET /healthz` is unauthenticated liveness only; it does not validate database readiness. `POST /v1/query` requires `Authorization: Bearer <token>` and `Content-Type: application/json`.

## Request

```json
{"question":"How long are backup snapshots retained?","request_id":"client-unique-id","top_k":3}
```

- `question`: nonblank string, at most 2,000 raw characters.
- `request_id`: 1–80 ASCII letters/digits/underscore/dot/hyphen, beginning with a letter or digit.
- `top_k`: optional integer 1–5, default 3. Booleans are not accepted as integers.
- Extra fields, duplicate keys, nonstandard JSON constants and malformed input are rejected.
- Maximum body size is 16,384 bytes. Content-Length is required; chunked transfer encoding is not supported by this application boundary.

## Response

```json
{
  "request_id":"client-unique-id",
  "status":"answered",
  "answer":"Backup snapshots are retained for 35 days.",
  "citations":[{"chunk_id":"backup-policy:0","document_id":"backup-policy","title":"Database backup policy","version":1,"quote":"Backup snapshots are retained for 35 days."}],
  "index_revision":"64-character content digest",
  "reason":"validated_evidence",
  "provider":"extractive-v1"
}
```

Statuses are `answered`, `abstained` and `blocked`. An abstention/block has empty answer and citations. Reasons include `insufficient_evidence`, `instruction_pattern`, `sensitive_pattern`, `invalid_provider_output` and `provider_unavailable`. These are domain outcomes with HTTP 200, not server failures. Clients must inspect `status`, not just the HTTP status code.

HTTP errors return only a stable `error` code: 400 invalid input; 401 unauthorized; 404 route not found; 405 unsupported method; 409 request-ID or index-revision conflict; 413 invalid body size; 415 non-JSON input; 429 tenant budget exceeded; 503 internal/storage failure. A 429 includes `Retry-After: 60`; this conservative bound may exceed the current fixed-window remainder. All responses include `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.

## Credential configuration

`EVIDENCE_CREDENTIALS` is a JSON object from high-entropy printable, non-whitespace ASCII tokens (32–512 characters) to tenant IDs. Multiple tokens can map to a tenant for rotation. The mapping is read at process startup. `EVIDENCE_AUDIT_KEY` is a separate secret of at least 32 UTF-8 bytes used for query fingerprints; retain it across restarts. `EVIDENCE_DB` defaults to `var/evidence.db`.

No administrative mutation endpoint, CORS policy, user session or credential creation API is exposed.
