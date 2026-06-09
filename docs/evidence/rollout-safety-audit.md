# Rollout Safety Audit

Overall status: **PASS**

This audit checks Deployment rollout strategy, availability windows,
termination drain settings, PDB alignment, and singleton collector
queue-PVC rollout behavior before the manifests are treated as
release evidence.

## Summary

- Workloads: `2`
- RollingUpdate workloads: `1`
- Recreate workloads: `1`
- Rollout timing guards: `2`
- Termination windows: `2`
- Detected negative fixtures: `12`

## Workloads

| Workload | Mode | Strategy | Min ready | Progress deadline | Termination grace |
| --- | --- | --- | ---: | ---: | ---: |
| `telemetry/otel-collector` | `singleton_recreate` | `Recreate` | 10 | 180 | 60 |
| `ai-observability-demo/toy-ai-inference-api` | `rolling_ha` | `RollingUpdate` | 10 | 180 | 30 |

## Checks

| Check | Status |
| --- | --- |
| `rolling_update_strategy` | PASS |
| `rolling_update_availability` | PASS |
| `singleton_recreate_strategy` | PASS |
| `singleton_queue_alignment` | PASS |
| `rollout_timing` | PASS |
| `termination_drain_window` | PASS |
| `pdb_rollout_alignment` | PASS |
| `rollout_label_governance` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `sample_strategy_recreate` | yes |
| `sample_allows_unavailable_pod` | yes |
| `sample_missing_surge_capacity` | yes |
| `sample_min_ready_zero` | yes |
| `sample_progress_deadline_short` | yes |
| `sample_missing_termination_grace` | yes |
| `collector_rolling_update_with_pvc` | yes |
| `collector_missing_queue_pvc` | yes |
| `collector_short_termination_grace` | yes |
| `missing_deployment_owner_label` | yes |
| `sample_pdb_min_equals_replicas` | yes |
| `collector_pdb_allows_eviction` | yes |
