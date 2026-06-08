#!/usr/bin/env python3
"""Audit repository governance documents for contributor-ready releases."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_files(repo_root: Path, paths: list[str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for path in paths:
        absolute = repo_root / path
        result[path] = absolute.read_text(encoding="utf-8") if absolute.is_file() else None
    return result


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def missing_terms(text: str | None, terms: list[str]) -> list[str]:
    if text is None:
        return terms
    return [term for term in terms if term not in text]


def codeowner_entries(text: str | None) -> list[dict[str, str]]:
    entries = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        entries.append({"pattern": parts[0], "owners": " ".join(parts[1:])})
    return entries


def evaluate_documents(files: dict[str, str | None], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_files = list(policy["required_files"])
    missing_files = [path for path in required_files if files.get(path) is None]
    contributing_missing = missing_terms(
        files.get("CONTRIBUTING.md"),
        list(policy.get("required_contributing_terms", [])),
    )
    security_missing = missing_terms(
        files.get("SECURITY.md"),
        list(policy.get("required_security_terms", [])),
    )
    release_missing = missing_terms(
        files.get("docs/release-process.md"),
        list(policy.get("required_release_terms", [])),
    )

    codeowners_text = files.get(".github/CODEOWNERS")
    entries = codeowner_entries(codeowners_text)
    owner = policy.get("codeowners", {}).get("required_owner")
    required_patterns = list(policy.get("codeowners", {}).get("required_patterns", []))
    patterns_by_name = {entry["pattern"]: entry for entry in entries}
    missing_patterns = [
        pattern
        for pattern in required_patterns
        if pattern not in patterns_by_name or owner not in patterns_by_name[pattern]["owners"]
    ]
    owner_count = sum(1 for entry in entries if owner in entry["owners"])
    checks = [
        check(
            "required_files",
            not missing_files,
            {"missing_files": missing_files, "required_files": required_files},
        ),
        check(
            "contribution_workflow",
            not contributing_missing,
            {"missing_terms": contributing_missing},
        ),
        check(
            "security_reporting",
            not security_missing,
            {"missing_terms": security_missing},
        ),
        check(
            "release_process",
            not release_missing,
            {"missing_terms": release_missing},
        ),
        check(
            "codeowners_coverage",
            not missing_patterns and owner_count >= len(required_patterns),
            {
                "required_owner": owner,
                "missing_patterns": missing_patterns,
                "owner_count": owner_count,
                "entries": entries,
            },
        ),
    ]
    metrics = {
        "required_file_count": len(required_files),
        "present_file_count": len(required_files) - len(missing_files),
        "codeowner_pattern_count": len(entries),
        "owned_pattern_count": owner_count,
    }
    return checks, metrics


def apply_fixture(files: dict[str, str | None], fixture: dict[str, Any]) -> dict[str, str | None]:
    mutated = copy.deepcopy(files)
    path = str(fixture.get("path", ""))
    mutation = fixture.get("mutation")
    if mutation == "remove_file":
        mutated[path] = None
    elif mutation == "remove_text":
        text = mutated.get(path)
        if text is not None:
            mutated[path] = text.replace(str(fixture.get("text", "")), "")
    elif mutation == "replace_text":
        text = mutated.get(path)
        if text is not None:
            mutated[path] = text.replace(str(fixture.get("from", "")), str(fixture.get("to", "")))
    elif mutation == "remove_line_containing":
        text = mutated.get(path)
        if text is not None:
            needle = str(fixture.get("text", ""))
            lines = [line for line in text.splitlines() if needle not in line]
            mutated[path] = "\n".join(lines) + "\n"
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(files: dict[str, str | None], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(files, fixture)
        checks, _ = evaluate_documents(mutated, policy)
        checks_by_name = {item["name"]: item for item in checks}
        expected = str(fixture.get("expected_failed_check"))
        detected = checks_by_name.get(expected, {}).get("ok") is False
        results.append(
            {
                "name": fixture.get("name"),
                "mutation": fixture.get("mutation"),
                "expected_failed_check": expected,
                "detected": detected,
            }
        )
    return results


def build_report(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    files = read_files(repo_root, list(policy["required_files"]))
    checks, metrics = evaluate_documents(files, policy)
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
        "required_file_count": metrics["required_file_count"],
        "present_file_count": metrics["present_file_count"],
        "codeowner_pattern_count": metrics["codeowner_pattern_count"],
        "owned_pattern_count": metrics["owned_pattern_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "checks": checks,
        "fixtures": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "repository-governance-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Repository Governance Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks whether the public repository has enough governance",
        "surface for contributors and reviewers to understand validation,",
        "security reporting, ownership, release evidence, and project",
        "boundaries.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Required files | {report['required_file_count']} |",
        f"| Present files | {report['present_file_count']} |",
        f"| CODEOWNERS patterns | {report['codeowner_pattern_count']} |",
        f"| Owned patterns | {report['owned_pattern_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Expected Failed Check | Detected |", "| --- | --- | --- |"])
    for item in report["fixtures"]:
        lines.append(
            f"| `{item['name']}` | `{item['expected_failed_check']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    (output_dir / "repository-governance-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/repository-governance-policy.json")
    parser.add_argument("--output-dir", default="out/repository-governance-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'repository-governance-audit.json'}")
    print(f"wrote {output_dir / 'repository-governance-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
