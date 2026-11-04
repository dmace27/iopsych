"""Run both Gitleaks scopes; publish counts only, never scanner payloads."""

import json
import os
import subprocess
import tempfile
from pathlib import Path


def main():
    report_dir = Path("security-reports")
    report_dir.mkdir(exist_ok=True)
    scanner = os.environ.get("GITLEAKS_BIN", "gitleaks")
    results = {}
    # Raw diagnostics and reports may contain credentials even with --redact.
    # Keep them private and ephemeral; never print or upload their contents.
    with tempfile.TemporaryDirectory(prefix="iopsych-secret-scan-") as temp:
        for scope, command in (("source", "dir"), ("history", "git")):
            report = Path(temp) / f"{scope}.json"
            try:
                process = subprocess.run(
                    [
                        scanner,
                        command,
                        ".",
                        *(["--log-opts=--all"] if command == "git" else []),
                        "--config",
                        ".gitleaks.toml",
                        "--redact=100",
                        "--exit-code",
                        "1",
                        "--report-format",
                        "json",
                        "--report-path",
                        str(report),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=480,
                    check=False,
                )
                findings = json.loads(report.read_text())
                if not isinstance(findings, list):
                    raise TypeError("Invalid report")
                count = len(findings)
                status = (
                    "clean"
                    if process.returncode == 0 and count == 0
                    else "findings"
                    if process.returncode == 1 and count > 0
                    else "error"
                )
                results[scope] = {
                    "status": status,
                    "findings": count,
                    "exit_code": process.returncode,
                }
            except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
                results[scope] = {
                    "status": "error",
                    "findings": None,
                    "exit_code": None,
                }
            print(f"Gitleaks {scope}: {json.dumps(results[scope], sort_keys=True)}")
    summary = {"scanner": "gitleaks", "version": "8.24.3", "scopes": results}
    (report_dir / "secret-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    return 0 if all(r["status"] == "clean" for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
