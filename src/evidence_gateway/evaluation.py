"""Gold-label release gates. No model judges, network calls or hidden services."""

import json
from pathlib import Path
import tempfile
from .engine import Engine
from .models import Document
from .store import Store


def evaluate(documents_path: str | Path, cases_path: str | Path) -> dict:
    documents = [
        Document(**row) for row in json.loads(Path(documents_path).read_text())
    ]
    cases = json.loads(Path(cases_path).read_text())
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Evaluation requires unique, nonempty case IDs")
    results = []
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "evaluation.db")
        store.ingest(documents)
        engine = Engine(
            store, audit_key=b"synthetic-evaluation-key-32-bytes!", per_minute=10000
        )
        for case in cases:
            answer = engine.query(case["tenant"], case["question"], case["id"])
            checks = {"status": answer["status"] == case["status"]}
            if "document" in case:
                checks["retrieval_hit"] = case["document"] in {
                    citation["document_id"] for citation in answer["citations"]
                }
            if "contains" in case:
                checks["expected_evidence"] = (
                    case["contains"].casefold() in answer["answer"].casefold()
                )
            if "forbidden" in case:
                checks["no_forbidden_content"] = (
                    case["forbidden"].casefold() not in json.dumps(answer).casefold()
                )
            authorized = {
                doc.id: doc for doc in documents if doc.tenant == case["tenant"]
            }
            checks["citation_integrity"] = all(
                cite["document_id"] in authorized
                and cite["quote"] in authorized[cite["document_id"]].text
                and cite["version"] == authorized[cite["document_id"]].version
                for cite in answer["citations"]
            )
            checks["nonanswer_is_empty"] = answer["status"] == "answered" or (
                not answer["answer"] and not answer["citations"]
            )
            results.append(
                {
                    "id": case["id"],
                    "passed": all(checks.values()),
                    "checks": checks,
                    "actual_status": answer["status"],
                }
            )
        audit = store.verify_audit()
    correct = sum(result["passed"] for result in results)
    retrieval = [
        r["checks"]["retrieval_hit"] for r in results if "retrieval_hit" in r["checks"]
    ]
    return {
        "schema_version": 1,
        "provider": "extractive-v1",
        "total": len(results),
        "passed": correct,
        "pass_rate": correct / len(results),
        "citation_document_hit_rate": sum(retrieval) / len(retrieval)
        if retrieval
        else None,
        "gate_passed": correct == len(results) and audit["valid"],
        "audit_valid": audit["valid"],
        "cases": results,
    }
