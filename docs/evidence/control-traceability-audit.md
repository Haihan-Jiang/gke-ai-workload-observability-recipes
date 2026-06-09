# Control Traceability Audit

Overall status: **PASS**

This audit proves that configured release-readiness controls trace back to
committed evidence, source code, policy/config inputs, and tests.

## Summary

| Metric | Value |
| --- | ---: |
| Controls | 52 |
| Release checks | 57 |
| Evidence files | 105 |
| Source inputs | 55 |
| Policy inputs | 53 |
| Test files | 52 |
| Detected fixtures | 6 |

## Checks

| Check | Status |
| --- | --- |
| `control_inventory` | PASS |
| `release_gate_linkage` | PASS |
| `traceability_depth` | PASS |
| `evidence_files` | PASS |
| `source_inputs` | PASS |
| `policy_inputs` | PASS |
| `test_coverage` | PASS |
| `negative_fixture_coverage` | PASS |

## Controls

| Control | Release Check | Evidence Files |
| --- | --- | ---: |
| `advanced_problem_coverage` | `advanced_problem_coverage` | 2 |
| `detailed_problem_coverage` | `detailed_problem_coverage` | 2 |
| `deployment_policy` | `deployment_policy` | 2 |
| `policy_regression_suite` | `policy_regression_suite` | 2 |
| `supply_chain_audit` | `supply_chain_audit` | 2 |
| `oss_license_audit` | `oss_license_audit` | 2 |
| `secret_hygiene_audit` | `secret_hygiene_audit` | 2 |
| `sbom_inventory_audit` | `sbom_inventory_audit` | 3 |
| `security_response_audit` | `security_response_audit` | 2 |
| `ci_governance_audit` | `ci_governance_audit` | 2 |
| `repository_governance_audit` | `repository_governance_audit` | 2 |
| `developer_runtime_audit` | `developer_runtime_audit` | 2 |
| `k8s_manifest_hardening` | `k8s_manifest_hardening` | 2 |
| `pod_security_admission_audit` | `pod_security_admission_audit` | 2 |
| `kubernetes_api_compatibility_audit` | `kubernetes_api_compatibility_audit` | 2 |
| `private_cluster_admission_boundary_audit` | `private_cluster_admission_boundary_audit` | 2 |
| `namespace_resource_audit` | `namespace_resource_audit` | 2 |
| `availability_topology_audit` | `availability_topology_audit` | 2 |
| `autoscaling_policy_audit` | `autoscaling_policy_audit` | 2 |
| `scheduling_placement_audit` | `scheduling_placement_audit` | 2 |
| `rollout_safety_audit` | `rollout_safety_audit` | 2 |
| `config_rollout_audit` | `config_rollout_audit` | 2 |
| `network_boundary_audit` | `network_boundary_audit` | 2 |
| `collector_self_observability_audit` | `collector_self_observability_audit` | 2 |
| `telemetry_exporter_authority_audit` | `telemetry_exporter_authority_audit` | 2 |
| `telemetry_sampling_audit` | `telemetry_sampling_audit` | 2 |
| `workload_identity_audit` | `workload_identity_audit` | 2 |
| `admission_policy_audit` | `admission_policy_audit` | 2 |
| `slo_alerting_rules` | `slo_alerting_rules` | 2 |
| `grafana_dashboard` | `grafana_dashboard` | 2 |
| `openslo_contract` | `openslo_contract` | 2 |
| `observability_drift_audit` | `observability_drift_audit` | 2 |
| `telemetry_redaction_audit` | `telemetry_redaction_audit` | 2 |
| `telemetry_cost_budget` | `telemetry_cost_budget` | 2 |
| `error_budget_ledger` | `error_budget_ledger` | 2 |
| `rollback_drill` | `rollback_drill` | 2 |
| `post_incident_review` | `post_incident_review` | 2 |
| `incident_response_drill` | `incident_response_drill` | 2 |
| `dependency_contract_audit` | `dependency_contract_audit` | 2 |
| `synthetic_probe_audit` | `synthetic_probe_audit` | 2 |
| `model_release_safety_audit` | `model_release_safety_audit` | 2 |
| `staged_telemetry_validation_audit` | `staged_telemetry_validation_audit` | 2 |
| `shadow_traffic_replay_audit` | `shadow_traffic_replay_audit` | 2 |
| `accelerator_quota_fairness_audit` | `accelerator_quota_fairness_audit` | 2 |
| `load_shedding_policy_audit` | `load_shedding_policy_audit` | 2 |
| `regional_failover_audit` | `regional_failover_audit` | 2 |
| `release_waiver_governance` | `release_waiver_governance` | 2 |
| `release_control_ownership_audit` | `release_control_ownership_audit` | 2 |
| `evidence_pipeline_audit` | `evidence_pipeline_audit` | 2 |
| `evidence_schema_audit` | `evidence_schema_audit` | 2 |
| `disaster_recovery_drill` | `disaster_recovery_drill` | 2 |
| `evidence_provenance` | `evidence_provenance` | 2 |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_control_entry` | `control_inventory` | yes |
| `unknown_release_check` | `release_gate_linkage` | yes |
| `missing_evidence_file` | `evidence_files` | yes |
| `missing_source_input` | `source_inputs` | yes |
| `missing_policy_input` | `policy_inputs` | yes |
| `missing_test_file` | `test_coverage` | yes |
