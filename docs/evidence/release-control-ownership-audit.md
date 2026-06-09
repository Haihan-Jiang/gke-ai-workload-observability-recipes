# Release Control Ownership Audit

Overall status: **PASS**

This audit verifies that every release-readiness check has an owner,
severity tier, review cadence, escalation path, rollback action, and
evidence path before the final release gate passes.

## Summary

| Metric | Value |
| --- | ---: |
| Controls | 50 |
| Release checks | 50 |
| Covered release checks | 50 |
| Tier 0 controls | 27 |
| Every-release controls | 38 |
| Owner groups | 5 |
| Detected fixtures | 6 |

## Checks

| Check | Status |
| --- | --- |
| `control_inventory` | PASS |
| `ownership_metadata` | PASS |
| `tier_contract` | PASS |
| `review_cadence_contract` | PASS |
| `owner_group_coverage` | PASS |
| `evidence_path_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Controls

| Control | Owner | Tier | Cadence | Evidence |
| --- | --- | --- | --- | --- |
| `reliability_gate` | `sre` | `tier_0_release_blocker` | `every_release` | `docs/evidence/reliability-gate.json` |
| `evidence_files` | `evidence` | `tier_0_release_blocker` | `every_release` | `docs/evidence/README.md` |
| `runbook_coverage` | `sre` | `tier_1_production_guard` | `every_release` | `docs/evidence/incident-runbooks.json` |
| `capacity_plan` | `sre` | `tier_1_production_guard` | `every_release` | `docs/evidence/capacity-plan.json` |
| `advanced_problem_coverage` | `mlops` | `tier_1_production_guard` | `monthly` | `docs/evidence/complex-problems.json` |
| `detailed_problem_coverage` | `mlops` | `tier_1_production_guard` | `monthly` | `docs/evidence/detailed-problems.json` |
| `deployment_policy` | `sre` | `tier_0_release_blocker` | `every_release` | `docs/evidence/deployment-policy.json` |
| `policy_regression_suite` | `evidence` | `tier_0_release_blocker` | `every_release` | `docs/evidence/policy-regression-suite.json` |
| `supply_chain_audit` | `security` | `tier_0_release_blocker` | `every_release` | `docs/evidence/supply-chain-audit.json` |
| `oss_license_audit` | `security` | `tier_0_release_blocker` | `every_release` | `docs/evidence/oss-license-audit.json` |
| `ci_governance_audit` | `security` | `tier_0_release_blocker` | `every_release` | `docs/evidence/ci-governance-audit.json` |
| `repository_governance_audit` | `security` | `tier_1_production_guard` | `monthly` | `docs/evidence/repository-governance-audit.json` |
| `developer_runtime_audit` | `evidence` | `tier_1_production_guard` | `monthly` | `docs/evidence/developer-runtime-audit.json` |
| `k8s_manifest_hardening` | `platform` | `tier_0_release_blocker` | `every_release` | `docs/evidence/k8s-hardening-audit.json` |
| `pod_security_admission_audit` | `security` | `tier_0_release_blocker` | `every_release` | `docs/evidence/pod-security-admission-audit.json` |
| `namespace_resource_audit` | `platform` | `tier_1_production_guard` | `every_release` | `docs/evidence/namespace-resource-audit.json` |
| `availability_topology_audit` | `platform` | `tier_1_production_guard` | `every_release` | `docs/evidence/availability-topology-audit.json` |
| `autoscaling_policy_audit` | `platform` | `tier_1_production_guard` | `every_release` | `docs/evidence/autoscaling-policy-audit.json` |
| `scheduling_placement_audit` | `platform` | `tier_1_production_guard` | `monthly` | `docs/evidence/scheduling-placement-audit.json` |
| `rollout_safety_audit` | `platform` | `tier_0_release_blocker` | `every_release` | `docs/evidence/rollout-safety-audit.json` |
| `config_rollout_audit` | `platform` | `tier_1_production_guard` | `every_release` | `docs/evidence/config-rollout-audit.json` |
| `network_boundary_audit` | `platform` | `tier_0_release_blocker` | `every_release` | `docs/evidence/network-boundary-audit.json` |
| `collector_self_observability_audit` | `platform` | `tier_1_production_guard` | `monthly` | `docs/evidence/collector-self-observability-audit.json` |
| `telemetry_sampling_audit` | `platform` | `tier_1_production_guard` | `monthly` | `docs/evidence/telemetry-sampling-audit.json` |
| `workload_identity_audit` | `security` | `tier_0_release_blocker` | `every_release` | `docs/evidence/workload-identity-audit.json` |
| `admission_policy_audit` | `security` | `tier_0_release_blocker` | `every_release` | `docs/evidence/admission-policy-audit.json` |
| `slo_alerting_rules` | `sre` | `tier_1_production_guard` | `every_release` | `docs/evidence/alerting-rules.json` |
| `grafana_dashboard` | `sre` | `tier_2_evidence_guard` | `monthly` | `docs/evidence/grafana-dashboard.json` |
| `openslo_contract` | `sre` | `tier_1_production_guard` | `monthly` | `docs/evidence/openslo-contract.json` |
| `observability_drift_audit` | `sre` | `tier_1_production_guard` | `every_release` | `docs/evidence/observability-drift-audit.json` |
| `telemetry_redaction_audit` | `security` | `tier_0_release_blocker` | `every_release` | `docs/evidence/telemetry-redaction-audit.json` |
| `telemetry_cost_budget` | `mlops` | `tier_1_production_guard` | `monthly` | `docs/evidence/telemetry-cost-budget.json` |
| `error_budget_ledger` | `sre` | `tier_0_release_blocker` | `every_release` | `docs/evidence/error-budget-ledger.json` |
| `rollback_drill` | `sre` | `tier_0_release_blocker` | `every_release` | `docs/evidence/rollback-drill.json` |
| `post_incident_review` | `sre` | `tier_1_production_guard` | `monthly` | `docs/evidence/post-incident-review.json` |
| `incident_response_drill` | `sre` | `tier_0_release_blocker` | `every_release` | `docs/evidence/incident-response-drill.json` |
| `dependency_contract_audit` | `mlops` | `tier_1_production_guard` | `monthly` | `docs/evidence/dependency-contract-audit.json` |
| `synthetic_probe_audit` | `mlops` | `tier_1_production_guard` | `every_release` | `docs/evidence/synthetic-probe-audit.json` |
| `model_release_safety_audit` | `mlops` | `tier_0_release_blocker` | `every_release` | `docs/evidence/model-release-safety-audit.json` |
| `shadow_traffic_replay_audit` | `mlops` | `tier_0_release_blocker` | `every_release` | `docs/evidence/shadow-traffic-replay-audit.json` |
| `accelerator_quota_fairness_audit` | `mlops` | `tier_1_production_guard` | `every_release` | `docs/evidence/accelerator-quota-fairness-audit.json` |
| `load_shedding_policy_audit` | `sre` | `tier_1_production_guard` | `every_release` | `docs/evidence/load-shedding-policy-audit.json` |
| `regional_failover_audit` | `sre` | `tier_0_release_blocker` | `every_release` | `docs/evidence/regional-failover-audit.json` |
| `release_waiver_governance` | `security` | `tier_0_release_blocker` | `every_release` | `docs/evidence/release-waiver-governance.json` |
| `release_control_ownership_audit` | `evidence` | `tier_0_release_blocker` | `every_release` | `docs/evidence/release-control-ownership-audit.json` |
| `control_traceability_audit` | `evidence` | `tier_0_release_blocker` | `every_release` | `docs/evidence/control-traceability-audit.json` |
| `evidence_pipeline_audit` | `evidence` | `tier_0_release_blocker` | `every_release` | `docs/evidence/evidence-pipeline-audit.json` |
| `evidence_schema_audit` | `evidence` | `tier_0_release_blocker` | `every_release` | `docs/evidence/evidence-schema-audit.json` |
| `disaster_recovery_drill` | `sre` | `tier_0_release_blocker` | `every_release` | `docs/evidence/disaster-recovery-drill.json` |
| `evidence_provenance` | `evidence` | `tier_0_release_blocker` | `every_release` | `docs/evidence/evidence-provenance.json` |
