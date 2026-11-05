# Deployment and operations

## Local and container execution

The zero-dependency CLI is for local evaluation. The optional image uses pinned Waitress 3.0.2, runs as UID/GID 10001 and keeps data under `/data`. Build and smoke-test locally:

```sh
sh scripts/container_smoke.sh
```

The script creates only a disposable local image, container and volume. It ingests the synthetic corpus, generates temporary credentials, verifies health and an authenticated answer, then removes the container/volume. It does not publish images or deploy cloud resources.

For a persistent deployment, supply `EVIDENCE_DB`, `EVIDENCE_CREDENTIALS` and `EVIDENCE_AUDIT_KEY` via a secret manager or protected runtime environment. Mount writable storage owned by UID 10001 at `/data`. Do not bake credentials or private data into the image. Use a read-only root filesystem where feasible, a writable `/data` mount, resource limits and TLS termination. The Python base image is a moving minor-version tag: resolve and review a digest in your release pipeline before production rollout.

## Suggested operational measurements

These are recommendations, not implemented telemetry or promised SLOs:

- HTTP error, abstention, blocked-query and rate-limit rates by tenant.
- P50/P95 query latency across increasing corpus sizes.
- SQLite lock wait/errors, disk space and WAL growth.
- Provider circuit transitions and failure reasons without prompts or credentials.
- Audit verification failures and externally anchored audit head/sequence.

`/healthz` reports process liveness only. For readiness, verify a database read and schema version through an operator-controlled probe. Avoid a public diagnostics endpoint containing tenant details.

## Runbook: 409 conflicts

For a completed request ID used against changed input/index, generate a new ID. For an index change before admission or during generation, retry with bounded backoff. The current HTTP response intentionally uses one generic conflict code. Inspect authorized operational activity, not raw prompt logs, to correlate ingestion changes.

## Runbook: provider failures

The offline provider should not require external connectivity. An adapter exception produces `abstained/provider_unavailable`. After three failures the local breaker opens for 30 seconds. Each worker has its own breaker; it is not shared across processes. A half-open probe can restore service. Generic Python work cannot be forcibly timed out safely in this library; remote adapters must implement connection/read/overall deadlines, bounded retries and cost budgets before being enabled.

## Backups and recovery

Use Python's SQLite backup API (or another supported online SQLite backup procedure), not a naked copy of a live main file that ignores WAL. Keep the database and its stable HMAC key available to the same recovery boundary; never place the key inside the public repository or database. Encrypt backups and test a restore into an isolated instance. Run `python -m evidence_gateway verify-audit --db <restored-path>` and compare head/event count against an independent checkpoint. An attacker with both original database and checkpoint control can bypass this check.

## Retention and deletion

Completed responses persist with a default 24-hour cache TTL and are deleted lazily when another request is admitted. No background purge is implemented, so an idle database can retain expired rows longer. Source deletion invalidates cached serving but does not erase old cached answer text or historical backups. Audit events have no automatic retention policy. Implement an authorized retention job, storage encryption, backup retention and secure disposal appropriate to the deployment's data obligations.

## Production-readiness checklist

- [ ] Managed identity and reviewed credential-to-tenant mapping; rotation/revocation process.
- [ ] TLS, reverse-proxy request/connection limits, trusted ingress and network isolation.
- [ ] Storage and backup encryption, access control, retention and deletion policy.
- [ ] Real-domain holdout evaluation and adversarial review beyond regex heuristics.
- [ ] Provider network deadlines, cost budgets and explicit data-sharing approval if adding a live model.
- [ ] Measured capacity, failure recovery, load testing and agreed availability objectives.
- [ ] Immutable external audit checkpoints and monitored verification.
- [ ] Reviewed dependency/image locks, SBOM and vulnerability scans.
- [ ] Independent security assessment and applicable compliance review.

This checklist is deliberately unchecked: these deployment-specific controls are not proven by this repository.
