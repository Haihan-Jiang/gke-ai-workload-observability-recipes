# Synthetic Probe Audit

Overall status: **PASS**

This audit checks that preflight synthetic probes cover the healthy
baseline, dependency failures, canary regression, and telemetry
delivery failure before release promotion. Each probe must connect
its replayed signal to alert routing, incident response, dependency
contracts, error-budget action, and rollback evidence where needed.

## Summary

- Probes: `5`
- Incident probes: `4`
- Preflight block probes: `2`
- Detected negative fixtures: `5`

## Probes

| Probe | Scenario | Type | Dependency | Alert | Release action |
| --- | --- | --- | --- | --- | --- |
| `baseline_readiness_probe` | `baseline` | `readiness` | `none` | `page` | `eligible_for_release` |
| `cache_dependency_probe` | `cache_miss_storm` | `dependency` | `vector_cache` | `ticket` | `require_sre_review_before_rollout` |
| `feature_store_timeout_probe` | `dependency_timeout` | `dependency` | `feature_store` | `page` | `block_release_or_rollback` |
| `canary_version_probe` | `rollout_regression` | `canary` | `model_runtime` | `page` | `block_release_or_rollback` |
| `telemetry_delivery_probe` | `collector_queue_pressure` | `telemetry` | `telemetry_exporter` | `page` | `require_sre_review_before_rollout` |

## Checks

| Check | Status |
| --- | --- |
| `probe_inventory` | PASS |
| `signal_contract` | PASS |
| `dependency_contract_linkage` | PASS |
| `alert_response_contract` | PASS |
| `rollout_preflight_guard` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Probe | Detected |
| --- | --- | --- |
| `missing_baseline_probe` | `baseline_readiness_probe` | yes |
| `unhealthy_baseline_probe` | `baseline_readiness_probe` | yes |
| `missing_dependency_link` | `feature_store_timeout_probe` | yes |
| `wrong_canary_alert_severity` | `canary_version_probe` | yes |
| `missing_canary_rollback_response` | `canary_version_probe` | yes |
