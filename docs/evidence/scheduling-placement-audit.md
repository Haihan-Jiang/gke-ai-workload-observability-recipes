# Scheduling Placement Audit

Overall status: **PASS**

This audit checks that the collector and sample inference workload
declare reviewable scheduling intent through non-preempting
PriorityClasses, soft node affinity, and bounded tolerations without
hard node selectors that would break portable local smoke tests.

## Summary

- Workloads: `2`
- PriorityClasses: `2`
- Preferred affinity expressions: `4`
- Tolerations: `2`
- Detected negative fixtures: `10`

## Workloads

| Workload | PriorityClass | Affinity keys | Toleration keys |
| --- | --- | --- | --- |
| `telemetry/otel-collector` | `ai-telemetry-critical` | `cloud.google.com/gke-nodepool`, `workload.haihan.dev/telemetry` | `workload.haihan.dev/telemetry` |
| `ai-observability-demo/toy-ai-inference-api` | `ai-inference-serving` | `cloud.google.com/gke-nodepool`, `workload.haihan.dev/inference` | `workload.haihan.dev/inference` |

## Checks

| Check | Status |
| --- | --- |
| `priority_class_definitions` | PASS |
| `workload_priority_binding` | PASS |
| `preferred_node_affinity` | PASS |
| `portable_scheduling_preferences` | PASS |
| `bounded_tolerations` | PASS |
| `scheduling_label_governance` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_inference_priority_class` | yes |
| `low_telemetry_priority_value` | yes |
| `preempting_telemetry_priority` | yes |
| `sample_missing_priority_binding` | yes |
| `collector_wrong_priority_binding` | yes |
| `sample_missing_nodepool_preference` | yes |
| `collector_hard_node_selector` | yes |
| `sample_missing_toleration` | yes |
| `collector_wildcard_toleration` | yes |
| `missing_priority_class_owner_label` | yes |
