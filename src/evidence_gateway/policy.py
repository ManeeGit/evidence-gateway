"""Defense in depth, not a complete prompt injection or PII detector."""

import re
import unicodedata
from .models import Claim, Hit
from .retrieval import tokens

INJECTION = re.compile(
    r"ignore\s+(all\s+|the\s+|any\s+)?(previous|prior|system)\s+instructions|"
    r"system\s*prompt|reveal\s+(your\s+)?secrets|"
    r"(?:send|upload|exfiltrate)\s+.{0,80}(?:https?://|credentials)|"
    r"<\s*/?\s*(?:system|assistant)\s*>",
    re.IGNORECASE,
)
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def unsafe(text: str) -> bool:
    return bool(INJECTION.search(normalized(text)))


def contains_sensitive_pattern(text: str) -> bool:
    return bool(EMAIL.search(text) or SSN.search(normalized(text)))


def validate_claims(
    claims: tuple[Claim, ...], hits: list[Hit], max_chars: int = 1800
) -> bool:
    if not claims or len(claims) > 3:
        return False
    allowed = {hit.chunk.id: hit.chunk for hit in hits}
    total = 0
    seen = set()
    for claim in claims:
        if not isinstance(claim, Claim) or not isinstance(claim.quote, str):
            return False
        chunk = allowed.get(claim.chunk_id)
        if chunk is None or not claim.quote.strip() or claim.quote not in chunk.text:
            return False
        if unsafe(claim.quote) or contains_sensitive_pattern(claim.quote):
            return False
        key = (claim.chunk_id, claim.quote)
        if key in seen:
            return False
        seen.add(key)
        total += len(claim.quote)
    return total <= max_chars


def query_coverage(question: str, hits: list[Hit]) -> float:
    query = set(tokens(question))
    evidence = set(tokens(" ".join(hit.chunk.text for hit in hits)))
    return len(query & evidence) / len(query) if query else 0.0
