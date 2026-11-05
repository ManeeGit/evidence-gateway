"""Orchestration: authorization precedes retrieval; every output fails closed."""

import hashlib
import hmac
from .models import Answer, GatewayError, identifier
from .policy import contains_sensitive_pattern, query_coverage, unsafe, validate_claims
from .providers import CircuitBreaker, ExtractiveProvider
from .retrieval import chunk_documents, rank
from .store import Store, canonical


class Engine:
    def __init__(
        self,
        store: Store,
        *,
        audit_key: bytes,
        provider=None,
        breaker=None,
        per_minute: int = 60,
    ):
        if not isinstance(audit_key, bytes) or len(audit_key) < 32:
            raise ValueError("audit_key must be at least 32 bytes")
        if type(per_minute) is not int or per_minute < 1:
            raise ValueError("per_minute must be a positive integer")
        self.store = store
        self.audit_key = audit_key
        self.provider = provider or ExtractiveProvider()
        self.breaker = breaker or CircuitBreaker()
        self.per_minute = per_minute

    def query(
        self, tenant: str, question: str, request_id: str, top_k: int = 3
    ) -> dict:
        identifier(tenant)
        identifier(request_id)
        if (
            not isinstance(question, str)
            or not question.strip()
            or len(question) > 2000
        ):
            raise GatewayError("Question must contain 1-2000 characters")
        if type(top_k) is not int or not 1 <= top_k <= 5:
            raise GatewayError("top_k must be an integer between 1 and 5")
        docs, index_revision = self.store.snapshot(tenant)
        fingerprint = hmac.new(
            self.audit_key,
            canonical(
                {
                    "question": question,
                    "top_k": top_k,
                    "policy": "v1",
                    "provider": self.provider.name,
                }
            ).encode(),
            hashlib.sha256,
        ).hexdigest()
        cached = self.store.begin_request(
            tenant, request_id, fingerprint, index_revision, per_minute=self.per_minute
        )
        if cached is not None:
            return cached
        claims = ()
        hits = []
        status, reason = "abstained", "insufficient_evidence"
        if unsafe(question):
            status, reason = "blocked", "instruction_pattern"
        elif contains_sensitive_pattern(question):
            status, reason = "blocked", "sensitive_pattern"
        else:
            # Filter before ranking, not after returning candidate scores or snippets.
            chunks = [
                c
                for c in chunk_documents(docs)
                if not unsafe(c.title + " " + c.text)
                and not contains_sensitive_pattern(c.title + " " + c.text)
            ]
            hits = rank(question, chunks, top_k)
            if hits and query_coverage(question, hits) >= 0.35:
                try:
                    proposed = self.breaker.call(
                        lambda: self.provider.generate(question, list(hits))
                    )
                    if validate_claims(proposed, hits):
                        claims = proposed
                        status, reason = "answered", "validated_evidence"
                    else:
                        reason = "invalid_provider_output"
                except Exception:
                    # Provider error text can contain prompts, credentials or document text.
                    reason = "provider_unavailable"
        sources = {hit.chunk.id: hit.chunk for hit in hits}
        citations = tuple(
            {
                "chunk_id": claim.chunk_id,
                "document_id": sources[claim.chunk_id].document_id,
                "title": sources[claim.chunk_id].title,
                "version": sources[claim.chunk_id].version,
                "quote": claim.quote,
            }
            for claim in claims
        )
        answer = Answer(
            request_id,
            status,
            "\n".join(c.quote for c in claims),
            citations,
            index_revision,
            reason,
            self.provider.name,
        ).to_dict()
        return self.store.finish_request(
            tenant, request_id, fingerprint, index_revision, answer
        )
