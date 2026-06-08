# Observability Drift Audit

Overall status: **PASS**

This audit compares the generated SLO alerting evidence, Grafana
dashboard evidence, OpenSLO evidence, and incident runbooks. The goal is
to catch semantic drift where each artifact passes by itself but no
longer describes the same operating contract.

## Scenario Surfaces

| Surface | Scenarios |
| --- | --- |
| `alerting` | `baseline`, `cache_miss_storm`, `collector_queue_pressure`, `dependency_timeout`, `rollout_regression` |
| `dashboard` | `baseline`, `cache_miss_storm`, `collector_queue_pressure`, `dependency_timeout`, `rollout_regression` |
| `openslo` | `baseline`, `cache_miss_storm`, `collector_queue_pressure`, `dependency_timeout`, `rollout_regression` |
| `runbooks` | `baseline`, `cache_miss_storm`, `collector_queue_pressure`, `dependency_timeout`, `rollout_regression` |

## Checks

| Check | Status |
| --- | --- |
| `scenario_contract` | PASS |
| `alert_metadata_contract` | PASS |
| `dashboard_contract` | PASS |
| `openslo_contract` | PASS |
| `runbook_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Drift Fixtures

| Fixture | Scenario | Detected |
| --- | --- | --- |
| `missing_alert_scenario` | `dependency_timeout` | yes |
| `missing_dashboard_scenario` | `cache_miss_storm` | yes |
| `missing_openslo_scenario` | `collector_queue_pressure` | yes |
| `missing_runbook_scenario` | `rollout_regression` | yes |
| `severity_mismatch` | `cache_miss_storm` | yes |
