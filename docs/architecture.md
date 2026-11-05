# Architecture and invariants

## Trusted and untrusted inputs

The application trusts the local operator's credential-to-tenant mapping and local document-ingestion files. A web client is untrusted. Request fields cannot select a tenant, upload documents, execute tools or supply URLs. A generator receives only the selected tenant's filtered hits. The provider interface is trusted in-process Python, so it is not isolation against malicious Python code; separate list copies prevent accidental mutation of the authoritative hit list.

## Read path

1. Authenticate a high-entropy bearer credential using constant-time comparison; resolve its tenant.
2. Reject oversized, malformed, duplicate-key or extra-field JSON. Limit question to 2,000 raw characters and top_k to 1–5.
3. Select only that tenant's documents and compute a SHA-256 revision over sorted canonical document contents, titles and versions.
4. In an immediate SQLite transaction, confirm the snapshot revision still matches; return a matching cached response or charge the tenant's fixed-minute budget.
5. Slice source text into bounded chunks. Filter instruction and sensitive-data patterns in title and text before BM25 ranking. Require at least 35% of query terms to occur in selected chunk text.
6. Invoke the provider through a process-local breaker. The baseline selects up to two source sentences.
7. Validate up to three claims totaling at most 1,800 characters. Every quote must be an exact substring of a retrieved chunk. Reject unknown citations, duplicates and detected unsafe output.
8. In one transaction, recheck revision, resolve concurrent duplicate/conflicting IDs, write the response and append one audit event.

Authorization is enforced at the SQL selection boundary, not by post-filtering an already-computed global ranking. A final source revision check closes changes occurring during generation; as with ordinary reads, a change after that commit cannot retroactively revoke bytes already delivered.

## Write path

Ingestion is a trusted local operation. `(tenant, document_id)` is the source primary key. Identical ingestion is a no-op. Changed documents require a strictly increasing positive integer version. A conflict rolls back the entire batch, including earlier valid entries. A deletion changes the content-derived revision; any old committed request ID now conflicts rather than returning its cached text.

## Idempotency semantics

The fingerprint is an HMAC of canonical question, top_k, policy version and provider name. The stable HMAC key must be retained across restarts; rotation invalidates matching of existing cache records. Cache keys are `(tenant, request_id)`, with a 24-hour retention window. Concurrent duplicate queries can compute twice and consume multiple budget units, but commit one answer/audit record. Providers must be side-effect-free. There is no exactly-once external operation claim.

## SQLite concurrency and schema

Connections are per operation, with a five-second busy timeout and WAL mode. Mutations use `BEGIN IMMEDIATE`; no connection is shared between threads. Index revision and response commit are checked within a single write transaction. Schema version 1 is recorded using `PRAGMA user_version`; unknown versions fail startup. This is a single-host design, not a network-filesystem or multi-region database pattern.

## Audit properties

Audit events store tenant, request ID, provider, status/reason, document IDs, revision, timestamp and keyed query fingerprint, never the raw question or answer. Response text is separately stored in the retry cache. Every audit event hashes its predecessor's hash plus canonical event JSON. The verifier detects accidental or uncoordinated mutation. A privileged attacker can rewrite or truncate the complete chain: periodically export the head and event count to independently controlled immutable storage to detect that class of modification.

## Architectural decisions

- [ADR 001: deterministic extractive baseline](adr/001-extractive-baseline.md)
- [ADR 002: SQLite revision-aware transactions](adr/002-sqlite-transactions.md)
