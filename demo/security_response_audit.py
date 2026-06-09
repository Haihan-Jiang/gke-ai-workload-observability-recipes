#!/usr/bin/env python3
"""Audit vulnerability response SLAs and disclosure handling."""

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
    return {
        path: (repo_root / path).read_text(encoding="utf-8") if (repo_root / path).is_file() else None
        for path in paths
    }


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def missing_terms(text: str | None, terms: list[str]) -> list[str]:
    if text is None:
        return terms
    return [term for term in terms if term not in text]


def tier_by_name(policy: dict[str, Any], name: str) -> dict[str, Any] | None:
    for tier in policy.get("severity_tiers", []):
        if str(tier.get("name", "")).lower() == name.lower():
            return tier
    return None


def duplicate_names(names: list[str]) -> list[str]:
    return sorted({name for name in names if names.count(name) > 1})


def severity_gaps(security_text: str | None, policy: dict[str, Any]) -> list[dict[str, Any]]:
    tiers = list(policy.get("severity_tiers", []))
    names = [str(tier.get("name", "")) for tier in tiers]
    labels = [str(tier.get("label", "")) for tier in tiers]
    gaps: list[dict[str, Any]] = []
    if len(tiers) < int(policy.get("minimum_severity_tiers", 0)):
        gaps.append(
            {
                "reason": "too_few_tiers",
                "tier_count": len(tiers),
                "minimum": policy.get("minimum_severity_tiers"),
            }
        )
    duplicates = duplicate_names(names)
    if duplicates:
        gaps.append({"reason": "duplicate_tiers", "tiers": duplicates})

    critical = tier_by_name(policy, "critical")
    if critical is None:
        gaps.append({"reason": "missing_critical"})
    elif int(critical.get("triage_hours", 999999)) > int(policy.get("max_critical_triage_hours", 24)):
        gaps.append(
            {
                "reason": "critical_triage_too_slow",
                "triage_hours": critical.get("triage_hours"),
                "maximum": policy.get("max_critical_triage_hours"),
            }
        )

    text = security_text or ""
    for label in labels:
        if label and label not in text:
            gaps.append({"reason": "missing_documented_label", "label": label})
    for tier in tiers:
        hours = str(tier.get("triage_hours", ""))
        label = str(tier.get("label", ""))
        if hours and f"triage within {hours} hours" not in text:
            gaps.append({"reason": "missing_documented_sla", "label": label, "triage_hours": hours})
        target = str(tier.get("target_action", ""))
        if target and target not in text:
            gaps.append({"reason": "missing_target_action", "label": label, "target_action": target})
    return gaps


def evaluate_documents(files: dict[str, str | None], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_files = list(policy["required_files"])
    missing_files = [path for path in required_files if files.get(path) is None]
    security_text = files.get("SECURITY.md")
    release_text = files.get("docs/release-process.md")
    contributing_text = files.get("CONTRIBUTING.md")
    private_missing = missing_terms(security_text, list(policy.get("required_security_terms", [])))
    fix_missing = missing_terms(security_text, list(policy.get("required_fix_terms", [])))
    disclosure_missing = missing_terms(security_text, list(policy.get("required_disclosure_terms", [])))
    release_missing = missing_terms(release_text, list(policy.get("required_release_terms", [])))
    contribution_missing = missing_terms(contributing_text, list(policy.get("required_contributing_terms", [])))
    severity_issues = severity_gaps(security_text, policy)
    critical = tier_by_name(policy, "critical") or {}
    checks = [
        check("required_files", not missing_files, {"missing_files": missing_files, "required_files": required_files}),
        check("private_reporting", not private_missing, {"missing_terms": private_missing}),
        check(
            "severity_sla",
            not severity_issues,
            {
                "severity_gaps": severity_issues,
                "tier_count": len(policy.get("severity_tiers", [])),
                "critical_triage_hours": critical.get("triage_hours"),
            },
        ),
        check("fix_and_evidence", not fix_missing, {"missing_terms": fix_missing}),
        check("disclosure_flow", not disclosure_missing, {"missing_terms": disclosure_missing}),
        check("release_process", not release_missing, {"missing_terms": release_missing}),
        check("contribution_boundary", not contribution_missing, {"missing_terms": contribution_missing}),
    ]
    metrics = {
        "required_file_count": len(required_files),
        "present_file_count": len(required_files) - len(missing_files),
        "severity_tier_count": len(policy.get("severity_tiers", [])),
        "critical_triage_hours": critical.get("triage_hours"),
    }
    return checks, metrics


def apply_fixture(
    files: dict[str, str | None],
    policy: dict[str, Any],
    fixture: dict[str, Any],
) -> tuple[dict[str, str | None], dict[str, Any]]:
    mutated_files = copy.deepcopy(files)
    mutated_policy = copy.deepcopy(policy)
    mutation = fixture.get("mutation")
    if mutation == "remove_text":
        path = str(fixture.get("path", ""))
        text = mutated_files.get(path)
        if text is not None:
            mutated_files[path] = text.replace(str(fixture.get("text", "")), "")
    elif mutation == "replace_text":
        path = str(fixture.get("path", ""))
        text = mutated_files.get(path)
        if text is not None:
            mutated_files[path] = text.replace(str(fixture.get("from", "")), str(fixture.get("to", "")))
    elif mutation == "remove_tier":
        target = str(fixture.get("tier", ""))
        mutated_policy["severity_tiers"] = [
            tier for tier in mutated_policy.get("severity_tiers", []) if tier.get("name") != target
        ]
    elif mutation == "set_tier_field":
        target = str(fixture.get("tier", ""))
        field = str(fixture.get("field", ""))
        for tier in mutated_policy.get("severity_tiers", []):
            if tier.get("name") == target:
                tier[field] = fixture.get("value")
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated_files, mutated_policy


def evaluate_fixtures(files: dict[str, str | None], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_files, mutated_policy = apply_fixture(files, policy, fixture)
        checks, _ = evaluate_documents(mutated_files, mutated_policy)
        failed_checks = [item["name"] for item in checks if not item["ok"]]
        expected = str(fixture.get("expected_failed_check"))
        results.append(
            {
                "name": fixture.get("name"),
                "mutation": fixture.get("mutation"),
                "expected_failed_check": expected,
                "failed_checks": failed_checks,
                "detected": expected in failed_checks,
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
        "severity_tier_count": metrics["severity_tier_count"],
        "critical_triage_hours": metrics["critical_triage_hours"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "checks": checks,
        "fixtures": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "security-response-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Security Response Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks the repository's vulnerability reporting channel,",
        "severity-tier SLA table, security-fix evidence expectations, and",
        "coordinated disclosure/update flow before release readiness can pass.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Required files | {report['required_file_count']} |",
        f"| Present files | {report['present_file_count']} |",
        f"| Severity tiers | {report['severity_tier_count']} |",
        f"| Critical triage hours | {report['critical_triage_hours']} |",
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
    (output_dir / "security-response-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/security-response-policy.json")
    parser.add_argument("--output-dir", default="out/security-response-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'security-response-audit.json'}")
    print(f"wrote {output_dir / 'security-response-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
