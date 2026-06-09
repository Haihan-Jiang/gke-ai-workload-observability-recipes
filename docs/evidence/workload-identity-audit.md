# Workload Identity Audit

Overall status: **PASS**

This audit checks that GKE Workload Identity, API mount
state, RBAC scope, static identity material handling, and upstream exporter
transport are explicit before the manifests are treated as production
deployment evidence.

## Summary

- Checks: `8`
- Identity boundaries: `2`
- Detected negative fixtures: `9`
- Upstream endpoint: `https://otel-gateway.example.com:4318`

## Identity Boundaries

| Workload | Namespace | Kubernetes SA | GCP SA | API mount |
| --- | --- | --- | --- | --- |
| `otel-collector` | `telemetry` | `otel-collector` | `otel-collector@gke-ai-inference-reliability.iam.gserviceaccount.com` | `enabled` |
| `toy-ai-inference-api` | `ai-observability-demo` | `toy-ai-inference-api` | `none` | `disabled` |

## Checks

| Check | Status |
| --- | --- |
| `workload_identity_annotation` | PASS |
| `collector_api_mount_boundary` | PASS |
| `application_api_mount_boundary` | PASS |
| `rbac_least_privilege` | PASS |
| `rbac_binding_scope` | PASS |
| `static_identity_material_guard` | PASS |
| `secure_exporter_boundary` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_workload_identity_annotation` | yes |
| `wrong_gcp_service_account_binding` | yes |
| `workload_api_mount_enabled` | yes |
| `static_gcp_identity_material_added` | yes |
| `GOOGLE_APPLICATION_CREDENTIALS` | yes |
| `collector_rbac_mutating_verb` | yes |
| `collector_rbac_wildcard_resource` | yes |
| `collector_binding_wrong_subject` | yes |
| `insecure_upstream_endpoint` | yes |
