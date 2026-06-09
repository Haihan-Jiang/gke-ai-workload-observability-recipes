# Kubernetes API Compatibility Audit

Overall status: **PASS**

This audit verifies that the GKE-shaped manifests use stable
Kubernetes API versions, keep optional OpenTelemetry and Prometheus
CRDs behind kind-smoke skip paths, and keep the admission policy on
the v1 fail-closed API surface.

## Summary

| Metric | Value |
| --- | ---: |
| Documents | 28 |
| Stable core resources | 26 |
| Optional CRDs | 2 |
| Admission policies | 1 |
| Admission bindings | 1 |
| Core apply steps | 5 |
| Detected fixtures | 8 |

## Checks

| Check | Status |
| --- | --- |
| `document_inventory` | PASS |
| `stable_core_api_versions` | PASS |
| `optional_crd_boundary` | PASS |
| `admission_policy_api` | PASS |
| `kind_smoke_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Resources

| Resource | API version | Optional CRD |
| --- | --- | --- |
| `Namespace/telemetry` | `v1` | no |
| `ResourceQuota/telemetry/telemetry-resource-quota` | `v1` | no |
| `LimitRange/telemetry/telemetry-limit-range` | `v1` | no |
| `Namespace/ai-observability-demo` | `v1` | no |
| `ResourceQuota/ai-observability-demo/ai-workload-resource-quota` | `v1` | no |
| `LimitRange/ai-observability-demo/ai-workload-limit-range` | `v1` | no |
| `PriorityClass/ai-telemetry-critical` | `scheduling.k8s.io/v1` | no |
| `PriorityClass/ai-inference-serving` | `scheduling.k8s.io/v1` | no |
| `ServiceAccount/telemetry/otel-collector` | `v1` | no |
| `ClusterRole/otel-collector-readonly` | `rbac.authorization.k8s.io/v1` | no |
| `ClusterRoleBinding/otel-collector-readonly` | `rbac.authorization.k8s.io/v1` | no |
| `PersistentVolumeClaim/telemetry/otel-collector-queue` | `v1` | no |
| `ConfigMap/telemetry/otel-collector-config` | `v1` | no |
| `Deployment/telemetry/otel-collector` | `apps/v1` | no |
| `Service/telemetry/otel-collector` | `v1` | no |
| `PodDisruptionBudget/telemetry/otel-collector` | `policy/v1` | no |
| `NetworkPolicy/telemetry/allow-otlp-from-ai-workloads` | `networking.k8s.io/v1` | no |
| `Instrumentation/telemetry/python-instrumentation` | `opentelemetry.io/v1alpha1` | yes |
| `PrometheusRule/telemetry/gke-ai-inference-reliability-alerts` | `monitoring.coreos.com/v1` | yes |
| `ConfigMap/telemetry/gke-ai-inference-grafana-dashboard` | `v1` | no |
| `ServiceAccount/ai-observability-demo/toy-ai-inference-api` | `v1` | no |
| `Deployment/ai-observability-demo/toy-ai-inference-api` | `apps/v1` | no |
| `Service/ai-observability-demo/toy-ai-inference-api` | `v1` | no |
| `PodDisruptionBudget/ai-observability-demo/toy-ai-inference-api` | `policy/v1` | no |
| `HorizontalPodAutoscaler/ai-observability-demo/toy-ai-inference-api` | `autoscaling/v2` | no |
| `NetworkPolicy/ai-observability-demo/allow-ai-workload-egress` | `networking.k8s.io/v1` | no |
| `ValidatingAdmissionPolicy/gke-ai-inference-reliability-deployments` | `admissionregistration.k8s.io/v1` | no |
| `ValidatingAdmissionPolicyBinding/gke-ai-inference-reliability-deployments` | `admissionregistration.k8s.io/v1` | no |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `deployment_uses_extensions_beta` | `stable_core_api_versions` | yes |
| `pdb_uses_policy_beta` | `stable_core_api_versions` | yes |
| `hpa_uses_legacy_version` | `stable_core_api_versions` | yes |
| `admission_policy_uses_beta` | `admission_policy_api` | yes |
| `admission_binding_warns_only` | `admission_policy_api` | yes |
| `missing_otel_crd_skip` | `optional_crd_boundary` | yes |
| `missing_prometheus_crd_skip` | `optional_crd_boundary` | yes |
| `missing_collector_apply_step` | `kind_smoke_contract` | yes |
