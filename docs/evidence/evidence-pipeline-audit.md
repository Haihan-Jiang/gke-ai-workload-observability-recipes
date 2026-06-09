# Evidence Pipeline Audit

Overall status: **PASS**

This audit checks that generated evidence steps run after their
producer steps and before their consumers, so release gates cannot
accidentally read stale committed artifacts.

## Summary

| Metric | Value |
| --- | ---: |
| Steps | 51 |
| Required steps | 51 |
| Dependencies | 52 |
| Artifact dependencies | 52 |
| Detected fixtures | 4 |

## Checks

| Check | Status |
| --- | --- |
| `step_inventory` | PASS |
| `dependency_inventory` | PASS |
| `dependency_order` | PASS |
| `artifact_dependency_coverage` | PASS |
| `negative_fixture_coverage` | PASS |

## Critical Dependencies

| Producer | Consumer | Ordered |
| --- | --- | --- |
| `incident_replay` | `reliability_gate` | yes |
| `incident_replay` | `capacity_planner` | yes |
| `reliability_gate` | `runbook_generator` | yes |
| `incident_replay` | `advanced_reliability` | yes |
| `incident_replay` | `detailed_reliability` | yes |
| `reliability_gate` | `deployment_policy` | yes |
| `advanced_reliability` | `deployment_policy` | yes |
| `detailed_reliability` | `deployment_policy` | yes |
| `alerting_rules` | `observability_drift_audit` | yes |
| `grafana_dashboard` | `observability_drift_audit` | yes |
| `openslo_contract` | `observability_drift_audit` | yes |
| `runbook_generator` | `observability_drift_audit` | yes |
| `openslo_contract` | `error_budget_ledger` | yes |
| `runbook_generator` | `rollback_drill` | yes |
| `deployment_policy` | `rollback_drill` | yes |
| `error_budget_ledger` | `rollback_drill` | yes |
| `advanced_reliability` | `post_incident_review` | yes |
| `rollback_drill` | `post_incident_review` | yes |
| `post_incident_review` | `incident_response_drill` | yes |
| `alerting_rules` | `incident_response_drill` | yes |
| `detailed_reliability` | `dependency_contract_audit` | yes |
| `dependency_contract_audit` | `synthetic_probe_audit` | yes |
| `incident_response_drill` | `synthetic_probe_audit` | yes |
| `synthetic_probe_audit` | `model_release_safety_audit` | yes |
| `model_release_safety_audit` | `evidence_pipeline_audit` | yes |
| `evidence_pipeline_audit` | `evidence_schema_audit` | yes |
| `developer_runtime_audit` | `evidence_schema_audit` | yes |
| `pod_security_admission_audit` | `evidence_schema_audit` | yes |
| `synthetic_probe_audit` | `evidence_schema_audit` | yes |
| `model_release_safety_audit` | `evidence_schema_audit` | yes |
| `telemetry_redaction_audit` | `shadow_traffic_replay_audit` | yes |
| `model_release_safety_audit` | `shadow_traffic_replay_audit` | yes |
| `synthetic_probe_audit` | `load_shedding_policy_audit` | yes |
| `load_shedding_policy_audit` | `accelerator_quota_fairness_audit` | yes |
| `shadow_traffic_replay_audit` | `accelerator_quota_fairness_audit` | yes |
| `release_waiver_governance` | `disaster_recovery_drill` | yes |
| `evidence_schema_audit` | `disaster_recovery_drill` | yes |
| `disaster_recovery_drill` | `regional_failover_audit` | yes |
| `load_shedding_policy_audit` | `regional_failover_audit` | yes |
| `regional_failover_audit` | `evidence_provenance` | yes |
| `regional_failover_audit` | `control_traceability_audit` | yes |
| `release_control_ownership_audit` | `control_traceability_audit` | yes |
| `evidence_schema_audit` | `control_traceability_audit` | yes |
| `evidence_pipeline_audit` | `control_traceability_audit` | yes |
| `control_traceability_audit` | `evidence_provenance` | yes |
| `render_incident_evidence` | `evidence_provenance` | yes |
| `evidence_provenance` | `release_readiness` | yes |
| `regional_failover_audit` | `release_readiness` | yes |
| `control_traceability_audit` | `release_readiness` | yes |
| `release_control_ownership_audit` | `release_readiness` | yes |
| `disaster_recovery_drill` | `release_readiness` | yes |
| `evidence_schema_audit` | `release_readiness` | yes |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `regional_before_disaster_recovery` | `dependency_order` | yes |
| `provenance_before_render_index` | `dependency_order` | yes |
| `missing_release_readiness_step` | `step_inventory` | yes |
| `duplicate_schema_audit_step` | `step_inventory` | yes |
