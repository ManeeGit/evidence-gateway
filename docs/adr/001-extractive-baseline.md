# ADR 001: Start with a deterministic extractive provider

Status: accepted.

A remote generative provider would introduce credentials, external data transmission, cost and nondeterminism before isolation and evidence contracts can be tested. The shipped baseline uses BM25 and verbatim source sentences. It is reproducible offline and gives exact citation verification. The tradeoff is limited paraphrase recall and no synthesis across evidence. A future adapter must return quote claims rather than unconstrained prose, preserve the same validation boundary, implement transport timeouts and run against a separately labeled evaluation set. We do not represent this baseline as an LLM.
