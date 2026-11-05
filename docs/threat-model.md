# Threat model

## Assets and trust boundaries

Protect tenant source contents, answer evidence, API credentials and audit integrity. The operator, ingestion files and Python provider code are trusted. Clients, user questions, retrieved text and provider return values are treated as potentially malformed. A hostile local administrator or arbitrary installed Python code is outside the isolation guarantee.

| Threat | Implemented control | Remaining risk |
|---|---|---|
| Cross-tenant query | Credential-derived identity; parameterized tenant SQL before retrieval | Misconfigured credential mapping grants wrong access; deploy managed identity |
| Citation fabrication | Exact quote membership in authoritative retrieved chunks | Quoted sources can be false or contextually misleading |
| Prompt injection | Narrow normalized pattern filters; no action or network tools | Heuristic bypasses remain; this is not a general injection classifier |
| Sensitive content | Email and SSN-shaped patterns in questions, title and text | Many forms of PII are not detected; false positives possible |
| Replay or duplicate IDs | Tenant-bound fingerprint, revision and transactional uniqueness | Concurrent compute can duplicate; expired IDs can be reused |
| Revoked/changed source | Admission and commit revision checks; cached revision conflict | Previously delivered data cannot be retracted; disk cache remains until cleanup |
| Resource exhaustion | 16 KiB body, query/top_k/output limits, tenant rate budgets | Fixed-window edge bursts, trusted-ingest size and large-tenant scan costs remain |
| Provider outage | Process-local circuit breaker, bounded output, generic abstention | No generic timeout for arbitrary Python code; network adapters need transport deadlines |
| Secret leakage through errors | No exception message or raw access log output | Deployment proxy/server logging must be reviewed independently |
| Audit tampering | Local chained hashes and verifier | Without external checkpoints, complete rewrite or tail truncation is undetectable |
| Credential theft | Constant-time comparisons, no persisted API credentials | Static credentials need TLS, secret management, rotation and least privilege |
| Dependency compromise | Zero core runtime deps, pinned optional tools and action SHAs | Base image tag and transitive tools are not fully hash-locked |

## Security test coverage

Tests include tenant spoof attempts, forged and mutated citations, sensitive/injection-bearing source titles, malformed/oversized JSON, cache revision races, tenant budget separation, concurrent retries, provider exceptions and stale circuit-breaker completions. The examples contain synthetic sensitive-pattern fixtures, not real personal data.

## Deployment boundary

Do not expose the stdlib development server. Place the optional production WSGI server behind a TLS reverse proxy with connection, request-header and idle-time limits. Restrict ingestion to trusted operators; do not ingest unreviewed confidential documents into the public demo. Do not use the project as the sole control protecting regulated data.
