from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import release_readiness


def ready_inputs(evidence_dir: Path) -> dict:
    scenarios = [f"scenario_{index}" for index in range(5)]
    for name in release_readiness.REQUIRED_EVIDENCE:
        (evidence_dir / name).write_text("evidence\n", encoding="utf-8")
    return {
        "gate": {"status": "pass"},
        "capacity": {
            "scenarios": [
                {
                    "scenario": scenario,
                    "warnings": [],
                }
                for scenario in scenarios
            ]
        },
        "runbooks": {
            "runbooks": [
                {
                    "scenario": scenario,
                }
                for scenario in scenarios
            ]
        },
        "advanced": {"problems": [{"id": f"C0{index}"} for index in range(5)]},
        "detailed": {"problems": [{"id": f"C1{index}"} for index in range(5)]},
        "policy": {
            "status": "generated",
            "decision": "promote",
            "control_count": 8,
        },
        "policy_regression": {
            "status": "pass",
            "fixture_count": 8,
            "failed_count": 0,
            "controls_under_test": sorted(release_readiness.REQUIRED_POLICY_REGRESSION_CONTROLS),
        },
        "supply_chain": {
            "status": "pass",
            "image_count": 2,
            "digest_pinned_count": 2,
            "failed_count": 0,
        },
        "oss_license": {
            "status": "pass",
            "action_count": 2,
            "image_count": 4,
            "third_party_reference_count": 6,
            "detected_fixture_count": 6,
            "failed_count": 0,
        },
        "secret_hygiene": {
            "status": "pass",
            "scanned_file_count": 310,
            "evidence_file_count": 126,
            "pattern_count": 6,
            "finding_count": 0,
            "skipped_file_count": 0,
            "detected_fixture_count": 6,
            "failed_count": 0,
        },
        "sbom_inventory": {
            "status": "pass",
            "component_count": 8,
            "action_count": 2,
            "image_count": 4,
            "runtime_count": 2,
            "source_path_count": 9,
            "detected_fixture_count": 6,
            "failed_count": 0,
        },
        "security_response": {
            "status": "pass",
            "present_file_count": 3,
            "severity_tier_count": 4,
            "critical_triage_hours": 24,
            "detected_fixture_count": 8,
            "failed_count": 0,
        },
        "ci_governance": {
            "status": "pass",
            "workflow_count": 1,
            "job_count": 1,
            "action_count": 2,
            "hardened_action_count": 2,
            "detected_fixture_count": 8,
            "failed_count": 0,
        },
        "repository_governance": {
            "status": "pass",
            "required_file_count": 6,
            "present_file_count": 6,
            "codeowner_pattern_count": 9,
            "owned_pattern_count": 9,
            "detected_fixture_count": 8,
            "failed_count": 0,
        },
        "developer_runtime": {
            "status": "pass",
            "required_file_count": 4,
            "present_file_count": 4,
            "make_target_count": 8,
            "phony_target_count": 8,
            "detected_fixture_count": 8,
            "failed_count": 0,
        },
        "k8s_hardening": {
            "status": "pass",
            "check_count": 11,
            "failed_count": 0,
        },
        "pod_security_admission": {
            "status": "pass",
            "namespace_count": 2,
            "workload_count": 2,
            "restricted_namespace_count": 2,
            "restricted_workload_count": 2,
            "detected_fixture_count": 10,
            "failed_count": 0,
        },
        "namespace_resource": {
            "status": "pass",
            "namespace_count": 2,
            "check_count": 8,
            "detected_fixture_count": 8,
            "failed_count": 0,
        },
        "availability_topology": {
            "status": "pass",
            "workload_count": 2,
            "pdb_count": 2,
            "topology_spread_count": 2,
            "detected_fixture_count": 7,
            "failed_count": 0,
        },
        "autoscaling_policy": {
            "status": "pass",
            "hpa_count": 1,
            "metric_count": 2,
            "behavior_policy_count": 3,
            "detected_fixture_count": 9,
            "failed_count": 0,
        },
        "scheduling_placement": {
            "status": "pass",
            "workload_count": 2,
            "priority_class_count": 2,
            "preferred_affinity_count": 4,
            "toleration_count": 2,
            "detected_fixture_count": 10,
            "failed_count": 0,
        },
        "rollout_safety": {
            "status": "pass",
            "workload_count": 2,
            "rolling_update_count": 1,
            "recreate_count": 1,
            "timing_guard_count": 2,
            "termination_window_count": 2,
            "detected_fixture_count": 12,
            "failed_count": 0,
        },
        "config_rollout": {
            "status": "pass",
            "config_map_count": 1,
            "deployment_count": 1,
            "checksum_annotation_count": 1,
            "read_only_config_mount_count": 1,
            "secret_marker_count": 0,
            "detected_fixture_count": 10,
            "failed_count": 0,
        },
        "network_boundary": {
            "status": "pass",
            "network_policy_count": 2,
            "egress_rule_count": 2,
            "detected_fixture_count": 10,
            "failed_count": 0,
        },
        "collector_self_observability": {
            "status": "pass",
            "receiver_count": 3,
            "self_metrics_target_count": 1,
            "scrape_job_count": 1,
            "detected_fixture_count": 10,
            "failed_count": 0,
        },
        "telemetry_sampling": {
            "status": "pass",
            "policy_count": 5,
            "critical_policy_count": 4,
            "baseline_sampling_percentage": 2,
            "detected_fixture_count": 10,
            "failed_count": 0,
        },
        "workload_identity": {
            "status": "pass",
            "check_count": 8,
            "identity_boundary_count": 2,
            "detected_fixture_count": 9,
            "failed_count": 0,
        },
        "admission_policy": {
            "status": "pass",
            "policy_check_count": 12,
            "allowed_deployment_count": 2,
            "denied_fixture_count": 10,
            "failed_count": 0,
        },
        "alerting": {
            "status": "pass",
            "rule_count": 5,
            "failed_count": 0,
        },
        "dashboard": {
            "status": "pass",
            "panel_count": 6,
            "failed_count": 0,
        },
        "openslo": {
            "status": "pass",
            "objective_target": 99.5,
            "scenario_count": 5,
            "failed_count": 0,
        },
        "observability_drift": {
            "status": "pass",
            "required_scenario_count": 5,
            "surface_count": 4,
            "detected_fixture_count": 5,
            "failed_count": 0,
        },
        "telemetry_redaction": {
            "status": "pass",
            "payload_count": 5,
            "redaction_violation_count": 0,
            "failed_count": 0,
        },
        "telemetry_cost": {
            "status": "pass",
            "scenario_count": 5,
            "daily_ingest_gib": 11.0,
            "failed_count": 0,
        },
        "error_budget": {
            "status": "pass",
            "scenario_count": 5,
            "non_green_count": 4,
            "failed_count": 0,
            "decision_counts": {
                "within_budget": 1,
                "manual_review_required": 2,
                "budget_exhausted": 2,
            },
        },
        "rollback_drill": {
            "status": "pass",
            "drill_count": 4,
            "rollback_required_count": 2,
            "failed_count": 0,
        },
        "post_incident_review": {
            "status": "pass",
            "review_count": 4,
            "action_item_count": 8,
            "failed_count": 0,
        },
        "incident_response_drill": {
            "status": "pass",
            "response_count": 5,
            "incident_response_count": 4,
            "page_count": 4,
            "ticket_count": 1,
            "detected_fixture_count": 5,
            "failed_count": 0,
        },
        "dependency_contract": {
            "status": "pass",
            "dependency_count": 4,
            "incident_contract_count": 4,
            "dominant_dependency_count": 3,
            "detected_fixture_count": 5,
            "failed_count": 0,
        },
        "synthetic_probe": {
            "status": "pass",
            "probe_count": 5,
            "incident_probe_count": 4,
            "preflight_block_count": 2,
            "detected_fixture_count": 5,
            "failed_count": 0,
        },
        "model_release_safety": {
            "status": "pass",
            "release_count": 2,
            "candidate_count": 1,
            "blocked_candidate_count": 1,
            "detected_fixture_count": 7,
            "failed_count": 0,
        },
        "shadow_traffic_replay": {
            "status": "pass",
            "replay_count": 2,
            "candidate_replay_count": 1,
            "blocked_shadow_count": 1,
            "detected_fixture_count": 7,
            "failed_count": 0,
        },
        "accelerator_quota": {
            "status": "pass",
            "quota_count": 5,
            "candidate_quota_count": 1,
            "protected_tier_count": 2,
            "detected_fixture_count": 7,
            "failed_count": 0,
        },
        "load_shedding_policy": {
            "status": "pass",
            "action_count": 5,
            "protective_action_count": 4,
            "detected_fixture_count": 5,
            "failed_count": 0,
        },
        "regional_failover": {
            "status": "pass",
            "event_count": 5,
            "standby_region_count": 2,
            "detected_fixture_count": 5,
            "failed_count": 0,
        },
        "release_waiver_governance": {
            "status": "pass",
            "waiver_count": 4,
            "conditional_approval_count": 2,
            "denied_override_count": 2,
            "invalid_waiver_count": 0,
            "unsafe_approved_count": 0,
            "failed_count": 0,
        },
        "release_control_ownership": {
            "status": "pass",
            "control_count": 53,
            "release_check_count": 53,
            "covered_release_check_count": 53,
            "tier0_count": 30,
            "every_release_count": 41,
            "owner_group_count": 5,
            "detected_fixture_count": 6,
            "failed_count": 0,
        },
        "control_traceability": {
            "status": "pass",
            "control_count": 48,
            "evidence_file_count": 97,
            "source_input_count": 48,
            "policy_input_count": 49,
            "test_file_count": 48,
            "detected_fixture_count": 6,
            "failed_count": 0,
        },
        "evidence_pipeline": {
            "status": "pass",
            "step_count": 55,
            "dependency_count": 65,
            "artifact_dependency_count": 65,
            "detected_fixture_count": 4,
            "failed_count": 0,
        },
        "evidence_schema": {
            "status": "pass",
            "artifact_count": 11,
            "required_field_count": 90,
            "required_check_count": 70,
            "detected_fixture_count": 11,
            "failed_count": 0,
        },
        "disaster_recovery_drill": {
            "status": "pass",
            "artifact_count": 73,
            "restored_count": 73,
            "hash_match_count": 73,
            "detected_fixture_count": 4,
            "estimated_restore_minutes": 7,
            "rto_minutes": 15,
            "failed_count": 0,
        },
        "evidence_provenance": {
            "status": "pass",
            "artifact_count": 127,
            "source_input_count": 119,
            "failed_count": 0,
        },
        "evidence_dir": evidence_dir,
    }


class ReleaseReadinessTest(unittest.TestCase):
    def test_requires_policy_regression_control_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}
            self.assertEqual("pass", report["status"])
            self.assertTrue(checks["policy_regression_suite"])

            inputs["policy_regression"]["controls_under_test"] = ["burn_rate"]
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}
            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["policy_regression_suite"])

    def test_requires_k8s_manifest_hardening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["k8s_hardening"]["failed_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["k8s_manifest_hardening"])

    def test_requires_pod_security_admission_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["pod_security_admission"]["restricted_namespace_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["pod_security_admission_audit"])

    def test_requires_supply_chain_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["supply_chain"]["digest_pinned_count"] = 0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["supply_chain_audit"])

    def test_requires_ci_governance_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["ci_governance"]["hardened_action_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["ci_governance_audit"])

    def test_requires_oss_license_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["oss_license"]["third_party_reference_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["oss_license_audit"])

    def test_requires_secret_hygiene_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["secret_hygiene"]["finding_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["secret_hygiene_audit"])

    def test_requires_sbom_inventory_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["sbom_inventory"]["component_count"] = 4
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["sbom_inventory_audit"])

    def test_requires_security_response_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["security_response"]["critical_triage_hours"] = 48
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["security_response_audit"])

    def test_requires_repository_governance_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["repository_governance"]["owned_pattern_count"] = 3
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["repository_governance_audit"])

    def test_requires_developer_runtime_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["developer_runtime"]["make_target_count"] = 3
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["developer_runtime_audit"])

    def test_requires_workload_identity_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["workload_identity"]["identity_boundary_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["workload_identity_audit"])

    def test_requires_namespace_resource_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["namespace_resource"]["detected_fixture_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["namespace_resource_audit"])

    def test_requires_availability_topology_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["availability_topology"]["topology_spread_count"] = 0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["availability_topology_audit"])

    def test_requires_autoscaling_policy_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["autoscaling_policy"]["metric_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["autoscaling_policy_audit"])

    def test_requires_scheduling_placement_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["scheduling_placement"]["priority_class_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["scheduling_placement_audit"])

    def test_requires_rollout_safety_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["rollout_safety"]["detected_fixture_count"] = 3
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["rollout_safety_audit"])

    def test_requires_config_rollout_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["config_rollout"]["checksum_annotation_count"] = 0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["config_rollout_audit"])

    def test_requires_network_boundary_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["network_boundary"]["network_policy_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["network_boundary_audit"])

    def test_requires_collector_self_observability_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["collector_self_observability"]["self_metrics_target_count"] = 0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["collector_self_observability_audit"])

    def test_requires_telemetry_sampling_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["telemetry_sampling"]["baseline_sampling_percentage"] = 50
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["telemetry_sampling_audit"])

    def test_requires_admission_policy_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["admission_policy"]["denied_fixture_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["admission_policy_audit"])

    def test_requires_slo_alerting_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["alerting"]["rule_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["slo_alerting_rules"])

    def test_requires_grafana_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["dashboard"]["panel_count"] = 3
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["grafana_dashboard"])

    def test_requires_openslo_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["openslo"]["scenario_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["openslo_contract"])

    def test_requires_observability_drift_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["observability_drift"]["detected_fixture_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["observability_drift_audit"])

    def test_requires_error_budget_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["error_budget"]["non_green_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["error_budget_ledger"])

    def test_requires_telemetry_redaction_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["telemetry_redaction"]["redaction_violation_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["telemetry_redaction_audit"])

    def test_requires_telemetry_cost_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["telemetry_cost"]["daily_ingest_gib"] = 99.0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["telemetry_cost_budget"])

    def test_requires_rollback_drill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["rollback_drill"]["rollback_required_count"] = 0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["rollback_drill"])

    def test_requires_post_incident_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["post_incident_review"]["action_item_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["post_incident_review"])

    def test_requires_incident_response_drill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["incident_response_drill"]["detected_fixture_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["incident_response_drill"])

    def test_requires_dependency_contract_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["dependency_contract"]["detected_fixture_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["dependency_contract_audit"])

    def test_requires_synthetic_probe_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["synthetic_probe"]["preflight_block_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["synthetic_probe_audit"])

    def test_requires_load_shedding_policy_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["load_shedding_policy"]["protective_action_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["load_shedding_policy_audit"])

    def test_requires_model_release_safety_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["model_release_safety"]["blocked_candidate_count"] = 0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["model_release_safety_audit"])

    def test_requires_shadow_traffic_replay_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["shadow_traffic_replay"]["blocked_shadow_count"] = 0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["shadow_traffic_replay_audit"])

    def test_requires_accelerator_quota_fairness_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["accelerator_quota"]["protected_tier_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["accelerator_quota_fairness_audit"])

    def test_requires_regional_failover_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["regional_failover"]["standby_region_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["regional_failover_audit"])

    def test_requires_release_waiver_governance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["release_waiver_governance"]["unsafe_approved_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["release_waiver_governance"])

    def test_requires_disaster_recovery_drill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["disaster_recovery_drill"]["hash_match_count"] = 29
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["disaster_recovery_drill"])

    def test_requires_release_control_ownership_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["release_control_ownership"]["owner_group_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["release_control_ownership_audit"])

    def test_requires_control_traceability_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["control_traceability"]["evidence_file_count"] = 20
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["control_traceability_audit"])

    def test_requires_evidence_pipeline_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["evidence_pipeline"]["dependency_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["evidence_pipeline_audit"])

    def test_requires_evidence_schema_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["evidence_schema"]["detected_fixture_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["evidence_schema_audit"])

    def test_requires_evidence_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["evidence_provenance"]["artifact_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["evidence_provenance"])


if __name__ == "__main__":
    unittest.main()
