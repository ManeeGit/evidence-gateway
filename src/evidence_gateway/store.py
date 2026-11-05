"""SQLite transaction boundary for revisions, rate budgets, retries and audit events."""

from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from .models import Conflict, Document, RateLimited, identifier


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def revision(documents: list[Document]) -> str:
    payload = [asdict(doc) for doc in sorted(documents, key=lambda doc: doc.id)]
    return hashlib.sha256(canonical(payload).encode()).hexdigest()


class Store:
    def __init__(self, path: str | Path, *, clock=time.time):
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError(
                "Use a file-backed SQLite database; connections are per operation."
            )
        self.clock = clock
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError("Unsupported database schema version")
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    tenant TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL,
                    text TEXT NOT NULL, version INTEGER NOT NULL,
                    PRIMARY KEY (tenant,id));
                CREATE TABLE IF NOT EXISTS requests (
                    tenant TEXT NOT NULL, request_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, revision TEXT NOT NULL,
                    response TEXT NOT NULL, created REAL NOT NULL,
                    PRIMARY KEY (tenant,request_id));
                CREATE TABLE IF NOT EXISTS budgets (
                    tenant TEXT NOT NULL, window INTEGER NOT NULL, used INTEGER NOT NULL,
                    PRIMARY KEY (tenant,window));
                CREATE TABLE IF NOT EXISTS audit (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, hash TEXT NOT NULL);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def ingest(self, documents: list[Document]) -> dict:
        if not documents or len(documents) > 10_000:
            raise ValueError("Ingest requires 1-10000 documents")
        keys = [(doc.tenant, doc.id) for doc in documents]
        if len(keys) != len(set(keys)):
            raise Conflict("Duplicate document identity in batch")
        written = unchanged = 0
        with self.transaction() as db:
            for doc in documents:
                row = db.execute(
                    "SELECT * FROM documents WHERE tenant=? AND id=?",
                    (doc.tenant, doc.id),
                ).fetchone()
                if row:
                    current = Document(**dict(row))
                    if doc == current:
                        unchanged += 1
                        continue
                    if doc.version <= current.version:
                        raise Conflict(
                            "Changed documents require a strictly increasing version"
                        )
                db.execute(
                    """INSERT INTO documents VALUES (?,?,?,?,?)
                    ON CONFLICT(tenant,id) DO UPDATE SET title=excluded.title,
                    text=excluded.text, version=excluded.version""",
                    (doc.tenant, doc.id, doc.title, doc.text, doc.version),
                )
                written += 1
        return {"written": written, "unchanged": unchanged}

    @staticmethod
    def _snapshot(db, tenant):
        rows = db.execute(
            "SELECT * FROM documents WHERE tenant=? ORDER BY id", (tenant,)
        ).fetchall()
        docs = [Document(**dict(row)) for row in rows]
        return docs, revision(docs)

    def snapshot(self, tenant: str):
        identifier(tenant)
        with self.connect() as db:
            return self._snapshot(db, tenant)

    def delete(self, tenant: str, document_id: str) -> bool:
        identifier(tenant)
        identifier(document_id)
        with self.transaction() as db:
            return (
                db.execute(
                    "DELETE FROM documents WHERE tenant=? AND id=?",
                    (tenant, document_id),
                ).rowcount
                == 1
            )

    def begin_request(
        self,
        tenant,
        request_id,
        fingerprint,
        index_revision,
        *,
        per_minute=60,
        ttl_seconds=86400,
    ):
        now = self.clock()
        window = int(now // 60)
        with self.transaction() as db:
            _, current_revision = self._snapshot(db, tenant)
            if current_revision != index_revision:
                raise Conflict(
                    "Index changed before request admission; retry the request"
                )
            db.execute("DELETE FROM requests WHERE created < ?", (now - ttl_seconds,))
            row = db.execute(
                "SELECT * FROM requests WHERE tenant=? AND request_id=?",
                (tenant, request_id),
            ).fetchone()
            if row:
                if (
                    row["fingerprint"] != fingerprint
                    or row["revision"] != index_revision
                ):
                    raise Conflict(
                        "Request ID was used for different input or an older index revision"
                    )
                return json.loads(row["response"])
            db.execute("DELETE FROM budgets WHERE window < ?", (window - 1,))
            row = db.execute(
                "SELECT used FROM budgets WHERE tenant=? AND window=?", (tenant, window)
            ).fetchone()
            if row and row["used"] >= per_minute:
                raise RateLimited(
                    "Tenant request budget exhausted; retry in the next minute"
                )
            db.execute(
                """INSERT INTO budgets VALUES (?,?,1)
                ON CONFLICT(tenant,window) DO UPDATE SET used=used+1""",
                (tenant, window),
            )
        return None

    def finish_request(self, tenant, request_id, fingerprint, index_revision, response):
        with self.transaction() as db:
            _, current_revision = self._snapshot(db, tenant)
            if current_revision != index_revision:
                raise Conflict("Index changed during generation; retry the request")
            row = db.execute(
                "SELECT * FROM requests WHERE tenant=? AND request_id=?",
                (tenant, request_id),
            ).fetchone()
            if row:
                if (
                    row["fingerprint"] != fingerprint
                    or row["revision"] != index_revision
                ):
                    raise Conflict("Concurrent request ID conflict")
                return json.loads(row["response"])
            now = self.clock()
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,?,?,?)",
                (
                    tenant,
                    request_id,
                    fingerprint,
                    index_revision,
                    canonical(response),
                    now,
                ),
            )
            event = canonical(
                {
                    "tenant": tenant,
                    "request_id": request_id,
                    "fingerprint": fingerprint,
                    "revision": index_revision,
                    "status": response["status"],
                    "reason": response["reason"],
                    "provider": response["provider"],
                    "created": now,
                    "documents": sorted(
                        {c["document_id"] for c in response["citations"]}
                    ),
                }
            )
            previous = db.execute(
                "SELECT hash FROM audit ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            previous_hash = previous["hash"] if previous else "0" * 64
            digest = hashlib.sha256((previous_hash + event).encode()).hexdigest()
            db.execute(
                "INSERT INTO audit(event,previous_hash,hash) VALUES (?,?,?)",
                (event, previous_hash, digest),
            )
        return response

    def verify_audit(self) -> dict:
        previous_hash = "0" * 64
        count = 0
        with self.connect() as db:
            for row in db.execute("SELECT * FROM audit ORDER BY seq"):
                expected = hashlib.sha256(
                    (previous_hash + row["event"]).encode()
                ).hexdigest()
                if row["previous_hash"] != previous_hash or row["hash"] != expected:
                    return {
                        "valid": False,
                        "events": count,
                        "first_invalid_sequence": row["seq"],
                    }
                previous_hash = row["hash"]
                count += 1
        return {"valid": True, "events": count, "head": previous_hash}
