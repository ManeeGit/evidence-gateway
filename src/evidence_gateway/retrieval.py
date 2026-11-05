"""Deterministic BM25 over an already-authorized document snapshot."""

from collections import Counter
import math
import re
import unicodedata
from .models import Chunk, Document, Hit

STOPWORDS = frozenset(
    "a an and are as at be by can do does for from how i in is it me of on or our the their this to was what when where which who with your we should".split()
)


def tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return [x for x in re.findall(r"[a-z0-9]+", normalized) if x not in STOPWORDS]


def chunk_documents(documents: list[Document], max_chars: int = 800) -> list[Chunk]:
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100")
    chunks = []
    for doc in sorted(documents, key=lambda d: d.id):
        # Exact slices preserve citation provenance, including punctuation and whitespace.
        start = 0
        part = 0
        while start < len(doc.text):
            end = min(start + max_chars, len(doc.text))
            if end < len(doc.text):
                boundary = doc.text.rfind(" ", start + max_chars // 2, end)
                if boundary != -1:
                    end = boundary
            text = doc.text[start:end].strip()
            if text:
                chunks.append(
                    Chunk(f"{doc.id}:{part}", doc.id, doc.title, text, doc.version)
                )
                part += 1
            start = end
    return chunks


def rank(question: str, chunks: list[Chunk], top_k: int = 3) -> list[Hit]:
    query = set(tokens(question))
    if not query or not chunks:
        return []
    counts = [Counter(tokens(c.title + " " + c.text)) for c in chunks]
    lengths = [sum(c.values()) for c in counts]
    avg_length = sum(lengths) / len(lengths) or 1
    frequencies = {term: sum(term in count for count in counts) for term in query}
    hits = []
    for chunk, count, length in zip(chunks, counts, lengths):
        score = 0.0
        for term in query:
            tf = count[term]
            if tf:
                df = frequencies[term]
                idf = math.log(1 + (len(chunks) - df + 0.5) / (df + 0.5))
                score += (
                    idf * (tf * 2.5) / (tf + 1.5 * (0.25 + 0.75 * length / avg_length))
                )
        if score > 0:
            hits.append(Hit(chunk, round(score, 8)))
    return sorted(hits, key=lambda hit: (-hit.score, hit.chunk.id))[:top_k]
