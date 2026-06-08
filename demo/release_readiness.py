#!/usr/bin/env python3
"""Aggregate lab evidence into a release-readiness report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_EVIDENCE = [
    "sample-incident-report.md",
    "sample-summary.json",
    "incident-dashboard.svg",
    "reliability-gate.md",
    "reliability-gate.json",
    "capacity-plan.md",
    "capacity-plan.json",
    "incident-runbooks.md",
    "incident-runbooks.json",
    "burn-rate-analysis.md",
    "burn-rate-analysis.json",
    "rollout-guard.md",
    "rollout-guard.json",
    "trace-quality-audit.md",
    "trace-quality-audit.json",
    "collector-resilience.md",
    "collector-resilience.json",
    "incident-correlation.md",
    "incident-correlation.json",
    "complex-problems.md",
    "complex-problems.json",
    "critical-path-attribution.md",
    "critical-path-attribution.json",
    "evidence-coverage.md",
    "evidence-coverage.json",
    "hpa-lag-analysis.md",
    "hpa-lag-analysis.json",
    "tenant-blast-radius.md",
    "tenant-blast-radius.json",
    "token-cost-guard.md",
    "token-cost-guard.json",
    "detailed-problems.md",
    "detailed-problems.json",
    "deployment-policy.md",
    "deployment-policy.json",
    "policy-regression-suite.md",
    "policy-regression-suite.json",
    "k8s-hardening-audit.md",
    "k8s-hardening-audit.json",
]

REQUIRED_POLICY_REGRESSION_CONTROLS = {
    "burn_rate",
    "collector_resilience",
    "hpa_lag",
    "reliability_gate",
    "rollout_guard",
    "tenant_blast_radius",
    "token_cost_guard",
    "trace_quality",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(
    *,
    gate: dict[str, Any],
    capacity: dict[str, Any],
    runbooks: dict[str, Any],
    advanced: dict[str, Any],
    detailed: dict[str, Any],
    policy: dict[str, Any],
    policy_regression: dict[str, Any],
    k8s_hardening: dict[str, Any],
    evidence_dir: Path,
) -> dict[str, Any]:
    evidence = [
        {"path": name, "exists": (evidence_dir / name).exists()}
        for name in REQUIRED_EVIDENCE
    ]
    scenario_names = {item["scenario"] for item in capacity.get("scenarios", [])}
    runbook_names = {item["scenario"] for item in runbooks.get("runbooks", [])}
    warnings = [
        warning
        for item in capacity.get("scenarios", [])
        for warning in item.get("warnings", [])
    ]
    controls_under_test = set(policy_regression.get("controls_under_test", []))
    checks = [
        {"name": "reliability_gate", "ok": gate.get("status") == "pass"},
        {"name": "evidence_files", "ok": all(item["exists"] for item in evidence)},
        {"name": "runbook_coverage", "ok": scenario_names == runbook_names and len(runbook_names) > 0},
        {"name": "capacity_plan", "ok": len(capacity.get("scenarios", [])) >= 5},
        {"name": "advanced_problem_coverage", "ok": len(advanced.get("problems", [])) >= 5},
        {"name": "detailed_problem_coverage", "ok": len(detailed.get("problems", [])) >= 5},
        {
            "name": "deployment_policy",
            "ok": policy.get("status") == "generated"
            and policy.get("decision")
            in {"promote", "manual_review_required", "block_production_promotion"}
            and int(policy.get("control_count", 0)) >= 8,
        },
        {
            "name": "policy_regression_suite",
            "ok": policy_regression.get("status") == "pass"
            and int(policy_regression.get("fixture_count", 0)) >= 8
            and int(policy_regression.get("failed_count", -1)) == 0
            and controls_under_test >= REQUIRED_POLICY_REGRESSION_CONTROLS,
        },
        {
            "name": "k8s_manifest_hardening",
            "ok": k8s_hardening.get("status") == "pass"
            and int(k8s_hardening.get("check_count", 0)) >= 11
            and int(k8s_hardening.get("failed_count", -1)) == 0,
        },
    ]
    return {
        "status": "pass" if all(item["ok"] for item in checks) else "fail",
        "checks": checks,
        "evidence": evidence,
        "warnings": sorted(set(warnings)),
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "release-readiness.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    status = str(report["status"]).upper()
    lines = [
        "# Release Readiness Evidence",
        "",
        f"Overall status: **{status}**",
        "",
        "This report is the final local gate for the portfolio lab. It verifies",
        "that the replay, reliability gate, capacity plan, runbooks, advanced",
        "reliability controls, detailed reliability controls, deployment",
        "policy, policy regression fixtures, Kubernetes manifest hardening,",
        "and committed evidence are present and internally consistent.",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")

    lines.extend(["", "## Evidence Files", "", "| Path | Present |", "| --- | --- |"])
    for item in report["evidence"]:
        lines.append(f"| `{item['path']}` | {'yes' if item['exists'] else 'no'} |")

    lines.extend(["", "## Capacity Warnings", ""])
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    lines.append("")
    (output_dir / "release-readiness.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", default="out/reliability-gate/reliability-gate.json")
    parser.add_argument("--capacity", default="out/capacity-plan/capacity-plan.json")
    parser.add_argument("--runbooks", default="out/incident-runbooks/incident-runbooks.json")
    parser.add_argument("--advanced", default="out/advanced-reliability/complex-problems.json")
    parser.add_argument("--detailed", default="out/detailed-reliability/detailed-problems.json")
    parser.add_argument("--policy", default="out/deployment-policy/deployment-policy.json")
    parser.add_argument("--policy-regression", default="out/policy-regression-suite/policy-regression-suite.json")
    parser.add_argument("--k8s-hardening", default="out/k8s-hardening-audit/k8s-hardening-audit.json")
    parser.add_argument("--evidence-dir", default="docs/evidence")
    parser.add_argument("--output-dir", default="out/release-readiness")
    args = parser.parse_args()

    report = evaluate(
        gate=load_json(Path(args.gate)),
        capacity=load_json(Path(args.capacity)),
        runbooks=load_json(Path(args.runbooks)),
        advanced=load_json(Path(args.advanced)),
        detailed=load_json(Path(args.detailed)),
        policy=load_json(Path(args.policy)),
        policy_regression=load_json(Path(args.policy_regression)),
        k8s_hardening=load_json(Path(args.k8s_hardening)),
        evidence_dir=Path(args.evidence_dir),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'release-readiness.json'}")
    print(f"wrote {output_dir / 'release-readiness.md'}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
