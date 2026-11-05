# Local validation record

Validation date: 2026-11-05. Environment: Linux, Python 3.12.14. All data was synthetic and no external model was called.

- 71 unit, API-boundary, integration, CLI, security-regression and concurrency tests passed.
- 25/25 checked-in gold-label evaluation cases passed; audit verification passed.
- Coverage.py measured 95% line coverage of the package. This is line coverage, not branch coverage or proof of correctness.
- Ruff lint and formatting checks passed.
- Source distribution and wheel build succeeded.
- A real local Waitress 3.0.2 process served a health request and an authenticated query returning the expected cited answer.
- Independent review reproduced four defects (source-title filtering, stale-cache revocation race, shared mutable hit list, stale circuit completion); each was fixed and covered by a targeted regression test. Re-review found no remaining critical issue.

Docker was not available in the local execution environment. The committed GitHub Actions workflow includes a fresh Docker build and health/authenticated-query smoke test; inspect the exact commit's CI run for its observed result. Multi-version execution is also delegated to the checked-in CI matrix. This document does not imply those CI stages ran locally.

These results describe this development validation only. They do not establish real-domain model accuracy, throughput, a service-level objective, production deployment, security certification or compliance.
