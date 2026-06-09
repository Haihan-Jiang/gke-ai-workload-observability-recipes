#!/usr/bin/env python3
"""Audit machine-readable schema contracts for generated evidence JSON."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
DEFAULT_ALLOWED_STATUSES = [PASS, FAIL]
VALID_CHECK_STATUSES = {PASS, FAIL}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_artifacts(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for artifact in policy.get("artifacts", []):
        path = str(artifact["path"])
        absolute = repo_root / path
        artifacts[path] = load_json(absolute) if absolute.is_file() else None
    return artifacts


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def artifact_contracts(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["path"]): item for item in policy.get("artifacts", [])}


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check_result_valid(item: dict[str, Any]) -> bool:
    has_ok = "ok" in item and isinstance(item.get("ok"), bool)
    has_status = "status" in item and item.get("status") in VALID_CHECK_STATUSES
    return has_ok or has_status


def evaluate_artifacts(artifacts: dict[str, Any], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contracts = artifact_contracts(policy)
    missing_artifacts = [path for path in contracts if artifacts.get(path) is None]
    present_count = sum(1 for path in contracts if isinstance(artifacts.get(path), dict))
    field_gaps = []
    status_gaps = []
    value_gaps = []
    check_shape_gaps = []
    check_inventory_gaps = []
    metric_gaps = []
    array_gaps = []
    observed_check_count = 0

    for path, contract in contracts.items():
        data = artifacts.get(path)
        if not isinstance(data, dict):
            continue

        required_fields = list(contract.get("required_fields", []))
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            field_gaps.append({"artifact": path, "missing_fields": missing_fields})

        allowed_statuses = contract.get("allowed_statuses", DEFAULT_ALLOWED_STATUSES)
        status = data.get("status")
        if "status" in required_fields and status not in allowed_statuses:
            status_gaps.append(
                {
                    "artifact": path,
                    "status": status,
                    "allowed_statuses": allowed_statuses,
                }
            )

        for field, allowed_values in contract.get("allowed_values", {}).items():
            value = data.get(field)
            if value not in allowed_values:
                value_gaps.append(
                    {
                        "artifact": path,
                        "field": field,
                        "observed": value,
                        "allowed_values": allowed_values,
                    }
                )

        checks = data.get("checks")
        required_checks = list(contract.get("required_checks", []))
        if "checks" in required_fields or required_checks:
            names = set()
            if not isinstance(checks, list):
                check_shape_gaps.append({"artifact": path, "reason": "checks_not_list"})
            else:
                observed_check_count += len(checks)
                for index, item in enumerate(checks):
                    if not isinstance(item, dict):
                        check_shape_gaps.append({"artifact": path, "index": index, "reason": "check_not_object"})
                        continue
                    name = item.get("name")
                    if not isinstance(name, str) or not name:
                        check_shape_gaps.append({"artifact": path, "index": index, "reason": "missing_name"})
                    else:
                        names.add(name)
                    if not check_result_valid(item):
                        check_shape_gaps.append(
                            {
                                "artifact": path,
                                "index": index,
                                "check": name,
                                "reason": "missing_or_invalid_result",
                            }
                        )
            missing_checks = [name for name in required_checks if name not in names]
            if missing_checks:
                check_inventory_gaps.append({"artifact": path, "missing_checks": missing_checks})

        for field, minimum in contract.get("minimum_metrics", {}).items():
            value = data.get(field)
            if not is_number(value) or value < minimum:
                metric_gaps.append(
                    {
                        "artifact": path,
                        "field": field,
                        "contract": "minimum",
                        "limit": minimum,
                        "observed": value,
                    }
                )

        for field, maximum in contract.get("maximum_metrics", {}).items():
            value = data.get(field)
            if not is_number(value) or value > maximum:
                metric_gaps.append(
                    {
                        "artifact": path,
                        "field": field,
                        "contract": "maximum",
                        "limit": maximum,
                        "observed": value,
                    }
                )

        for field, minimum_length in contract.get("array_min_lengths", {}).items():
            value = data.get(field)
            if not isinstance(value, list) or len(value) < minimum_length:
                array_gaps.append(
                    {
                        "artifact": path,
                        "field": field,
                        "minimum_length": minimum_length,
                        "observed_length": len(value) if isinstance(value, list) else None,
                    }
                )

    checks = [
        check(
            "artifact_inventory",
            not missing_artifacts and present_count >= int(policy.get("minimum_artifact_count", 0)),
            {
                "missing_artifacts": missing_artifacts,
                "artifact_count": present_count,
                "policy_artifact_count": len(contracts),
                "minimum_artifact_count": policy.get("minimum_artifact_count"),
            },
        ),
        check("required_fields", not field_gaps, {"field_gaps": field_gaps}),
        check("status_contract", not status_gaps, {"status_gaps": status_gaps}),
        check("value_contract", not value_gaps, {"value_gaps": value_gaps}),
        check("check_shape", not check_shape_gaps, {"check_shape_gaps": check_shape_gaps}),
        check("check_inventory", not check_inventory_gaps, {"check_inventory_gaps": check_inventory_gaps}),
        check("metric_contract", not metric_gaps, {"metric_gaps": metric_gaps}),
        check("array_contract", not array_gaps, {"array_gaps": array_gaps}),
    ]
    metrics = {
        "artifact_count": present_count,
        "policy_artifact_count": len(contracts),
        "required_field_count": sum(len(item.get("required_fields", [])) for item in contracts.values()),
        "required_check_count": sum(len(item.get("required_checks", [])) for item in contracts.values()),
        "metric_contract_count": sum(
            len(item.get("minimum_metrics", {})) + len(item.get("maximum_metrics", {}))
            for item in contracts.values()
        ),
        "array_contract_count": sum(len(item.get("array_min_lengths", {})) for item in contracts.values()),
        "observed_check_count": observed_check_count,
    }
    return checks, metrics


def apply_fixture(artifacts: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(artifacts)
    artifact = str(fixture.get("artifact", ""))
    data = mutated.get(artifact)
    if not isinstance(data, dict):
        return mutated

    mutation = fixture.get("mutation")
    if mutation == "remove_field":
        data.pop(str(fixture.get("field", "")), None)
    elif mutation == "set_field":
        data[str(fixture.get("field", ""))] = fixture.get("value")
    elif mutation == "remove_check":
        target = str(fixture.get("check", ""))
        checks = data.get("checks")
        if isinstance(checks, list):
            data["checks"] = [
                item
                for item in checks
                if not isinstance(item, dict) or item.get("name") != target
            ]
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(artifacts: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(artifacts, fixture)
        checks, _ = evaluate_artifacts(mutated, policy)
        failed_checks = [item["name"] for item in checks if not item["ok"]]
        expected = str(fixture.get("expected_failed_check"))
        results.append(
            {
                "name": fixture.get("name"),
                "artifact": fixture.get("artifact"),
                "mutation": fixture.get("mutation"),
                "expected_failed_check": expected,
                "failed_checks": failed_checks,
                "detected": expected in failed_checks,
            }
        )
    return results


def artifact_summary(artifacts: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    summary = []
    for path in artifact_contracts(policy):
        data = artifacts.get(path)
        item = {"path": path, "present": isinstance(data, dict)}
        if isinstance(data, dict):
            item["status"] = data.get("status")
            item["check_count"] = len(data.get("checks", [])) if isinstance(data.get("checks"), list) else None
        summary.append(item)
    return summary


def build_report(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    artifacts = load_artifacts(repo_root, policy)
    checks, metrics = evaluate_artifacts(artifacts, policy)
    fixtures = evaluate_fixtures(artifacts, policy)
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
        "artifact_count": metrics["artifact_count"],
        "policy_artifact_count": metrics["policy_artifact_count"],
        "required_field_count": metrics["required_field_count"],
        "required_check_count": metrics["required_check_count"],
        "metric_contract_count": metrics["metric_contract_count"],
        "array_contract_count": metrics["array_contract_count"],
        "observed_check_count": metrics["observed_check_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "checks": checks,
        "fixtures": fixtures,
        "artifacts": artifact_summary(artifacts, policy),
    }


def resolved_output_path(path: Path, default_name: str) -> Path:
    return path if path.suffix else path / default_name


def write_json(report: dict[str, Any], output: Path) -> None:
    path = resolved_output_path(output, "evidence-schema-audit.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output: Path) -> None:
    path = resolved_output_path(output, "evidence-schema-audit.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Evidence Schema Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that critical evidence JSON files keep stable",
        "machine-readable contracts for status fields, required fields, check",
        "inventory, metric minimums, metric ceilings, array lengths, allowed",
        "values, and negative drift fixtures.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Artifacts | {report['artifact_count']} |",
        f"| Required fields | {report['required_field_count']} |",
        f"| Required checks | {report['required_check_count']} |",
        f"| Metric contracts | {report['metric_contract_count']} |",
        f"| Array contracts | {report['array_contract_count']} |",
        f"| Observed checks | {report['observed_check_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")

    lines.extend(["", "## Artifact Contracts", "", "| Artifact | Status | Checks |", "| --- | --- | ---: |"])
    for item in report["artifacts"]:
        status = item.get("status", "missing")
        check_count = item.get("check_count")
        lines.append(f"| `{item['path']}` | `{status}` | {check_count if check_count is not None else 'n/a'} |")

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
    parser.add_argument("--policy", default="config/evidence-schema-policy.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    parser.add_argument("--output", default="")
    parser.add_argument("--markdown-output", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    policy = load_json(resolve_repo_path(repo_root, args.policy))
    report = build_report(repo_root, policy)
    output_dir = resolve_repo_path(repo_root, args.output_dir)
    json_output = resolve_repo_path(repo_root, args.output) if args.output else output_dir
    markdown_output = resolve_repo_path(repo_root, args.markdown_output) if args.markdown_output else output_dir
    write_json(report, json_output)
    write_markdown(report, markdown_output)
    print(f"wrote {resolved_output_path(json_output, 'evidence-schema-audit.json')}")
    print(f"wrote {resolved_output_path(markdown_output, 'evidence-schema-audit.md')}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
