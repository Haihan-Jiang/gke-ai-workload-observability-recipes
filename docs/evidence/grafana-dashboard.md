# Grafana Dashboard Evidence

Overall status: **PASS**

This generated dashboard is dashboard-as-code evidence for the lab. It
ties SLO scenarios to Prometheus queries, runbook links, and alerting
context so reviewers can inspect the operational surface without
manually designing panels.

## Panels

| Panel | Type | Scenarios |
| --- | --- | --- |
| `p95 latency by service version` | `timeseries` | baseline, rollout_regression |
| `error rate by response class` | `timeseries` | dependency_timeout, rollout_regression |
| `cache miss ratio` | `timeseries` | cache_miss_storm |
| `collector telemetry loss` | `timeseries` | collector_queue_pressure |
| `active SLO alerts` | `table` | baseline, cache_miss_storm, collector_queue_pressure, dependency_timeout, rollout_regression |
| `rollout candidate p95` | `stat` | rollout_regression |

## Audit Checks

| Check | Status |
| --- | --- |
| `dashboard_uid` | PASS |
| `panel_count` | PASS |
| `scenario_coverage` | PASS |
| `panel_type_coverage` | PASS |
| `prometheus_datasource` | PASS |
| `runbook_links` | PASS |
| `config_map_manifest` | PASS |
