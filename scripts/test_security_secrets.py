"""Failure and disclosure regressions for the isolated security scanner wrapper."""

import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "security_secrets", Path(__file__).with_name("security-secrets.py")
)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class SecretScannerTests(unittest.TestCase):
    def run_case(self, outcomes):
        calls = []

        def run(command, **kwargs):
            self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
            self.assertIn("--redact=100", command)
            calls.append(command[1])
            code, report = outcomes[len(calls) - 1]
            if isinstance(code, Exception):
                raise code
            if report is not None:
                Path(command[-1]).write_text(report)
            return subprocess.CompletedProcess(command, code)

        with tempfile.TemporaryDirectory() as temp, contextlib.chdir(temp):
            output = io.StringIO()
            with (
                patch.object(scanner.subprocess, "run", side_effect=run),
                contextlib.redirect_stdout(output),
            ):
                result = scanner.main()
            summary = Path("security-reports/secret-summary.json").read_text()
            self.assertNotIn("sensitive-test-marker", output.getvalue() + summary)
            self.assertEqual(calls, ["dir", "git"])
            return result, json.loads(summary)["scopes"]

    def test_both_clean(self):
        result, scopes = self.run_case([(0, "[]"), (0, "[]")])
        self.assertEqual(result, 0)
        self.assertEqual(scopes["history"]["status"], "clean")

    def test_source_finding_does_not_suppress_history_or_expose_payload(self):
        result, scopes = self.run_case(
            [(1, '[{"Secret":"sensitive-test-marker"}]'), (0, "[]")]
        )
        self.assertEqual(result, 1)
        self.assertEqual(scopes["source"]["findings"], 1)
        self.assertEqual(scopes["history"]["status"], "clean")

    def test_fail_closed_and_continue_after_errors(self):
        for outcome in [
            (2, "[]"),
            (0, None),
            (0, "not json"),
            (0, "{}"),
            (0, '[{"Secret":"sensitive-test-marker"}]'),
            (1, "[]"),
            (FileNotFoundError(), None),
            (subprocess.TimeoutExpired("gitleaks", 480), None),
        ]:
            with self.subTest(outcome=outcome):
                result, scopes = self.run_case([outcome, (0, "[]")])
                self.assertEqual(result, 1)
                self.assertEqual(scopes["source"]["status"], "error")
                self.assertEqual(scopes["history"]["status"], "clean")

    def test_history_finding_fails_gate(self):
        result, _ = self.run_case([(0, "[]"), (1, "[{}]")])
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
