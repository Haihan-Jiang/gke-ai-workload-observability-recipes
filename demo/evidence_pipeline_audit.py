#!/usr/bin/env python3
"""Audit evidence generation pipeline dependency ordering."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
PYTHON_STEP_RE = re.compile(r"^\s*python3\s+(demo/[A-Za-z0-9_]+\.py)\b")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def step_script_map(policy: dict[str, Any]) -> dict[str, str]:
    return {str(item["script"]): str(item["name"]) for item in policy.get("required_steps", [])}


def required_step_names(policy: dict[str, Any]) -> list[str]:
    return [str(item["name"]) for item in policy.get("required_steps", [])]


def extract_steps(script_text: str, policy: dict[str, Any]) -> list[dict[str, Any]]:
    by_script = step_script_map(policy)
    steps = []
    for line_number, line in enumerate(script_text.splitlines(), 1):
        match = PYTHON_STEP_RE.match(line)
        if not match:
            continue
        script = match.group(1)
        name = by_script.get(script)
        if name:
            steps.append({"name": name, "script": script, "line": line_number})
    return steps


def step_indexes(steps: list[dict[str, Any]]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for index, step in enumerate(steps):
        indexes.setdefault(str(step["name"]), index)
    return indexes


def duplicate_steps(steps: list[dict[str, Any]]) -> list[str]:
    names = [str(step["name"]) for step in steps]
    return sorted({name for name in names if names.count(name) > 1})


def evaluate_steps(steps: list[dict[str, Any]], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required = required_step_names(policy)
    observed = [str(step["name"]) for step in steps]
    indexes = step_indexes(steps)
    missing = [name for name in required if name not in observed]
    duplicates = duplicate_steps(steps)
    unknown_dependencies = []
    order_gaps = []
    artifact_dependencies = []

    for dependency in policy.get("dependencies", []):
        producer = str(dependency["producer"])
        consumer = str(dependency["consumer"])
        artifact = str(dependency.get("artifact", ""))
        if artifact:
            artifact_dependencies.append(artifact)
        if producer not in indexes or consumer not in indexes:
            unknown_dependencies.append(
                {
                    "producer": producer,
                    "consumer": consumer,
                    "artifact": artifact,
                    "missing_steps": [
                        name for name in [producer, consumer] if name not in indexes
                    ],
                }
            )
            continue
        if indexes[producer] >= indexes[consumer]:
            order_gaps.append(
                {
                    "producer": producer,
                    "consumer": consumer,
                    "artifact": artifact,
                    "producer_index": indexes[producer],
                    "consumer_index": indexes[consumer],
                }
            )

    checks = [
        check(
            "step_inventory",
            not missing
            and not duplicates
            and len(steps) >= int(policy.get("minimum_step_count", 0)),
            {
                "step_count": len(steps),
                "minimum_step_count": policy.get("minimum_step_count"),
                "missing_steps": missing,
                "duplicate_steps": duplicates,
            },
        ),
        check(
            "dependency_inventory",
            not unknown_dependencies
            and len(policy.get("dependencies", [])) >= int(policy.get("minimum_dependency_count", 0)),
            {
                "dependency_count": len(policy.get("dependencies", [])),
                "minimum_dependency_count": policy.get("minimum_dependency_count"),
                "unknown_dependencies": unknown_dependencies,
            },
        ),
        check(
            "dependency_order",
            not order_gaps,
            {"order_gaps": order_gaps},
        ),
        check(
            "artifact_dependency_coverage",
            len(artifact_dependencies) == len(policy.get("dependencies", []))
            and all(path for path in artifact_dependencies),
            {
                "artifact_dependency_count": len(artifact_dependencies),
                "dependency_count": len(policy.get("dependencies", [])),
            },
        ),
    ]
    metrics = {
        "step_count": len(steps),
        "required_step_count": len(required),
        "dependency_count": len(policy.get("dependencies", [])),
        "artifact_dependency_count": len(artifact_dependencies),
    }
    return checks, metrics


def move_after(steps: list[dict[str, Any]], producer: str, consumer: str) -> list[dict[str, Any]]:
    moved = [copy.deepcopy(step) for step in steps]
    producer_items = [step for step in moved if step["name"] == producer]
    if not producer_items:
        return moved
    producer_item = producer_items[0]
    moved = [step for step in moved if step is not producer_item]
    consumer_indexes = [index for index, step in enumerate(moved) if step["name"] == consumer]
    if not consumer_indexes:
        moved.append(producer_item)
        return moved
    moved.insert(consumer_indexes[0] + 1, producer_item)
    return moved


def apply_fixture(steps: list[dict[str, Any]], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutation = fixture.get("mutation")
    if mutation == "producer_after_consumer":
        return move_after(
            steps,
            str(fixture.get("producer", "")),
            str(fixture.get("consumer", "")),
        )
    if mutation == "remove_step":
        target = str(fixture.get("step", ""))
        return [copy.deepcopy(step) for step in steps if step["name"] != target]
    if mutation == "duplicate_step":
        target = str(fixture.get("step", ""))
        mutated = [copy.deepcopy(step) for step in steps]
        for step in steps:
            if step["name"] == target:
                duplicate = copy.deepcopy(step)
                duplicate["line"] = int(duplicate.get("line", 0)) + 1
                mutated.append(duplicate)
                break
        return mutated
    raise ValueError(f"unsupported fixture mutation: {mutation}")


def evaluate_fixtures(steps: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(steps, fixture)
        checks, _ = evaluate_steps(mutated, policy)
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


def dependency_summary(steps: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    indexes = step_indexes(steps)
    summary = []
    for dependency in policy.get("dependencies", []):
        producer = str(dependency["producer"])
        consumer = str(dependency["consumer"])
        producer_index = indexes.get(producer)
        consumer_index = indexes.get(consumer)
        summary.append(
            {
                "producer": producer,
                "consumer": consumer,
                "artifact": dependency.get("artifact"),
                "producer_index": producer_index,
                "consumer_index": consumer_index,
                "ordered": producer_index is not None
                and consumer_index is not None
                and producer_index < consumer_index,
            }
        )
    return summary


def build_report(repo_root: Path, policy: dict[str, Any], script: Path) -> dict[str, Any]:
    script_path = script if script.is_absolute() else repo_root / script
    steps = extract_steps(script_path.read_text(encoding="utf-8"), policy)
    checks, metrics = evaluate_steps(steps, policy)
    fixtures = evaluate_fixtures(steps, policy)
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
        "script": str(script),
        "step_count": metrics["step_count"],
        "required_step_count": metrics["required_step_count"],
        "dependency_count": metrics["dependency_count"],
        "artifact_dependency_count": metrics["artifact_dependency_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "checks": checks,
        "steps": steps,
        "dependencies": dependency_summary(steps, policy),
        "fixtures": fixtures,
    }


def resolved_output_path(path: Path, default_name: str) -> Path:
    return path if path.suffix else path / default_name


def write_json(report: dict[str, Any], output: Path) -> None:
    path = resolved_output_path(output, "evidence-pipeline-audit.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output: Path) -> None:
    path = resolved_output_path(output, "evidence-pipeline-audit.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Evidence Pipeline Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that generated evidence steps run after their",
        "producer steps and before their consumers, so release gates cannot",
        "accidentally read stale committed artifacts.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Steps | {report['step_count']} |",
        f"| Required steps | {report['required_step_count']} |",
        f"| Dependencies | {report['dependency_count']} |",
        f"| Artifact dependencies | {report['artifact_dependency_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Critical Dependencies", "", "| Producer | Consumer | Ordered |", "| --- | --- | --- |"])
    for item in report["dependencies"]:
        lines.append(
            f"| `{item['producer']}` | `{item['consumer']}` | {'yes' if item['ordered'] else 'no'} |"
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
    parser.add_argument("--policy", default="config/evidence-pipeline-policy.json")
    parser.add_argument("--script", default="scripts/generate-evidence.sh")
    parser.add_argument("--output-dir", default="docs/evidence")
    parser.add_argument("--output", default="")
    parser.add_argument("--markdown-output", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    policy = load_json(resolve_repo_path(repo_root, args.policy))
    report = build_report(repo_root, policy, Path(args.script))
    output_dir = resolve_repo_path(repo_root, args.output_dir)
    json_output = resolve_repo_path(repo_root, args.output) if args.output else output_dir
    markdown_output = resolve_repo_path(repo_root, args.markdown_output) if args.markdown_output else output_dir
    write_json(report, json_output)
    write_markdown(report, markdown_output)
    print(f"wrote {resolved_output_path(json_output, 'evidence-pipeline-audit.json')}")
    print(f"wrote {resolved_output_path(markdown_output, 'evidence-pipeline-audit.md')}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
