import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_gateway.api import from_environment
from evidence_gateway.cli import main

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "cli.db")

    def run_command(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(args)
        return code, json.loads(output.getvalue())

    def test_ingest_and_verify(self):
        code, result = self.run_command(
            ["ingest", str(ROOT / "examples/documents.json"), "--db", self.db]
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["written"], 8)
        code, audit = self.run_command(["verify-audit", "--db", self.db])
        self.assertTrue(audit["valid"])
        self.assertEqual(code, 0)

    def test_demo(self):
        code, result = self.run_command(
            [
                "demo",
                "--db",
                self.db,
                "--documents",
                str(ROOT / "examples/documents.json"),
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "answered")

    def test_evaluate_writes_report(self):
        report = Path(self.tmp.name) / "nested/report.json"
        code, result = self.run_command(
            [
                "evaluate",
                "--documents",
                str(ROOT / "examples/documents.json"),
                "--cases",
                str(ROOT / "examples/evaluation.json"),
                "--output",
                str(report),
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(report.read_text()), result)

    def test_evaluation_failure_returns_nonzero(self):
        cases = Path(self.tmp.name) / "bad-cases.json"
        cases.write_text(
            json.dumps(
                [
                    {
                        "id": "bad-gold",
                        "tenant": "acme",
                        "question": "backup",
                        "status": "blocked",
                    }
                ]
            )
        )
        code, result = self.run_command(
            [
                "evaluate",
                "--documents",
                str(ROOT / "examples/documents.json"),
                "--cases",
                str(cases),
            ]
        )
        self.assertEqual(code, 1)
        self.assertFalse(result["gate_passed"])

    def test_server_requires_credentials(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as result:
                main(["serve", "--db", self.db])
        self.assertEqual(result.exception.code, 2)

    def test_production_factory(self):
        environment = {
            "EVIDENCE_DB": self.db,
            "EVIDENCE_AUDIT_KEY": "x" * 32,
            "EVIDENCE_CREDENTIALS": json.dumps({"y" * 32: "alpha"}),
        }
        with patch.dict(os.environ, environment, clear=True):
            app = from_environment()
        self.assertEqual(app.credentials, {"y" * 32: "alpha"})

    def test_production_factory_rejects_missing_credentials(self):
        with patch.dict(os.environ, {"EVIDENCE_DB": self.db}, clear=True):
            with self.assertRaises(ValueError):
                from_environment()

    def test_production_factory_rejects_array(self):
        with patch.dict(os.environ, {"EVIDENCE_CREDENTIALS": "[]"}, clear=True):
            with self.assertRaises(ValueError):
                from_environment()
