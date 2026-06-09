# Evidence Pipeline Audit

Overall status: **PASS**

This audit checks that generated evidence steps run after their
producer steps and before their consumers, so release gates cannot
accidentally read stale committed artifacts.

## Summary

| Metric | Value |
| --- | ---: |
| Steps | 72 |
| Required steps | 72 |
| Dependencies | 204 |
| Artifact dependencies | 204 |
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
| `incident_replay` | `replay_source_contract_audit` | yes |
| `incident_replay` | `replay_source_contract_audit` | yes |
| `replay_source_contract_audit` | `reliability_gate` | yes |
| `replay_source_contract_audit` | `advanced_reliability` | yes |
| `replay_source_contract_audit` | `detailed_reliability` | yes |
| `replay_source_contract_audit` | `telemetry_redaction_audit` | yes |
| `replay_source_contract_audit` | `telemetry_cost_budget` | yes |
| `replay_source_contract_audit` | `evidence_provenance` | yes |
| `replay_source_contract_audit` | `control_traceability_audit` | yes |
| `replay_source_contract_audit` | `release_readiness` | yes |
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
| `advanced_reliability` | `staged_telemetry_validation_audit` | yes |
| `advanced_reliability` | `staged_telemetry_validation_audit` | yes |
| `telemetry_redaction_audit` | `staged_telemetry_validation_audit` | yes |
| `telemetry_cost_budget` | `staged_telemetry_validation_audit` | yes |
| `telemetry_exporter_authority_audit` | `staged_telemetry_validation_audit` | yes |
| `synthetic_probe_audit` | `staged_telemetry_validation_audit` | yes |
| `model_release_safety_audit` | `staged_telemetry_validation_audit` | yes |
| `staged_telemetry_validation_audit` | `evidence_pipeline_audit` | yes |
| `oss_license_audit` | `control_traceability_audit` | yes |
| `secret_hygiene_audit` | `control_traceability_audit` | yes |
| `sbom_inventory_audit` | `control_traceability_audit` | yes |
| `security_response_audit` | `control_traceability_audit` | yes |
| `kubernetes_api_compatibility_audit` | `control_traceability_audit` | yes |
| `private_cluster_admission_boundary_audit` | `control_traceability_audit` | yes |
| `telemetry_exporter_authority_audit` | `control_traceability_audit` | yes |
| `staged_telemetry_validation_audit` | `control_traceability_audit` | yes |
| `evidence_pipeline_audit` | `validation_contract_audit` | yes |
| `developer_runtime_audit` | `evidence_schema_audit` | yes |
| `pod_security_admission_audit` | `evidence_schema_audit` | yes |
| `kubernetes_api_compatibility_audit` | `evidence_schema_audit` | yes |
| `private_cluster_admission_boundary_audit` | `evidence_schema_audit` | yes |
| `telemetry_exporter_authority_audit` | `evidence_schema_audit` | yes |
| `synthetic_probe_audit` | `evidence_schema_audit` | yes |
| `model_release_safety_audit` | `evidence_schema_audit` | yes |
| `staged_telemetry_validation_audit` | `evidence_schema_audit` | yes |
| `validation_contract_audit` | `evidence_schema_audit` | yes |
| `validation_contract_audit` | `render_incident_evidence` | yes |
| `validation_contract_audit` | `documentation_link_integrity_audit` | yes |
| `telemetry_redaction_audit` | `shadow_traffic_replay_audit` | yes |
| `model_release_safety_audit` | `shadow_traffic_replay_audit` | yes |
| `synthetic_probe_audit` | `load_shedding_policy_audit` | yes |
| `load_shedding_policy_audit` | `accelerator_quota_fairness_audit` | yes |
| `shadow_traffic_replay_audit` | `accelerator_quota_fairness_audit` | yes |
| `release_waiver_governance` | `disaster_recovery_drill` | yes |
| `security_response_audit` | `disaster_recovery_drill` | yes |
| `kubernetes_api_compatibility_audit` | `disaster_recovery_drill` | yes |
| `private_cluster_admission_boundary_audit` | `disaster_recovery_drill` | yes |
| `telemetry_exporter_authority_audit` | `disaster_recovery_drill` | yes |
| `staged_telemetry_validation_audit` | `disaster_recovery_drill` | yes |
| `evidence_schema_audit` | `disaster_recovery_drill` | yes |
| `validation_contract_audit` | `disaster_recovery_drill` | yes |
| `disaster_recovery_drill` | `regional_failover_audit` | yes |
| `load_shedding_policy_audit` | `regional_failover_audit` | yes |
| `regional_failover_audit` | `evidence_provenance` | yes |
| `regional_failover_audit` | `control_traceability_audit` | yes |
| `validation_contract_audit` | `release_control_ownership_audit` | yes |
| `release_control_ownership_audit` | `control_traceability_audit` | yes |
| `evidence_schema_audit` | `control_traceability_audit` | yes |
| `validation_contract_audit` | `control_traceability_audit` | yes |
| `evidence_pipeline_audit` | `control_traceability_audit` | yes |
| `oss_license_audit` | `evidence_provenance` | yes |
| `secret_hygiene_audit` | `evidence_provenance` | yes |
| `sbom_inventory_audit` | `evidence_provenance` | yes |
| `security_response_audit` | `evidence_provenance` | yes |
| `kubernetes_api_compatibility_audit` | `evidence_provenance` | yes |
| `private_cluster_admission_boundary_audit` | `evidence_provenance` | yes |
| `telemetry_exporter_authority_audit` | `evidence_provenance` | yes |
| `staged_telemetry_validation_audit` | `evidence_provenance` | yes |
| `validation_contract_audit` | `evidence_provenance` | yes |
| `render_incident_evidence` | `documentation_link_integrity_audit` | yes |
| `documentation_link_integrity_audit` | `disaster_recovery_drill` | yes |
| `documentation_link_integrity_audit` | `evidence_provenance` | yes |
| `documentation_link_integrity_audit` | `control_traceability_audit` | yes |
| `render_incident_evidence` | `evidence_provenance` | yes |
| `evidence_provenance` | `proof_packet_integrity_audit` | yes |
| `evidence_provenance` | `control_traceability_audit` | yes |
| `proof_packet_integrity_audit` | `control_traceability_audit` | yes |
| `proof_packet_integrity_audit` | `release_readiness` | yes |
| `evidence_provenance` | `release_readiness` | yes |
| `regional_failover_audit` | `release_readiness` | yes |
| `documentation_link_integrity_audit` | `release_readiness` | yes |
| `control_traceability_audit` | `release_readiness` | yes |
| `release_control_ownership_audit` | `release_readiness` | yes |
| `oss_license_audit` | `release_readiness` | yes |
| `secret_hygiene_audit` | `release_readiness` | yes |
| `sbom_inventory_audit` | `release_readiness` | yes |
| `security_response_audit` | `release_readiness` | yes |
| `kubernetes_api_compatibility_audit` | `release_readiness` | yes |
| `private_cluster_admission_boundary_audit` | `release_readiness` | yes |
| `telemetry_exporter_authority_audit` | `release_readiness` | yes |
| `staged_telemetry_validation_audit` | `release_readiness` | yes |
| `disaster_recovery_drill` | `release_readiness` | yes |
| `evidence_schema_audit` | `release_readiness` | yes |
| `validation_contract_audit` | `release_readiness` | yes |
| `replay_source_contract_audit` | `public_claim_evidence_audit` | yes |
| `telemetry_redaction_audit` | `public_claim_evidence_audit` | yes |
| `synthetic_probe_audit` | `public_claim_evidence_audit` | yes |
| `model_release_safety_audit` | `public_claim_evidence_audit` | yes |
| `staged_telemetry_validation_audit` | `public_claim_evidence_audit` | yes |
| `shadow_traffic_replay_audit` | `public_claim_evidence_audit` | yes |
| `accelerator_quota_fairness_audit` | `public_claim_evidence_audit` | yes |
| `load_shedding_policy_audit` | `public_claim_evidence_audit` | yes |
| `release_waiver_governance` | `public_claim_evidence_audit` | yes |
| `evidence_pipeline_audit` | `public_claim_evidence_audit` | yes |
| `validation_contract_audit` | `public_claim_evidence_audit` | yes |
| `maintainer_intake_audit` | `public_claim_evidence_audit` | yes |
| `maintainer_intake_audit` | `render_incident_evidence` | yes |
| `maintainer_intake_audit` | `documentation_link_integrity_audit` | yes |
| `maintainer_intake_audit` | `evidence_schema_audit` | yes |
| `maintainer_intake_audit` | `disaster_recovery_drill` | yes |
| `maintainer_intake_audit` | `evidence_provenance` | yes |
| `maintainer_intake_audit` | `control_traceability_audit` | yes |
| `maintainer_intake_audit` | `release_readiness` | yes |
| `public_claim_evidence_audit` | `disaster_recovery_drill` | yes |
| `public_claim_evidence_audit` | `evidence_provenance` | yes |
| `public_claim_evidence_audit` | `control_traceability_audit` | yes |
| `public_claim_evidence_audit` | `release_readiness` | yes |
| `public_claim_evidence_audit` | `evidence_schema_audit` | yes |
| `public_claim_evidence_audit` | `documentation_link_integrity_audit` | yes |
| `release_notes_contract_audit` | `render_incident_evidence` | yes |
| `release_notes_contract_audit` | `documentation_link_integrity_audit` | yes |
| `release_notes_contract_audit` | `evidence_schema_audit` | yes |
| `release_notes_contract_audit` | `disaster_recovery_drill` | yes |
| `release_notes_contract_audit` | `evidence_provenance` | yes |
| `release_notes_contract_audit` | `control_traceability_audit` | yes |
| `release_notes_contract_audit` | `release_readiness` | yes |
| `architecture_decision_audit` | `public_claim_evidence_audit` | yes |
| `architecture_decision_audit` | `render_incident_evidence` | yes |
| `architecture_decision_audit` | `documentation_link_integrity_audit` | yes |
| `architecture_decision_audit` | `evidence_schema_audit` | yes |
| `architecture_decision_audit` | `disaster_recovery_drill` | yes |
| `architecture_decision_audit` | `evidence_provenance` | yes |
| `architecture_decision_audit` | `control_traceability_audit` | yes |
| `architecture_decision_audit` | `release_readiness` | yes |
| `architecture_decision_audit` | `proof_packet_integrity_audit` | yes |
| `reviewer_reproducibility_audit` | `public_claim_evidence_audit` | yes |
| `reviewer_reproducibility_audit` | `render_incident_evidence` | yes |
| `reviewer_reproducibility_audit` | `documentation_link_integrity_audit` | yes |
| `reviewer_reproducibility_audit` | `evidence_schema_audit` | yes |
| `reviewer_reproducibility_audit` | `disaster_recovery_drill` | yes |
| `reviewer_reproducibility_audit` | `evidence_provenance` | yes |
| `reviewer_reproducibility_audit` | `control_traceability_audit` | yes |
| `reviewer_reproducibility_audit` | `release_readiness` | yes |
| `reviewer_reproducibility_audit` | `proof_packet_integrity_audit` | yes |
| `threat_model_audit` | `public_claim_evidence_audit` | yes |
| `threat_model_audit` | `render_incident_evidence` | yes |
| `threat_model_audit` | `documentation_link_integrity_audit` | yes |
| `threat_model_audit` | `evidence_schema_audit` | yes |
| `threat_model_audit` | `disaster_recovery_drill` | yes |
| `threat_model_audit` | `evidence_provenance` | yes |
| `threat_model_audit` | `control_traceability_audit` | yes |
| `threat_model_audit` | `release_readiness` | yes |
| `threat_model_audit` | `proof_packet_integrity_audit` | yes |
| `data_handling_audit` | `public_claim_evidence_audit` | yes |
| `data_handling_audit` | `render_incident_evidence` | yes |
| `data_handling_audit` | `documentation_link_integrity_audit` | yes |
| `data_handling_audit` | `evidence_schema_audit` | yes |
| `data_handling_audit` | `disaster_recovery_drill` | yes |
| `data_handling_audit` | `evidence_provenance` | yes |
| `data_handling_audit` | `control_traceability_audit` | yes |
| `data_handling_audit` | `release_readiness` | yes |
| `data_handling_audit` | `proof_packet_integrity_audit` | yes |
| `dependency_update_audit` | `public_claim_evidence_audit` | yes |
| `dependency_update_audit` | `render_incident_evidence` | yes |
| `dependency_update_audit` | `documentation_link_integrity_audit` | yes |
| `dependency_update_audit` | `evidence_schema_audit` | yes |
| `dependency_update_audit` | `disaster_recovery_drill` | yes |
| `dependency_update_audit` | `evidence_provenance` | yes |
| `dependency_update_audit` | `control_traceability_audit` | yes |
| `dependency_update_audit` | `release_readiness` | yes |
| `dependency_update_audit` | `proof_packet_integrity_audit` | yes |
| `security_scanning_audit` | `public_claim_evidence_audit` | yes |
| `security_scanning_audit` | `render_incident_evidence` | yes |
| `security_scanning_audit` | `documentation_link_integrity_audit` | yes |
| `security_scanning_audit` | `evidence_schema_audit` | yes |
| `security_scanning_audit` | `disaster_recovery_drill` | yes |
| `security_scanning_audit` | `evidence_provenance` | yes |
| `security_scanning_audit` | `control_traceability_audit` | yes |
| `security_scanning_audit` | `release_readiness` | yes |
| `security_scanning_audit` | `proof_packet_integrity_audit` | yes |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `regional_before_disaster_recovery` | `dependency_order` | yes |
| `provenance_before_render_index` | `dependency_order` | yes |
| `missing_release_readiness_step` | `step_inventory` | yes |
| `duplicate_schema_audit_step` | `step_inventory` | yes |
