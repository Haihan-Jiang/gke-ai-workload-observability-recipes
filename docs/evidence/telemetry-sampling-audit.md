# Telemetry Sampling Audit

Overall status: **PASS**

This audit checks that OpenTelemetry tail sampling keeps critical AI
inference traces for errors, dependency timeouts, rollout regressions,
and collector pressure while bounding healthy baseline trace volume.

## Summary

- Sampling policies: `5`
- Critical policies: `4`
- Baseline sampling percentage: `2`
- Detected negative fixtures: `10`

## Checks

| Check | Status |
| --- | --- |
| `collector_config_map` | PASS |
| `sampling_processor_defined` | PASS |
| `trace_pipeline_sampling_order` | PASS |
| `metrics_pipeline_excludes_tail_sampling` | PASS |
| `sampling_decision_window` | PASS |
| `sampling_buffer` | PASS |
| `critical_trace_policy_coverage` | PASS |
| `baseline_sampling_budget` | PASS |
| `exporter_queue_preserved` | PASS |
| `collector_config_label_governance` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_tail_sampling_processor` | yes |
| `tail_sampling_removed_from_traces` | yes |
| `tail_sampling_after_batch` | yes |
| `metrics_pipeline_tail_sampling` | yes |
| `unbounded_decision_wait` | yes |
| `undersized_trace_buffer` | yes |
| `missing_error_policy` | yes |
| `wrong_dependency_attribute` | yes |
| `excessive_baseline_sampling` | yes |
| `missing_collector_config_owner_label` | yes |
