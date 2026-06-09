# Dependency Contract Audit

Overall status: **PASS**

This audit checks that critical inference dependencies have owners,
timeout/retry/fallback controls, alert routing, runbook linkage,
failure-mode evidence, and release-action linkage before their
signals are trusted by the release gate.

## Summary

- Dependencies: `4`
- Incident contracts: `4`
- Dominant dependency signals: `3`
- Detected negative fixtures: `5`

## Contracts

| Dependency | Scenario | Owner | Alert | Release action | Signal |
| --- | --- | --- | --- | --- | ---: |
| `vector_cache` | `cache_miss_storm` | Inference platform / retrieval owner | `ticket` | `require_sre_review_before_rollout` | `128.0` |
| `feature_store` | `dependency_timeout` | Feature platform / dependency owner | `page` | `block_release_or_rollback` | `730.0` |
| `model_runtime` | `rollout_regression` | Service owner / release engineer | `page` | `block_release_or_rollback` | `246.0` |
| `telemetry_exporter` | `collector_queue_pressure` | Observability platform | `page` | `require_sre_review_before_rollout` | `0.42` |

## Checks

| Check | Status |
| --- | --- |
| `dependency_inventory` | PASS |
| `owner_runbook_contract` | PASS |
| `alert_contract` | PASS |
| `failure_mode_contract` | PASS |
| `release_action_contract` | PASS |
| `resilience_settings` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Dependency | Detected |
| --- | --- | --- |
| `missing_dependency_owner` | `feature_store` | yes |
| `wrong_alert_severity` | `model_runtime` | yes |
| `missing_fallback` | `vector_cache` | yes |
| `wrong_release_action` | `feature_store` | yes |
| `missing_failure_signal` | `feature_store` | yes |
