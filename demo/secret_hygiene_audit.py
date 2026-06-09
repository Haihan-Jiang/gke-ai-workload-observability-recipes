#!/usr/bin/env python3
"""Audit committed repository files for high-confidence secret leaks."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def is_excluded(path: Path, excluded_dirs: set[str]) -> bool:
    return any(part in excluded_dirs for part in path.parts)


def collect_scan_paths(repo_root: Path, policy: dict[str, Any]) -> list[str]:
    excluded_dirs = set(policy.get("excluded_dirs", []))
    max_file_bytes = int(policy.get("max_file_bytes", 0))
    paths: list[str] = []
    for raw_root in policy.get("scan_roots", []):
        root = repo_root / str(raw_root)
        if root.is_file():
            if max_file_bytes and root.stat().st_size > max_file_bytes:
                continue
            paths.append(str(root.relative_to(repo_root)))
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or is_excluded(path.relative_to(repo_root), excluded_dirs):
                continue
            if max_file_bytes and path.stat().st_size > max_file_bytes:
                continue
            paths.append(str(path.relative_to(repo_root)))
    return sorted(set(paths))


def read_files(repo_root: Path, paths: list[str]) -> tuple[dict[str, str], list[dict[str, str]]]:
    files = {}
    skipped = []
    for path in paths:
        try:
            files[path] = (repo_root / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append({"path": path, "reason": "not_utf8"})
        except OSError as exc:
            skipped.append({"path": path, "reason": str(exc)})
    return files, skipped


def compile_patterns(policy: dict[str, Any]) -> list[dict[str, Any]]:
    patterns = []
    for item in policy.get("deny_patterns", []):
        patterns.append(
            {
                "name": str(item["name"]),
                "severity": str(item.get("severity", "critical")),
                "regex": str(item["regex"]),
                "compiled": re.compile(str(item["regex"])),
            }
        )
    return patterns


def redact(value: str) -> str:
    if len(value) <= 8:
        return "<redacted>"
    return f"{value[:4]}...{value[-4:]}"


def scan_files(files: dict[str, str], patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for path, text in files.items():
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in patterns:
                for match in pattern["compiled"].finditer(line):
                    findings.append(
                        {
                            "path": path,
                            "line": line_no,
                            "pattern": pattern["name"],
                            "severity": pattern["severity"],
                            "redacted": redact(match.group(0)),
                        }
                    )
    return findings


def synthetic_secret(pattern_name: str) -> str:
    values = {
        "private_key_header": "-----BEGIN " + "PRIVATE KEY-----",
        "aws_access_key_id": "AKIA" + "IOSFODNN7" + "EXAMPLE",
        "google_api_key": "AIza" + "SyD0exAMPL3" + "exAMPL3exAMPL3exAMPL3exA",
        "github_token": "ghp_" + "0123456789abcdef" + "0123456789abcdef" + "0123456789",
        "slack_webhook": "https://hooks.slack.com/services/"
        + "T00000000/"
        + "B00000000/"
        + "0123456789abcdef01234567",
        "slack_token": "xoxb-" + "0123456789abcdef012345",
    }
    if pattern_name not in values:
        raise ValueError(f"unsupported synthetic secret pattern: {pattern_name}")
    return values[pattern_name]


def evaluate_files(files: dict[str, str], skipped: list[dict[str, str]], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    patterns = compile_patterns(policy)
    findings = scan_files(files, patterns)
    evidence_files = [path for path in files if path.startswith("docs/evidence/")]
    pattern_gaps = [
        item
        for item in policy.get("deny_patterns", [])
        if not item.get("name") or not item.get("regex") or not item.get("severity")
    ]
    checks = [
        check(
            "scanned_file_inventory",
            len(files) >= int(policy.get("minimum_scanned_files", 0)) and not skipped,
            {
                "scanned_file_count": len(files),
                "minimum_scanned_files": policy.get("minimum_scanned_files"),
                "skipped_files": skipped,
            },
        ),
        check(
            "generated_evidence_scan",
            len(evidence_files) >= int(policy.get("minimum_evidence_files", 0)),
            {
                "evidence_file_count": len(evidence_files),
                "minimum_evidence_files": policy.get("minimum_evidence_files"),
            },
        ),
        check(
            "deny_pattern_catalog",
            len(patterns) >= int(policy.get("minimum_pattern_count", 0)) and not pattern_gaps,
            {
                "pattern_count": len(patterns),
                "minimum_pattern_count": policy.get("minimum_pattern_count"),
                "pattern_gaps": pattern_gaps,
            },
        ),
        check("secret_pattern_scan", not findings, {"finding_count": len(findings), "findings": findings}),
    ]
    metrics = {
        "scanned_file_count": len(files),
        "evidence_file_count": len(evidence_files),
        "pattern_count": len(patterns),
        "finding_count": len(findings),
        "skipped_file_count": len(skipped),
    }
    return checks, metrics


def apply_fixture(files: dict[str, str], fixture: dict[str, Any]) -> dict[str, str]:
    mutated = copy.deepcopy(files)
    path = str(fixture.get("path", ""))
    mutation = fixture.get("mutation")
    if mutation == "append_synthetic_secret":
        mutated[path] = (mutated.get(path) or "") + "\n" + synthetic_secret(str(fixture.get("pattern_name"))) + "\n"
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(files: dict[str, str], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        checks, _ = evaluate_files(apply_fixture(files, fixture), [], policy)
        failed_checks = [item["name"] for item in checks if not item["ok"]]
        expected = str(fixture.get("expected_failed_check"))
        results.append(
            {
                "name": fixture.get("name"),
                "mutation": fixture.get("mutation"),
                "pattern_name": fixture.get("pattern_name"),
                "expected_failed_check": expected,
                "failed_checks": failed_checks,
                "detected": expected in failed_checks,
            }
        )
    return results


def build_report(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    paths = collect_scan_paths(repo_root, policy)
    files, skipped = read_files(repo_root, paths)
    checks, metrics = evaluate_files(files, skipped, policy)
    fixtures = evaluate_fixtures(files, policy)
    detected_fixture_count = sum(1 for item in fixtures if item["detected"])
    checks.append(
        check(
            "negative_fixture_coverage",
            detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
            {
                "detected_fixture_count": detected_fixture_count,
                "minimum_detected_fixtures": policy.get("minimum_detected_fixtures"),
                "fixtures": fixtures,
            },
        )
    )
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "failed_count": failed_count,
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        **metrics,
        "checks": checks,
        "fixtures": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "secret-hygiene-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Secret Hygiene Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit scans committed source, manifests, documentation, and",
        "generated evidence for high-confidence secret formats before release",
        "readiness is reported.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Scanned files | {report['scanned_file_count']} |",
        f"| Generated evidence files scanned | {report['evidence_file_count']} |",
        f"| Deny patterns | {report['pattern_count']} |",
        f"| Findings | {report['finding_count']} |",
        f"| Skipped files | {report['skipped_file_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Pattern | Expected Failed Check | Detected |", "| --- | --- | --- | --- |"])
    for item in report["fixtures"]:
        lines.append(
            f"| `{item['name']}` | `{item['pattern_name']}` | `{item['expected_failed_check']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    (output_dir / "secret-hygiene-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/secret-hygiene-policy.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'secret-hygiene-audit.json'}")
    print(f"wrote {output_dir / 'secret-hygiene-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
