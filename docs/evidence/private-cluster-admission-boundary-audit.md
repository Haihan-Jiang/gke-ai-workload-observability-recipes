# Private Cluster Admission Boundary Audit

Overall status: **PASS**

This audit verifies that private GKE clusters can use the lab's
admission controls without an external admission webhook firewall
dependency. It also keeps optional operator-backed CRDs behind
kind-smoke API-resource probes and skip paths.

## Summary

| Metric | Value |
| --- | ---: |
| Documents | 28 |
| Native admission resources | 2 |
| Webhook configurations | 0 |
| Webhook services | 0 |
| Optional operator boundaries | 2 |
| Private cluster doc markers | 2 |
| Detected fixtures | 6 |

## Checks

| Check | Status |
| --- | --- |
| `document_inventory` | PASS |
| `native_admission_boundary` | PASS |
| `webhook_service_boundary` | PASS |
| `optional_operator_boundary` | PASS |
| `private_cluster_docs` | PASS |
| `negative_fixture_coverage` | PASS |

## Native Admission Resources

| Resource |
| --- |
| `ValidatingAdmissionPolicy/gke-ai-inference-reliability-deployments` |
| `ValidatingAdmissionPolicyBinding/gke-ai-inference-reliability-deployments` |

## Optional Operator Boundaries

| Kind | API group | Probe | Skip path |
| --- | --- | --- | --- |
| `Instrumentation` | `opentelemetry.io` | yes | yes |
| `PrometheusRule` | `monitoring.coreos.com` | yes | yes |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `adds_validating_webhook_configuration` | `native_admission_boundary` | yes |
| `adds_mutating_webhook_configuration` | `native_admission_boundary` | yes |
| `adds_admission_webhook_service` | `webhook_service_boundary` | yes |
| `adds_native_admission_client_config` | `native_admission_boundary` | yes |
| `removes_otel_operator_skip` | `optional_operator_boundary` | yes |
| `removes_private_cluster_docs` | `private_cluster_docs` | yes |
