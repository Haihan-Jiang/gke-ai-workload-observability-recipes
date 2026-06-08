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
    "telemetry-redaction-audit.md",
    "telemetry-redaction-audit.json",
    "telemetry-cost-budget.md",
    "telemetry-cost-budget.json",
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
    "supply-chain-audit.md",
    "supply-chain-audit.json",
    "k8s-hardening-audit.md",
    "k8s-hardening-audit.json",
    "admission-policy-audit.md",
    "admission-policy-audit.json",
    "alerting-rules.md",
    "alerting-rules.json",
    "grafana-dashboard.md",
    "grafana-dashboard.json",
    "openslo-contract.md",
    "openslo-contract.json",
    "observability-drift-audit.md",
    "observability-drift-audit.json",
    "error-budget-ledger.md",
    "error-budget-ledger.json",
    "rollback-drill.md",
    "rollback-drill.json",
    "post-incident-review.md",
    "post-incident-review.json",
    "incident-response-drill.md",
    "incident-response-drill.json",
    "dependency-contract-audit.md",
    "dependency-contract-audit.json",
    "synthetic-probe-audit.md",
    "synthetic-probe-audit.json",
    "load-shedding-policy-audit.md",
    "load-shedding-policy-audit.json",
    "release-waiver-governance.md",
    "release-waiver-governance.json",
    "disaster-recovery-drill.md",
    "disaster-recovery-drill.json",
    "evidence-provenance.md",
    "evidence-provenance.json",
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
    supply_chain: dict[str, Any],
    k8s_hardening: dict[str, Any],
    admission_policy: dict[str, Any],
    alerting: dict[str, Any],
    dashboard: dict[str, Any],
    openslo: dict[str, Any],
    observability_drift: dict[str, Any],
    telemetry_redaction: dict[str, Any],
    telemetry_cost: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    post_incident_review: dict[str, Any],
    incident_response_drill: dict[str, Any],
    dependency_contract: dict[str, Any],
    synthetic_probe: dict[str, Any],
    load_shedding_policy: dict[str, Any],
    release_waiver_governance: dict[str, Any],
    disaster_recovery_drill: dict[str, Any],
    evidence_provenance: dict[str, Any],
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
            "name": "supply_chain_audit",
            "ok": supply_chain.get("status") == "pass"
            and int(supply_chain.get("image_count", 0)) >= 2
            and int(supply_chain.get("digest_pinned_count", 0)) >= 2
            and int(supply_chain.get("failed_count", -1)) == 0,
        },
        {
            "name": "k8s_manifest_hardening",
            "ok": k8s_hardening.get("status") == "pass"
            and int(k8s_hardening.get("check_count", 0)) >= 11
            and int(k8s_hardening.get("failed_count", -1)) == 0,
        },
        {
            "name": "admission_policy_audit",
            "ok": admission_policy.get("status") == "pass"
            and int(admission_policy.get("policy_check_count", 0)) >= 10
            and int(admission_policy.get("allowed_deployment_count", 0)) >= 2
            and int(admission_policy.get("denied_fixture_count", 0)) >= 8
            and int(admission_policy.get("failed_count", -1)) == 0,
        },
        {
            "name": "slo_alerting_rules",
            "ok": alerting.get("status") == "pass"
            and int(alerting.get("rule_count", 0)) >= 5
            and int(alerting.get("failed_count", -1)) == 0,
        },
        {
            "name": "grafana_dashboard",
            "ok": dashboard.get("status") == "pass"
            and int(dashboard.get("panel_count", 0)) >= 6
            and int(dashboard.get("failed_count", -1)) == 0,
        },
        {
            "name": "openslo_contract",
            "ok": openslo.get("status") == "pass"
            and float(openslo.get("objective_target", 0)) >= 99.0
            and int(openslo.get("scenario_count", 0)) >= 5
            and int(openslo.get("failed_count", -1)) == 0,
        },
        {
            "name": "observability_drift_audit",
            "ok": observability_drift.get("status") == "pass"
            and int(observability_drift.get("required_scenario_count", 0)) >= 5
            and int(observability_drift.get("surface_count", 0)) >= 4
            and int(observability_drift.get("detected_fixture_count", 0)) >= 5
            and int(observability_drift.get("failed_count", -1)) == 0,
        },
        {
            "name": "telemetry_redaction_audit",
            "ok": telemetry_redaction.get("status") == "pass"
            and int(telemetry_redaction.get("payload_count", 0)) >= 5
            and int(telemetry_redaction.get("redaction_violation_count", -1)) == 0
            and int(telemetry_redaction.get("failed_count", -1)) == 0,
        },
        {
            "name": "telemetry_cost_budget",
            "ok": telemetry_cost.get("status") == "pass"
            and int(telemetry_cost.get("scenario_count", 0)) >= 5
            and float(telemetry_cost.get("daily_ingest_gib", 999999.0)) <= 25.0
            and int(telemetry_cost.get("failed_count", -1)) == 0,
        },
        {
            "name": "error_budget_ledger",
            "ok": error_budget.get("status") == "pass"
            and int(error_budget.get("scenario_count", 0)) >= 5
            and int(error_budget.get("non_green_count", 0)) >= 4
            and int(error_budget.get("failed_count", -1)) == 0
            and error_budget.get("decision_counts", {}).get("within_budget") == 1,
        },
        {
            "name": "rollback_drill",
            "ok": rollback_drill.get("status") == "pass"
            and int(rollback_drill.get("drill_count", 0)) >= 4
            and int(rollback_drill.get("rollback_required_count", 0)) >= 2
            and int(rollback_drill.get("failed_count", -1)) == 0,
        },
        {
            "name": "post_incident_review",
            "ok": post_incident_review.get("status") == "pass"
            and int(post_incident_review.get("review_count", 0)) >= 4
            and int(post_incident_review.get("action_item_count", 0)) >= 8
            and int(post_incident_review.get("failed_count", -1)) == 0,
        },
        {
            "name": "incident_response_drill",
            "ok": incident_response_drill.get("status") == "pass"
            and int(incident_response_drill.get("response_count", 0)) >= 5
            and int(incident_response_drill.get("incident_response_count", 0)) >= 4
            and int(incident_response_drill.get("page_count", 0)) >= 4
            and int(incident_response_drill.get("ticket_count", 0)) >= 1
            and int(incident_response_drill.get("detected_fixture_count", 0)) >= 5
            and int(incident_response_drill.get("failed_count", -1)) == 0,
        },
        {
            "name": "dependency_contract_audit",
            "ok": dependency_contract.get("status") == "pass"
            and int(dependency_contract.get("dependency_count", 0)) >= 4
            and int(dependency_contract.get("incident_contract_count", 0)) >= 4
            and int(dependency_contract.get("dominant_dependency_count", 0)) >= 3
            and int(dependency_contract.get("detected_fixture_count", 0)) >= 5
            and int(dependency_contract.get("failed_count", -1)) == 0,
        },
        {
            "name": "synthetic_probe_audit",
            "ok": synthetic_probe.get("status") == "pass"
            and int(synthetic_probe.get("probe_count", 0)) >= 5
            and int(synthetic_probe.get("incident_probe_count", 0)) >= 4
            and int(synthetic_probe.get("preflight_block_count", 0)) >= 2
            and int(synthetic_probe.get("detected_fixture_count", 0)) >= 5
            and int(synthetic_probe.get("failed_count", -1)) == 0,
        },
        {
            "name": "load_shedding_policy_audit",
            "ok": load_shedding_policy.get("status") == "pass"
            and int(load_shedding_policy.get("action_count", 0)) >= 5
            and int(load_shedding_policy.get("protective_action_count", 0)) >= 4
            and int(load_shedding_policy.get("detected_fixture_count", 0)) >= 5
            and int(load_shedding_policy.get("failed_count", -1)) == 0,
        },
        {
            "name": "release_waiver_governance",
            "ok": release_waiver_governance.get("status") == "pass"
            and int(release_waiver_governance.get("waiver_count", 0)) >= 4
            and int(release_waiver_governance.get("conditional_approval_count", 0)) >= 2
            and int(release_waiver_governance.get("denied_override_count", 0)) >= 2
            and int(release_waiver_governance.get("invalid_waiver_count", -1)) == 0
            and int(release_waiver_governance.get("unsafe_approved_count", -1)) == 0
            and int(release_waiver_governance.get("failed_count", -1)) == 0,
        },
        {
            "name": "disaster_recovery_drill",
            "ok": disaster_recovery_drill.get("status") == "pass"
            and int(disaster_recovery_drill.get("artifact_count", 0)) >= 24
            and int(disaster_recovery_drill.get("restored_count", -1)) == int(disaster_recovery_drill.get("artifact_count", 0))
            and int(disaster_recovery_drill.get("hash_match_count", -1)) == int(disaster_recovery_drill.get("artifact_count", 0))
            and int(disaster_recovery_drill.get("detected_fixture_count", 0)) >= 4
            and int(disaster_recovery_drill.get("estimated_restore_minutes", 999999)) <= int(disaster_recovery_drill.get("rto_minutes", 0))
            and int(disaster_recovery_drill.get("failed_count", -1)) == 0,
        },
        {
            "name": "evidence_provenance",
            "ok": evidence_provenance.get("status") == "pass"
            and int(evidence_provenance.get("artifact_count", 0)) >= 70
            and int(evidence_provenance.get("source_input_count", 0)) >= 51
            and int(evidence_provenance.get("failed_count", -1)) == 0,
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
        "policy, policy regression fixtures, supply-chain audit, Kubernetes",
        "manifest hardening, admission policy simulation, SLO alerting rules,",
        "Grafana dashboard coverage, OpenSLO contract, observability drift",
        "detection,",
        "telemetry redaction, telemetry cost budget, error-budget accounting,",
        "rollback drill coverage, post-incident review coverage, incident",
        "response drill coverage, dependency contract coverage, release",
        "synthetic probe coverage, load-shedding policy coverage, release",
        "waiver governance, disaster recovery drill coverage, evidence",
        "provenance, and committed evidence are present and internally",
        "consistent.",
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
    parser.add_argument("--supply-chain", default="out/supply-chain-audit/supply-chain-audit.json")
    parser.add_argument("--k8s-hardening", default="out/k8s-hardening-audit/k8s-hardening-audit.json")
    parser.add_argument("--admission-policy", default="out/admission-policy-audit/admission-policy-audit.json")
    parser.add_argument("--alerting", default="out/alerting-rules/alerting-rules.json")
    parser.add_argument("--dashboard", default="out/grafana-dashboard/grafana-dashboard.json")
    parser.add_argument("--openslo", default="out/openslo-contract/openslo-contract.json")
    parser.add_argument("--observability-drift", default="out/observability-drift-audit/observability-drift-audit.json")
    parser.add_argument("--telemetry-redaction", default="out/telemetry-redaction-audit/telemetry-redaction-audit.json")
    parser.add_argument("--telemetry-cost", default="out/telemetry-cost-budget/telemetry-cost-budget.json")
    parser.add_argument("--error-budget", default="out/error-budget-ledger/error-budget-ledger.json")
    parser.add_argument("--rollback-drill", default="out/rollback-drill/rollback-drill.json")
    parser.add_argument("--post-incident-review", default="out/post-incident-review/post-incident-review.json")
    parser.add_argument("--incident-response-drill", default="out/incident-response-drill/incident-response-drill.json")
    parser.add_argument("--dependency-contract", default="out/dependency-contract-audit/dependency-contract-audit.json")
    parser.add_argument("--synthetic-probe", default="out/synthetic-probe-audit/synthetic-probe-audit.json")
    parser.add_argument("--load-shedding-policy", default="out/load-shedding-policy-audit/load-shedding-policy-audit.json")
    parser.add_argument("--release-waiver-governance", default="out/release-waiver-governance/release-waiver-governance.json")
    parser.add_argument("--disaster-recovery-drill", default="out/disaster-recovery-drill/disaster-recovery-drill.json")
    parser.add_argument("--evidence-provenance", default="out/evidence-provenance/evidence-provenance.json")
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
        supply_chain=load_json(Path(args.supply_chain)),
        k8s_hardening=load_json(Path(args.k8s_hardening)),
        admission_policy=load_json(Path(args.admission_policy)),
        alerting=load_json(Path(args.alerting)),
        dashboard=load_json(Path(args.dashboard)),
        openslo=load_json(Path(args.openslo)),
        observability_drift=load_json(Path(args.observability_drift)),
        telemetry_redaction=load_json(Path(args.telemetry_redaction)),
        telemetry_cost=load_json(Path(args.telemetry_cost)),
        error_budget=load_json(Path(args.error_budget)),
        rollback_drill=load_json(Path(args.rollback_drill)),
        post_incident_review=load_json(Path(args.post_incident_review)),
        incident_response_drill=load_json(Path(args.incident_response_drill)),
        dependency_contract=load_json(Path(args.dependency_contract)),
        synthetic_probe=load_json(Path(args.synthetic_probe)),
        load_shedding_policy=load_json(Path(args.load_shedding_policy)),
        release_waiver_governance=load_json(Path(args.release_waiver_governance)),
        disaster_recovery_drill=load_json(Path(args.disaster_recovery_drill)),
        evidence_provenance=load_json(Path(args.evidence_provenance)),
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
