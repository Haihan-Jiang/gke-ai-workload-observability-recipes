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
    "ci-governance-audit.md",
    "ci-governance-audit.json",
    "repository-governance-audit.md",
    "repository-governance-audit.json",
    "developer-runtime-audit.md",
    "developer-runtime-audit.json",
    "k8s-hardening-audit.md",
    "k8s-hardening-audit.json",
    "pod-security-admission-audit.md",
    "pod-security-admission-audit.json",
    "namespace-resource-audit.md",
    "namespace-resource-audit.json",
    "availability-topology-audit.md",
    "availability-topology-audit.json",
    "autoscaling-policy-audit.md",
    "autoscaling-policy-audit.json",
    "scheduling-placement-audit.md",
    "scheduling-placement-audit.json",
    "rollout-safety-audit.md",
    "rollout-safety-audit.json",
    "config-rollout-audit.md",
    "config-rollout-audit.json",
    "network-boundary-audit.md",
    "network-boundary-audit.json",
    "collector-self-observability-audit.md",
    "collector-self-observability-audit.json",
    "telemetry-sampling-audit.md",
    "telemetry-sampling-audit.json",
    "workload-identity-audit.md",
    "workload-identity-audit.json",
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
    "model-release-safety-audit.md",
    "model-release-safety-audit.json",
    "shadow-traffic-replay-audit.md",
    "shadow-traffic-replay-audit.json",
    "accelerator-quota-fairness-audit.md",
    "accelerator-quota-fairness-audit.json",
    "load-shedding-policy-audit.md",
    "load-shedding-policy-audit.json",
    "regional-failover-audit.md",
    "regional-failover-audit.json",
    "release-waiver-governance.md",
    "release-waiver-governance.json",
    "evidence-schema-audit.md",
    "evidence-schema-audit.json",
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
    ci_governance: dict[str, Any],
    repository_governance: dict[str, Any],
    developer_runtime: dict[str, Any],
    k8s_hardening: dict[str, Any],
    pod_security_admission: dict[str, Any],
    namespace_resource: dict[str, Any],
    availability_topology: dict[str, Any],
    autoscaling_policy: dict[str, Any],
    scheduling_placement: dict[str, Any],
    rollout_safety: dict[str, Any],
    config_rollout: dict[str, Any],
    network_boundary: dict[str, Any],
    collector_self_observability: dict[str, Any],
    telemetry_sampling: dict[str, Any],
    workload_identity: dict[str, Any],
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
    model_release_safety: dict[str, Any],
    shadow_traffic_replay: dict[str, Any],
    accelerator_quota: dict[str, Any],
    load_shedding_policy: dict[str, Any],
    regional_failover: dict[str, Any],
    release_waiver_governance: dict[str, Any],
    evidence_schema: dict[str, Any],
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
            "name": "ci_governance_audit",
            "ok": ci_governance.get("status") == "pass"
            and int(ci_governance.get("workflow_count", 0)) >= 1
            and int(ci_governance.get("job_count", 0)) >= 1
            and int(ci_governance.get("action_count", 0)) >= 2
            and int(ci_governance.get("hardened_action_count", 0)) >= 2
            and int(ci_governance.get("detected_fixture_count", 0)) >= 8
            and int(ci_governance.get("failed_count", -1)) == 0,
        },
        {
            "name": "repository_governance_audit",
            "ok": repository_governance.get("status") == "pass"
            and int(repository_governance.get("present_file_count", 0)) >= 6
            and int(repository_governance.get("owned_pattern_count", 0)) >= 9
            and int(repository_governance.get("detected_fixture_count", 0)) >= 8
            and int(repository_governance.get("failed_count", -1)) == 0,
        },
        {
            "name": "developer_runtime_audit",
            "ok": developer_runtime.get("status") == "pass"
            and int(developer_runtime.get("present_file_count", 0)) >= 4
            and int(developer_runtime.get("make_target_count", 0)) >= 8
            and int(developer_runtime.get("detected_fixture_count", 0)) >= 8
            and int(developer_runtime.get("failed_count", -1)) == 0,
        },
        {
            "name": "k8s_manifest_hardening",
            "ok": k8s_hardening.get("status") == "pass"
            and int(k8s_hardening.get("check_count", 0)) >= 11
            and int(k8s_hardening.get("failed_count", -1)) == 0,
        },
        {
            "name": "pod_security_admission_audit",
            "ok": pod_security_admission.get("status") == "pass"
            and int(pod_security_admission.get("namespace_count", 0)) >= 2
            and int(pod_security_admission.get("workload_count", 0)) >= 2
            and int(pod_security_admission.get("restricted_namespace_count", 0)) >= 2
            and int(pod_security_admission.get("restricted_workload_count", 0)) >= 2
            and int(pod_security_admission.get("detected_fixture_count", 0)) >= 10
            and int(pod_security_admission.get("failed_count", -1)) == 0,
        },
        {
            "name": "namespace_resource_audit",
            "ok": namespace_resource.get("status") == "pass"
            and int(namespace_resource.get("namespace_count", 0)) >= 2
            and int(namespace_resource.get("check_count", 0)) >= 8
            and int(namespace_resource.get("detected_fixture_count", 0)) >= 8
            and int(namespace_resource.get("failed_count", -1)) == 0,
        },
        {
            "name": "availability_topology_audit",
            "ok": availability_topology.get("status") == "pass"
            and int(availability_topology.get("workload_count", 0)) >= 2
            and int(availability_topology.get("pdb_count", 0)) >= 2
            and int(availability_topology.get("topology_spread_count", 0)) >= 2
            and int(availability_topology.get("detected_fixture_count", 0)) >= 7
            and int(availability_topology.get("failed_count", -1)) == 0,
        },
        {
            "name": "autoscaling_policy_audit",
            "ok": autoscaling_policy.get("status") == "pass"
            and int(autoscaling_policy.get("hpa_count", 0)) >= 1
            and int(autoscaling_policy.get("metric_count", 0)) >= 2
            and int(autoscaling_policy.get("behavior_policy_count", 0)) >= 3
            and int(autoscaling_policy.get("detected_fixture_count", 0)) >= 9
            and int(autoscaling_policy.get("failed_count", -1)) == 0,
        },
        {
            "name": "scheduling_placement_audit",
            "ok": scheduling_placement.get("status") == "pass"
            and int(scheduling_placement.get("workload_count", 0)) >= 2
            and int(scheduling_placement.get("priority_class_count", 0)) >= 2
            and int(scheduling_placement.get("preferred_affinity_count", 0)) >= 4
            and int(scheduling_placement.get("toleration_count", 0)) >= 2
            and int(scheduling_placement.get("detected_fixture_count", 0)) >= 10
            and int(scheduling_placement.get("failed_count", -1)) == 0,
        },
        {
            "name": "rollout_safety_audit",
            "ok": rollout_safety.get("status") == "pass"
            and int(rollout_safety.get("workload_count", 0)) >= 2
            and int(rollout_safety.get("rolling_update_count", 0)) >= 1
            and int(rollout_safety.get("recreate_count", 0)) >= 1
            and int(rollout_safety.get("timing_guard_count", 0)) >= 2
            and int(rollout_safety.get("termination_window_count", 0)) >= 2
            and int(rollout_safety.get("detected_fixture_count", 0)) >= 12
            and int(rollout_safety.get("failed_count", -1)) == 0,
        },
        {
            "name": "config_rollout_audit",
            "ok": config_rollout.get("status") == "pass"
            and int(config_rollout.get("config_map_count", 0)) >= 1
            and int(config_rollout.get("deployment_count", 0)) >= 1
            and int(config_rollout.get("checksum_annotation_count", 0)) >= 1
            and int(config_rollout.get("read_only_config_mount_count", 0)) >= 1
            and int(config_rollout.get("secret_marker_count", -1)) == 0
            and int(config_rollout.get("detected_fixture_count", 0)) >= 10
            and int(config_rollout.get("failed_count", -1)) == 0,
        },
        {
            "name": "network_boundary_audit",
            "ok": network_boundary.get("status") == "pass"
            and int(network_boundary.get("network_policy_count", 0)) >= 2
            and int(network_boundary.get("egress_rule_count", 0)) >= 2
            and int(network_boundary.get("detected_fixture_count", 0)) >= 10
            and int(network_boundary.get("failed_count", -1)) == 0,
        },
        {
            "name": "collector_self_observability_audit",
            "ok": collector_self_observability.get("status") == "pass"
            and int(collector_self_observability.get("receiver_count", 0)) >= 3
            and int(collector_self_observability.get("self_metrics_target_count", 0)) >= 1
            and int(collector_self_observability.get("scrape_job_count", 0)) >= 1
            and int(collector_self_observability.get("detected_fixture_count", 0)) >= 10
            and int(collector_self_observability.get("failed_count", -1)) == 0,
        },
        {
            "name": "telemetry_sampling_audit",
            "ok": telemetry_sampling.get("status") == "pass"
            and int(telemetry_sampling.get("policy_count", 0)) >= 5
            and int(telemetry_sampling.get("critical_policy_count", 0)) >= 4
            and float(telemetry_sampling.get("baseline_sampling_percentage", 999999.0)) <= 5.0
            and int(telemetry_sampling.get("detected_fixture_count", 0)) >= 10
            and int(telemetry_sampling.get("failed_count", -1)) == 0,
        },
        {
            "name": "workload_identity_audit",
            "ok": workload_identity.get("status") == "pass"
            and int(workload_identity.get("check_count", 0)) >= 8
            and int(workload_identity.get("identity_boundary_count", 0)) >= 2
            and int(workload_identity.get("detected_fixture_count", 0)) >= 8
            and int(workload_identity.get("failed_count", -1)) == 0,
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
            "name": "model_release_safety_audit",
            "ok": model_release_safety.get("status") == "pass"
            and int(model_release_safety.get("release_count", 0)) >= 2
            and int(model_release_safety.get("candidate_count", 0)) >= 1
            and int(model_release_safety.get("blocked_candidate_count", 0)) >= 1
            and int(model_release_safety.get("detected_fixture_count", 0)) >= 7
            and int(model_release_safety.get("failed_count", -1)) == 0,
        },
        {
            "name": "shadow_traffic_replay_audit",
            "ok": shadow_traffic_replay.get("status") == "pass"
            and int(shadow_traffic_replay.get("replay_count", 0)) >= 2
            and int(shadow_traffic_replay.get("candidate_replay_count", 0)) >= 1
            and int(shadow_traffic_replay.get("blocked_shadow_count", 0)) >= 1
            and int(shadow_traffic_replay.get("detected_fixture_count", 0)) >= 7
            and int(shadow_traffic_replay.get("failed_count", -1)) == 0,
        },
        {
            "name": "accelerator_quota_fairness_audit",
            "ok": accelerator_quota.get("status") == "pass"
            and int(accelerator_quota.get("quota_count", 0)) >= 5
            and int(accelerator_quota.get("candidate_quota_count", 0)) >= 1
            and int(accelerator_quota.get("protected_tier_count", 0)) >= 2
            and int(accelerator_quota.get("detected_fixture_count", 0)) >= 7
            and int(accelerator_quota.get("failed_count", -1)) == 0,
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
            "name": "regional_failover_audit",
            "ok": regional_failover.get("status") == "pass"
            and int(regional_failover.get("event_count", 0)) >= 5
            and int(regional_failover.get("standby_region_count", 0)) >= 2
            and int(regional_failover.get("detected_fixture_count", 0)) >= 5
            and int(regional_failover.get("failed_count", -1)) == 0,
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
            "name": "evidence_schema_audit",
            "ok": evidence_schema.get("status") == "pass"
            and int(evidence_schema.get("artifact_count", 0)) >= 10
            and int(evidence_schema.get("required_field_count", 0)) >= 80
            and int(evidence_schema.get("required_check_count", 0)) >= 60
            and int(evidence_schema.get("detected_fixture_count", 0)) >= 10
            and int(evidence_schema.get("failed_count", -1)) == 0,
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
            and int(evidence_provenance.get("artifact_count", 0)) >= 104
            and int(evidence_provenance.get("source_input_count", 0)) >= 87
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
        "policy, policy regression fixtures, supply-chain audit, CI",
        "governance, repository governance, developer runtime governance, Kubernetes manifest hardening, Pod Security Admission governance, namespace resource governance, availability",
        "topology governance, autoscaling policy governance, scheduling",
        "placement governance, rollout safety governance, config rollout governance, network boundary governance, collector self-observability, telemetry sampling",
        "governance, Workload Identity audit, admission policy simulation,",
        "SLO alerting rules,",
        "Grafana dashboard coverage, OpenSLO contract, observability drift",
        "detection,",
        "telemetry redaction, telemetry cost budget, error-budget accounting,",
        "rollback drill coverage, post-incident review coverage, incident",
        "response drill coverage, dependency contract coverage, synthetic",
        "probe coverage, model release safety coverage, shadow traffic replay",
        "coverage, accelerator quota fairness coverage, load-shedding policy",
        "coverage, regional failover coverage,",
        "waiver governance, evidence schema contracts, disaster recovery",
        "drill coverage, evidence provenance, and committed evidence are",
        "present and internally",
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
    parser.add_argument("--ci-governance", default="out/ci-governance-audit/ci-governance-audit.json")
    parser.add_argument("--repository-governance", default="out/repository-governance-audit/repository-governance-audit.json")
    parser.add_argument("--developer-runtime", default="out/developer-runtime-audit/developer-runtime-audit.json")
    parser.add_argument("--k8s-hardening", default="out/k8s-hardening-audit/k8s-hardening-audit.json")
    parser.add_argument("--pod-security-admission", default="out/pod-security-admission-audit/pod-security-admission-audit.json")
    parser.add_argument("--namespace-resource", default="out/namespace-resource-audit/namespace-resource-audit.json")
    parser.add_argument("--availability-topology", default="out/availability-topology-audit/availability-topology-audit.json")
    parser.add_argument("--autoscaling-policy", default="out/autoscaling-policy-audit/autoscaling-policy-audit.json")
    parser.add_argument("--scheduling-placement", default="out/scheduling-placement-audit/scheduling-placement-audit.json")
    parser.add_argument("--rollout-safety", default="out/rollout-safety-audit/rollout-safety-audit.json")
    parser.add_argument("--config-rollout", default="out/config-rollout-audit/config-rollout-audit.json")
    parser.add_argument("--network-boundary", default="out/network-boundary-audit/network-boundary-audit.json")
    parser.add_argument("--collector-self-observability", default="out/collector-self-observability-audit/collector-self-observability-audit.json")
    parser.add_argument("--telemetry-sampling", default="out/telemetry-sampling-audit/telemetry-sampling-audit.json")
    parser.add_argument("--workload-identity", default="out/workload-identity-audit/workload-identity-audit.json")
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
    parser.add_argument("--model-release-safety", default="out/model-release-safety-audit/model-release-safety-audit.json")
    parser.add_argument("--shadow-traffic-replay", default="out/shadow-traffic-replay-audit/shadow-traffic-replay-audit.json")
    parser.add_argument("--accelerator-quota", default="out/accelerator-quota-fairness-audit/accelerator-quota-fairness-audit.json")
    parser.add_argument("--load-shedding-policy", default="out/load-shedding-policy-audit/load-shedding-policy-audit.json")
    parser.add_argument("--regional-failover", default="out/regional-failover-audit/regional-failover-audit.json")
    parser.add_argument("--release-waiver-governance", default="out/release-waiver-governance/release-waiver-governance.json")
    parser.add_argument("--evidence-schema", default="out/evidence-schema-audit/evidence-schema-audit.json")
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
        ci_governance=load_json(Path(args.ci_governance)),
        repository_governance=load_json(Path(args.repository_governance)),
        developer_runtime=load_json(Path(args.developer_runtime)),
        k8s_hardening=load_json(Path(args.k8s_hardening)),
        pod_security_admission=load_json(Path(args.pod_security_admission)),
        namespace_resource=load_json(Path(args.namespace_resource)),
        availability_topology=load_json(Path(args.availability_topology)),
        autoscaling_policy=load_json(Path(args.autoscaling_policy)),
        scheduling_placement=load_json(Path(args.scheduling_placement)),
        rollout_safety=load_json(Path(args.rollout_safety)),
        config_rollout=load_json(Path(args.config_rollout)),
        network_boundary=load_json(Path(args.network_boundary)),
        collector_self_observability=load_json(Path(args.collector_self_observability)),
        telemetry_sampling=load_json(Path(args.telemetry_sampling)),
        workload_identity=load_json(Path(args.workload_identity)),
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
        model_release_safety=load_json(Path(args.model_release_safety)),
        shadow_traffic_replay=load_json(Path(args.shadow_traffic_replay)),
        accelerator_quota=load_json(Path(args.accelerator_quota)),
        load_shedding_policy=load_json(Path(args.load_shedding_policy)),
        regional_failover=load_json(Path(args.regional_failover)),
        release_waiver_governance=load_json(Path(args.release_waiver_governance)),
        evidence_schema=load_json(Path(args.evidence_schema)),
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
