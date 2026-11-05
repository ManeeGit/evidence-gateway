# ADR 002: Use a single-host SQLite transaction boundary

Status: accepted.

Keep source metadata, request cache, tenant budgets and audit events in one local transactional store so the demo has no service dependencies. WAL and per-operation connections allow ordinary threaded readers, while immediate transactions serialize writes. Content-derived tenant revisions make stale source state explicit; concurrent source changes produce a conflict instead of a stale answer.

The tradeoff is whole-tenant scans, serialized write paths and no distributed consensus or HA. A larger deployment should move source/index revisions and idempotency into a database with an explicit transaction design, with tenant enforcement at every retrieval backend. Switching databases must preserve the tested invariants rather than merely changing the connection string.
