# SLO Alerting Rules

Overall status: **PASS**

These generated alert rules connect replay evidence to operations. The
rules preserve scenario ownership, severity, runbook links, and dashboard
hints so a release gate can become a page or ticket with enough context
for first response.

## Alerts

| Alert | Scenario | Severity | For |
| --- | --- | --- | --- |
| `GKEAIInferenceBaselineLatencySLOViolation` | `baseline` | `page` | `5m` |
| `GKEAIInferenceCacheMissStorm` | `cache_miss_storm` | `ticket` | `10m` |
| `GKEAIInferenceDependencyErrorBudgetBurn` | `dependency_timeout` | `page` | `5m` |
| `GKEAIInferenceRolloutVersionRegression` | `rollout_regression` | `page` | `5m` |
| `GKEAICollectorTelemetryLoss` | `collector_queue_pressure` | `page` | `5m` |

## Audit Checks

| Check | Status |
| --- | --- |
| `alert_count` | PASS |
| `unique_alert_names` | PASS |
| `scenario_coverage` | PASS |
| `required_labels` | PASS |
| `required_annotations` | PASS |
| `page_alerts_present` | PASS |
| `prometheus_rule_manifest` | PASS |
