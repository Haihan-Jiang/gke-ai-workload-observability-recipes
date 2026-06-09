# Telemetry Cost Budget

Overall status: **PASS**

This budget estimates trace ingest and retention from the generated
OTLP payloads. It keeps incident traces useful while checking that
sampling, span volume, payload size, and retention assumptions stay
inside a production-style telemetry budget.

## Summary

- Production QPS: `250.0`
- Weighted bytes per request after sampling: `544.1`
- Daily ingest: `10.95` GiB
- Retained storage: `76.62` GiB

## Scenario Cost Inputs

| Scenario | Requests | Spans/request | Bytes/request |
| --- | ---: | ---: | ---: |
| `baseline` | 8 | 4.0 | 6290.88 |
| `cache_miss_storm` | 7 | 4.0 | 6356.0 |
| `dependency_timeout` | 6 | 4.0 | 6663.33 |
| `rollout_regression` | 7 | 4.0 | 6506.86 |
| `collector_queue_pressure` | 6 | 4.0 | 6960.17 |

## Checks

| Check | Status |
| --- | --- |
| `payload_coverage` | PASS |
| `span_budget` | PASS |
| `payload_size_budget` | PASS |
| `sampling_policy` | PASS |
| `critical_scenario_sampling` | PASS |
| `daily_ingest_budget` | PASS |
| `retention_budget` | PASS |
