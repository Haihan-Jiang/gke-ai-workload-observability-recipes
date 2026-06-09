# Evidence Schema Audit

Overall status: **PASS**

This audit checks that critical evidence JSON files keep stable
machine-readable contracts for status fields, required fields, check
inventory, metric minimums, metric ceilings, array lengths, allowed
values, and negative drift fixtures.

## Summary

| Metric | Value |
| --- | ---: |
| Artifacts | 21 |
| Required fields | 227 |
| Required checks | 138 |
| Metric contracts | 146 |
| Array contracts | 50 |
| Observed checks | 138 |
| Detected fixtures | 21 |

## Checks

| Check | Status |
| --- | --- |
| `artifact_inventory` | PASS |
| `required_fields` | PASS |
| `status_contract` | PASS |
| `value_contract` | PASS |
| `check_shape` | PASS |
| `check_inventory` | PASS |
| `metric_contract` | PASS |
| `array_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Artifact Contracts

| Artifact | Status | Checks |
| --- | --- | ---: |
| `docs/evidence/evidence-pipeline-audit.json` | `pass` | 5 |
| `docs/evidence/validation-contract-audit.json` | `pass` | 7 |
| `docs/evidence/developer-runtime-audit.json` | `pass` | 7 |
| `docs/evidence/repository-governance-audit.json` | `pass` | 6 |
| `docs/evidence/ci-governance-audit.json` | `pass` | 8 |
| `docs/evidence/pod-security-admission-audit.json` | `pass` | 6 |
| `docs/evidence/kubernetes-api-compatibility-audit.json` | `pass` | 6 |
| `docs/evidence/private-cluster-admission-boundary-audit.json` | `pass` | 6 |
| `docs/evidence/telemetry-exporter-authority-audit.json` | `pass` | 8 |
| `docs/evidence/synthetic-probe-audit.json` | `pass` | 6 |
| `docs/evidence/model-release-safety-audit.json` | `pass` | 8 |
| `docs/evidence/staged-telemetry-validation-audit.json` | `pass` | 7 |
| `docs/evidence/deployment-policy.json` | `generated` | n/a |
| `docs/evidence/supply-chain-audit.json` | `pass` | 6 |
| `docs/evidence/k8s-hardening-audit.json` | `pass` | 11 |
| `docs/evidence/workload-identity-audit.json` | `pass` | 8 |
| `docs/evidence/public-claim-evidence-audit.json` | `pass` | 6 |
| `docs/evidence/release-notes-contract-audit.json` | `pass` | 7 |
| `docs/evidence/maintainer-intake-audit.json` | `pass` | 8 |
| `docs/evidence/architecture-decision-audit.json` | `pass` | 6 |
| `docs/evidence/reviewer-reproducibility-audit.json` | `pass` | 6 |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_developer_runtime_status` | `required_fields` | yes |
| `invalid_ci_status` | `status_contract` | yes |
| `malformed_synthetic_probe_checks` | `check_shape` | yes |
| `missing_pod_security_namespace_check` | `check_inventory` | yes |
| `missing_kubernetes_api_stable_core_check` | `check_inventory` | yes |
| `missing_exporter_authority_annotation_check` | `check_inventory` | yes |
| `missing_private_cluster_webhook_boundary_check` | `check_inventory` | yes |
| `missing_staged_telemetry_preflight_check` | `check_inventory` | yes |
| `low_developer_runtime_make_target_count` | `metric_contract` | yes |
| `deployment_policy_without_decision` | `required_fields` | yes |
| `model_release_without_blocked_candidate` | `metric_contract` | yes |
| `missing_workload_identity_annotation_check` | `check_inventory` | yes |
| `missing_supply_chain_digest_count` | `required_fields` | yes |
| `missing_k8s_hardening_container_check` | `check_inventory` | yes |
| `low_pipeline_dependency_count` | `metric_contract` | yes |
| `missing_validation_committed_json_check` | `check_inventory` | yes |
| `low_public_claim_count` | `metric_contract` | yes |
| `low_release_note_field_count` | `metric_contract` | yes |
| `low_maintainer_issue_template_count` | `metric_contract` | yes |
| `low_architecture_decision_count` | `metric_contract` | yes |
| `low_reviewer_command_count` | `metric_contract` | yes |
