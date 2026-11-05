# Evaluation design

## Release contract

`python -m evidence_gateway evaluate` loads the checked-in synthetic corpus into a new temporary database and runs 25 unique cases. It creates no external requests or billable model calls. The report contains per-case checks and a strict all-pass gate. The command exits 1 if any assertion or audit verification fails.

Cases cover backup, incident, access and deployment questions, different answers for two tenants, a tenant canary, an unknown tenant, out-of-domain questions, instruction attacks, Unicode normalization, email/SSN-shaped input and poisoned/sensitive source filtering.

## Metrics

- `pass_rate`: cases where every declared check passed divided by all cases.
- `citation_document_hit_rate`: fraction of cases with a gold document label that cite that document at least once. This is **not** recall@k, MRR, answer precision or a semantic faithfulness score.
- `citation_integrity`: every returned quote occurs in the authorized source document and carries the current version.
- `nonanswer_is_empty`: blocked/abstained outcomes contain no answer or citations.
- Expected fragment, expected status and forbidden-content checks are explicit per case.

The checked-in examples are small and intentionally lexical. They are suited to deterministic regression prevention, not statistical claims about unseen enterprise questions. Passing 25/25 is not “100% accurate AI.” No live LLM model or judge is evaluated.

## Extending responsibly

Add independently labeled questions, paraphrases, irrelevant distractors, conflicting versions, authorization failures and actual domain negatives. Keep a holdout set separate from development cases. Measure answerability, abstention calibration, retrieval ranking and latency by tenant size before choosing thresholds. Record provider/model version, prompt version, corpus revision and cost if adding a live adapter. Never copy private customer documents into public fixtures.

## Quality workflow

The unit suite tests mechanisms separately from gold scenarios. It includes deterministic clocks and coordinated threads for race tests. CI runs supported Python versions, lint/format, at least 80% line coverage, the evaluation gate, a narrow credential-pattern scanner, package build and Docker health/authenticated-query smoke test. The scanner is not a replacement for a mature secret-scanning service or dependency security review.
