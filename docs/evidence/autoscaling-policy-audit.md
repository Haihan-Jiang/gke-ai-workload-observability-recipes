# Autoscaling Policy Audit

Overall status: **PASS**

This audit checks that the sample inference workload has a real
HorizontalPodAutoscaler, not only an offline HPA lag model. It verifies
the HPA target, replica bounds, CPU/memory metrics, metric-to-request
alignment, scale behavior, owner labels, and negative fixtures.

## Summary

- HPA count: `1`
- Metrics: `2`
- Behavior policies: `3`
- Detected negative fixtures: `9`

## Target

| Namespace | Deployment | HPA | Min replicas | Max replicas | Metrics |
| --- | --- | --- | ---: | ---: | --- |
| `ai-observability-demo` | `toy-ai-inference-api` | `toy-ai-inference-api` | 2 | 8 | `cpu`, `memory` |

## Checks

| Check | Status |
| --- | --- |
| `hpa_coverage` | PASS |
| `hpa_target_ref` | PASS |
| `replica_bounds` | PASS |
| `metric_coverage` | PASS |
| `metric_targets` | PASS |
| `metric_request_alignment` | PASS |
| `scale_behavior` | PASS |
| `autoscaling_label_governance` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_hpa` | yes |
| `wrong_scale_target` | yes |
| `min_replicas_below_policy` | yes |
| `max_replicas_below_burst_budget` | yes |
| `missing_cpu_metric` | yes |
| `cpu_target_too_high` | yes |
| `missing_scale_down_stabilization` | yes |
| `missing_cpu_request` | yes |
| `missing_hpa_owner_label` | yes |
