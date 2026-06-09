# Collector Self-Observability Audit

Overall status: **PASS**

This audit checks that the OpenTelemetry Collector scrapes its own
internal metrics on loopback, sends them through the metrics pipeline,
and preserves queued export and retry behavior for collector health
signals.

## Summary

- Receivers: `3`
- Self-metrics scrape jobs: `1`
- Self-metrics targets: `1`
- Detected negative fixtures: `10`

## Checks

| Check | Status |
| --- | --- |
| `collector_config_map` | PASS |
| `self_metrics_receiver_defined` | PASS |
| `self_metrics_scrape_job` | PASS |
| `self_metrics_loopback_target` | PASS |
| `self_metrics_scrape_interval` | PASS |
| `metrics_pipeline_collects_self_metrics` | PASS |
| `metrics_pipeline_processor_order` | PASS |
| `metrics_pipeline_excludes_trace_sampling` | PASS |
| `self_metrics_exporter_path` | PASS |
| `self_metrics_exporter_queue` | PASS |
| `collector_config_label_governance` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_self_metrics_receiver` | yes |
| `self_metrics_removed_from_pipeline` | yes |
| `wrong_scrape_job_name` | yes |
| `missing_scrape_target` | yes |
| `non_loopback_scrape_target` | yes |
| `slow_scrape_interval` | yes |
| `tail_sampling_in_metrics_pipeline` | yes |
| `missing_resource_enrichment` | yes |
| `disabled_exporter_queue` | yes |
| `missing_collector_config_owner_label` | yes |
