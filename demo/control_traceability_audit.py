#!/usr/bin/env python3
"""Audit traceability from release controls to evidence, source, policy, and tests."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
DEFAULT_ALLOWED_STATUSES = [PASS, "generated"]
CHECK_NAME_RE = re.compile(r'"name":\s*"([^"]+)"')


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def extract_release_checks(path: Path) -> set[str]:
    return set(CHECK_NAME_RE.findall(path.read_text(encoding="utf-8")))


def existing_nonempty(repo_root: Path, relative_path: str) -> bool:
    path = repo_root / relative_path
    return path.is_file() and path.stat().st_size > 0


def json_status_gap(repo_root: Path, relative_path: str, allowed_statuses: list[str]) -> dict[str, Any] | None:
    if not relative_path.endswith(".json"):
        return None
    path = repo_root / relative_path
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": relative_path, "reason": f"invalid_json: {exc}"}
    if isinstance(data, dict) and "status" in data and data.get("status") not in allowed_statuses:
        return {"path": relative_path, "reason": "status_not_allowed", "status": data.get("status")}
    return None


def control_names(policy: dict[str, Any]) -> list[str]:
    return [str(item["name"]) for item in policy.get("controls", [])]


def duplicate_names(names: list[str]) -> list[str]:
    return sorted({name for name in names if names.count(name) > 1})


def evaluate_controls(repo_root: Path, policy: dict[str, Any], release_checks: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    controls = list(policy.get("controls", []))
    names = control_names(policy)
    duplicates = duplicate_names(names)
    release_gaps = []
    depth_gaps = []
    evidence_gaps = []
    source_gaps = []
    policy_gaps = []
    test_gaps = []
    evidence_file_count = 0
    source_input_count = 0
    policy_input_count = 0
    test_file_count = 0

    for control in controls:
        name = str(control.get("name", ""))
        release_check = str(control.get("release_readiness_check", ""))
        evidence_paths = [str(path) for path in control.get("evidence", [])]
        source_paths = [str(path) for path in control.get("source_inputs", [])]
        policy_paths = [str(path) for path in control.get("policy_inputs", [])]
        test_paths = [str(path) for path in control.get("tests", [])]
        allowed_statuses = list(control.get("allowed_statuses", DEFAULT_ALLOWED_STATUSES))

        missing_fields = [
            field
            for field, values in {
                "release_readiness_check": [release_check],
                "evidence": evidence_paths,
                "source_inputs": source_paths,
                "tests": test_paths,
            }.items()
            if not values or not all(values)
        ]
        if missing_fields:
            depth_gaps.append({"control": name, "missing_fields": missing_fields})

        if release_check not in release_checks:
            release_gaps.append({"control": name, "release_readiness_check": release_check})

        for relative_path in evidence_paths:
            evidence_file_count += 1
            if not existing_nonempty(repo_root, relative_path):
                evidence_gaps.append({"control": name, "path": relative_path, "reason": "missing_or_empty"})
                continue
            status_gap = json_status_gap(repo_root, relative_path, allowed_statuses)
            if status_gap:
                status_gap["control"] = name
                evidence_gaps.append(status_gap)

        for relative_path in source_paths:
            source_input_count += 1
            if not existing_nonempty(repo_root, relative_path):
                source_gaps.append({"control": name, "path": relative_path})

        for relative_path in policy_paths:
            policy_input_count += 1
            if not existing_nonempty(repo_root, relative_path):
                policy_gaps.append({"control": name, "path": relative_path})

        for relative_path in test_paths:
            test_file_count += 1
            path = repo_root / relative_path
            if not existing_nonempty(repo_root, relative_path):
                test_gaps.append({"control": name, "path": relative_path, "reason": "missing_or_empty"})
            elif "def test_" not in path.read_text(encoding="utf-8"):
                test_gaps.append({"control": name, "path": relative_path, "reason": "no_test_functions"})

    checks = [
        check(
            "control_inventory",
            not duplicates and len(controls) >= int(policy.get("minimum_control_count", 0)),
            {
                "control_count": len(controls),
                "minimum_control_count": policy.get("minimum_control_count"),
                "duplicate_controls": duplicates,
            },
        ),
        check(
            "release_gate_linkage",
            not release_gaps and len(release_checks) >= int(policy.get("minimum_release_check_count", 0)),
            {
                "release_check_count": len(release_checks),
                "minimum_release_check_count": policy.get("minimum_release_check_count"),
                "release_gaps": release_gaps,
            },
        ),
        check("traceability_depth", not depth_gaps, {"depth_gaps": depth_gaps}),
        check("evidence_files", not evidence_gaps, {"evidence_gaps": evidence_gaps}),
        check("source_inputs", not source_gaps, {"source_gaps": source_gaps}),
        check(
            "policy_inputs",
            not policy_gaps and policy_input_count >= int(policy.get("minimum_policy_input_count", 0)),
            {
                "policy_input_count": policy_input_count,
                "minimum_policy_input_count": policy.get("minimum_policy_input_count"),
                "policy_gaps": policy_gaps,
            },
        ),
        check("test_coverage", not test_gaps, {"test_gaps": test_gaps}),
    ]
    metrics = {
        "control_count": len(controls),
        "release_check_count": len(release_checks),
        "evidence_file_count": evidence_file_count,
        "source_input_count": source_input_count,
        "policy_input_count": policy_input_count,
        "test_file_count": test_file_count,
    }
    return checks, metrics


def apply_fixture(policy: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(policy)
    controls = mutated.get("controls", [])
    mutation = fixture.get("mutation")
    control_name = str(fixture.get("control", ""))
    if mutation == "remove_control":
        mutated["controls"] = [item for item in controls if item.get("name") != control_name]
    elif mutation == "set_release_check":
        for control in controls:
            if control.get("name") == control_name:
                control["release_readiness_check"] = fixture.get("value")
    elif mutation == "add_missing_evidence":
        for control in controls:
            if control.get("name") == control_name:
                control.setdefault("evidence", []).append(fixture.get("path"))
    elif mutation == "add_missing_source":
        for control in controls:
            if control.get("name") == control_name:
                control.setdefault("source_inputs", []).append(fixture.get("path"))
    elif mutation == "add_missing_policy":
        for control in controls:
            if control.get("name") == control_name:
                control.setdefault("policy_inputs", []).append(fixture.get("path"))
    elif mutation == "add_missing_test":
        for control in controls:
            if control.get("name") == control_name:
                control.setdefault("tests", []).append(fixture.get("path"))
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(repo_root: Path, policy: dict[str, Any], release_checks: set[str]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(policy, fixture)
        checks, _ = evaluate_controls(repo_root, mutated, release_checks)
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


def build_report(repo_root: Path, policy: dict[str, Any], release_readiness_source: Path) -> dict[str, Any]:
    release_path = release_readiness_source if release_readiness_source.is_absolute() else repo_root / release_readiness_source
    release_checks = extract_release_checks(release_path)
    checks, metrics = evaluate_controls(repo_root, policy, release_checks)
    fixtures = evaluate_fixtures(repo_root, policy, release_checks)
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
        "control_count": metrics["control_count"],
        "release_check_count": metrics["release_check_count"],
        "evidence_file_count": metrics["evidence_file_count"],
        "source_input_count": metrics["source_input_count"],
        "policy_input_count": metrics["policy_input_count"],
        "test_file_count": metrics["test_file_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "checks": checks,
        "controls": policy.get("controls", []),
        "fixtures": fixtures,
    }


def resolved_output_path(path: Path, default_name: str) -> Path:
    return path if path.suffix else path / default_name


def write_json(report: dict[str, Any], output: Path) -> None:
    path = resolved_output_path(output, "control-traceability-audit.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output: Path) -> None:
    path = resolved_output_path(output, "control-traceability-audit.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Control Traceability Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit proves that configured release-readiness controls trace back to",
        "committed evidence, source code, policy/config inputs, and tests.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Controls | {report['control_count']} |",
        f"| Release checks | {report['release_check_count']} |",
        f"| Evidence files | {report['evidence_file_count']} |",
        f"| Source inputs | {report['source_input_count']} |",
        f"| Policy inputs | {report['policy_input_count']} |",
        f"| Test files | {report['test_file_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Controls", "", "| Control | Release Check | Evidence Files |", "| --- | --- | ---: |"])
    for item in report["controls"]:
        lines.append(
            f"| `{item['name']}` | `{item['release_readiness_check']}` | {len(item.get('evidence', []))} |"
        )
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Expected Failed Check | Detected |", "| --- | --- | --- |"])
    for item in report["fixtures"]:
        lines.append(
            f"| `{item['name']}` | `{item['expected_failed_check']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def resolve_repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/control-traceability-policy.json")
    parser.add_argument("--release-readiness-source", default="demo/release_readiness.py")
    parser.add_argument("--output-dir", default="docs/evidence")
    parser.add_argument("--output", default="")
    parser.add_argument("--markdown-output", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    policy = load_json(resolve_repo_path(repo_root, args.policy))
    report = build_report(repo_root, policy, Path(args.release_readiness_source))
    output_dir = resolve_repo_path(repo_root, args.output_dir)
    json_output = resolve_repo_path(repo_root, args.output) if args.output else output_dir
    markdown_output = resolve_repo_path(repo_root, args.markdown_output) if args.markdown_output else output_dir
    write_json(report, json_output)
    write_markdown(report, markdown_output)
    print(f"wrote {resolved_output_path(json_output, 'control-traceability-audit.json')}")
    print(f"wrote {resolved_output_path(markdown_output, 'control-traceability-audit.md')}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
