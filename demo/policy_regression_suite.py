#!/usr/bin/env python3
"""Run deployment-policy regression fixtures against synthetic evidence."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo import deployment_policy


def baseline_evidence() -> dict[str, dict[str, Any]]:
    return {
        "gate": {"status": "pass"},
        "burn_rate": {
            "windows": [
                {
                    "window": "5m",
                    "burn_rate": 0.4,
                    "action": "observe",
                }
            ]
        },
        "rollout_guard": {"decision": "promote"},
        "trace_quality": {
            "status": "pass",
            "payloads": 5,
            "spans": 136,
            "resource_missing": {},
            "root_missing": {},
            "child_span_missing": {},
        },
        "collector_resilience": {
            "risk": "ok",
            "queue_utilization": 0.42,
            "estimated_lost_spans": 0,
            "required_storage_mib": 96,
            "configured_storage_mib": 256,
        },
        "hpa_lag": {
            "scenarios": [
                {
                    "scenario": "baseline",
                    "decision": "steady_state",
                    "violations": [],
                }
            ]
        },
        "tenant_blast_radius": {"breached_scenarios": []},
        "token_cost_guard": {
            "scenarios": [
                {
                    "scenario": "baseline",
                    "decision": "allow",
                    "violations": [],
                }
            ]
        },
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(base: Any, overrides: Any) -> Any:
    if isinstance(base, dict) and isinstance(overrides, dict):
        merged = copy.deepcopy(base)
        for key, value in overrides.items():
            merged[key] = deep_merge(merged.get(key), value)
        return merged
    return copy.deepcopy(overrides)


def evidence_for_fixture(fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = baseline_evidence()
    overrides = fixture.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError(f"fixture {fixture.get('name', '<unknown>')} overrides must be an object")
    return deep_merge(evidence, overrides)


def evaluate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    name = str(fixture.get("name", "unnamed"))
    evidence = evidence_for_fixture(fixture)
    policy = deployment_policy.evaluate(**evidence)

    expected_decision = str(fixture["expected_decision"])
    expected_blocking = sorted(str(item) for item in fixture.get("expected_blocking_controls", []))
    expected_review = sorted(str(item) for item in fixture.get("expected_review_controls", []))
    actual_blocking = sorted(str(item) for item in policy.get("blocking_controls", []))
    actual_review = sorted(str(item) for item in policy.get("review_controls", []))

    checks = {
        "decision": policy.get("decision") == expected_decision,
        "blocking_controls": actual_blocking == expected_blocking,
        "review_controls": actual_review == expected_review,
    }
    return {
        "name": name,
        "description": fixture.get("description", ""),
        "passed": all(checks.values()),
        "checks": checks,
        "expected_decision": expected_decision,
        "actual_decision": policy.get("decision"),
        "expected_blocking_controls": expected_blocking,
        "actual_blocking_controls": actual_blocking,
        "expected_review_controls": expected_review,
        "actual_review_controls": actual_review,
        "human_approval_required": policy.get("human_approval_required"),
        "operator_actions": policy.get("operator_actions", []),
    }


def run_suite(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    results = [evaluate_fixture(fixture) for fixture in fixtures]
    controls = sorted(
        {
            control
            for result in results
            for control in result["actual_blocking_controls"] + result["actual_review_controls"]
        }
    )
    passed_count = sum(1 for result in results if result["passed"])
    return {
        "status": "pass" if passed_count == len(results) else "fail",
        "fixture_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "controls_under_test": controls,
        "fixtures": results,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "policy-regression-suite.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Policy Regression Suite",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This suite protects the deployment policy from silent drift. Each",
        "fixture starts from the same clean release evidence and changes one",
        "production signal to prove that promote, block, and manual-review",
        "decisions remain stable.",
        "",
        "## Fixtures",
        "",
        "| Fixture | Expected | Actual | Status |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["fixtures"]:
        status = "PASS" if item["passed"] else "FAIL"
        lines.append(
            f"| `{item['name']}` | `{item['expected_decision']}` | `{item['actual_decision']}` | {status} |"
        )

    lines.extend(["", "## Controls Under Test", ""])
    if report["controls_under_test"]:
        for control in report["controls_under_test"]:
            lines.append(f"- `{control}`")
    else:
        lines.append("- none")

    lines.extend(["", "## Operator Action Coverage", ""])
    for item in report["fixtures"]:
        lines.append(f"### {item['name']}")
        if item["operator_actions"]:
            for action in item["operator_actions"]:
                lines.append(f"- {action}")
        else:
            lines.append("- none")
        lines.append("")
    output_dir.joinpath("policy-regression-suite.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", default="config/deployment-policy-fixtures.json")
    parser.add_argument("--output-dir", default="out/policy-regression-suite")
    args = parser.parse_args()

    fixture_config = load_json(Path(args.fixtures))
    fixtures = fixture_config.get("fixtures", [])
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("fixture config must contain a non-empty fixtures list")

    report = run_suite(fixtures)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'policy-regression-suite.json'}")
    print(f"wrote {output_dir / 'policy-regression-suite.md'}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
