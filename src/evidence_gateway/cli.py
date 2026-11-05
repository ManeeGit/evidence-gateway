"""Local development CLI. All shipped commands work without a model API key."""

import argparse
import json
import os
from pathlib import Path
import sys
from wsgiref.simple_server import WSGIRequestHandler, make_server
from .api import Application
from .engine import Engine
from .evaluation import evaluate
from .models import Document
from .store import Store


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        # Access logs are disabled because URLs can contain user-supplied data.
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser(
        "ingest", help="Atomically ingest trusted local JSON documents"
    )
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--db", default="var/evidence.db")
    evaluate_cmd = sub.add_parser("evaluate", help="Run gold-label release gates")
    evaluate_cmd.add_argument("--documents", default="examples/documents.json")
    evaluate_cmd.add_argument("--cases", default="examples/evaluation.json")
    evaluate_cmd.add_argument("--output", type=Path)
    demo = sub.add_parser("demo", help="Run an offline synthetic-data demonstration")
    demo.add_argument("--db", default="var/demo.db")
    demo.add_argument("--documents", default="examples/documents.json")
    serve = sub.add_parser(
        "serve", help="Loopback-only development server; not a production server"
    )
    serve.add_argument("--db", default="var/evidence.db")
    serve.add_argument("--port", default=8080, type=int)
    audit = sub.add_parser("verify-audit", help="Verify the local hash chain")
    audit.add_argument("--db", default="var/evidence.db")
    args = parser.parse_args(argv)
    if args.command == "evaluate":
        result = evaluate(args.documents, args.cases)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0 if result["gate_passed"] else 1
    store = Store(args.db)
    if args.command == "ingest":
        documents = [Document(**row) for row in json.loads(args.file.read_text())]
        print(json.dumps(store.ingest(documents)))
    elif args.command == "verify-audit":
        result = store.verify_audit()
        print(json.dumps(result))
        return 0 if result["valid"] else 1
    elif args.command == "demo":
        store.ingest(
            [Document(**row) for row in json.loads(Path(args.documents).read_text())]
        )
        engine = Engine(store, audit_key=b"public-synthetic-demo-key-32-bytes")
        print(
            json.dumps(
                engine.query(
                    "acme", "How long are backup snapshots retained?", "demo-retention"
                ),
                indent=2,
            )
        )
    elif args.command == "serve":
        raw_key = os.environ.get("EVIDENCE_AUDIT_KEY", "")
        raw_credentials = os.environ.get("EVIDENCE_CREDENTIALS", "")
        if not raw_key or not raw_credentials:
            parser.error(
                "EVIDENCE_AUDIT_KEY and EVIDENCE_CREDENTIALS must be set; see README"
            )
        try:
            app = Application(
                Engine(store, audit_key=raw_key.encode()), json.loads(raw_credentials)
            )
        except (ValueError, TypeError, AttributeError) as exc:
            parser.error(f"Invalid credential configuration: {type(exc).__name__}")
        print(
            f"Development server at http://127.0.0.1:{args.port}; use only on a trusted machine."
        )
        with make_server(
            "127.0.0.1", args.port, app, handler_class=QuietHandler
        ) as server:
            server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
