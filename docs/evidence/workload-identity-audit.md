# Workload Identity Audit

Overall status: **PASS**

This audit checks that GKE Workload Identity, service account token
mounting, RBAC scope, static credential handling, and upstream exporter
transport are explicit before the manifests are treated as production
deployment evidence.

## Summary

- Checks: `8`
- Identity boundaries: `2`
- Detected negative fixtures: `9`
- Upstream endpoint: `https://otel-gateway.example.com:4318`

## Identity Boundaries

| Workload | Namespace | Kubernetes SA | GCP SA | Automount token |
| --- | --- | --- | --- | --- |
| `otel-collector` | `telemetry` | `otel-collector` | `otel-collector@gke-ai-inference-reliability.iam.gserviceaccount.com` | `true` |
| `toy-ai-inference-api` | `ai-observability-demo` | `toy-ai-inference-api` | `none` | `false` |

## Checks

| Check | Status |
| --- | --- |
| `workload_identity_annotation` | PASS |
| `collector_token_boundary` | PASS |
| `application_token_boundary` | PASS |
| `rbac_least_privilege` | PASS |
| `rbac_binding_scope` | PASS |
| `static_credential_guard` | PASS |
| `secure_exporter_boundary` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_workload_identity_annotation` | yes |
| `wrong_gcp_service_account_binding` | yes |
| `workload_token_automount_enabled` | yes |
| `static_gcp_secret_added` | yes |
| `GOOGLE_APPLICATION_CREDENTIALS` | yes |
| `collector_rbac_mutating_verb` | yes |
| `collector_rbac_wildcard_resource` | yes |
| `collector_binding_wrong_subject` | yes |
| `insecure_upstream_endpoint` | yes |
