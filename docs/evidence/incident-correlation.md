# Incident Correlation

| Scenario | Root cause | Dedupe key | Owner | Symptoms |
| --- | --- | --- | --- | --- |
| `cache_miss_storm` | `cache_miss_storm` | `cache_miss_storm:v1` | inference retrieval owner | latency, cache_miss |
| `dependency_timeout` | `dependency_timeout` | `dependency_timeout:v1` | feature platform / dependency owner | latency, errors |
| `rollout_regression` | `rollout_regression` | `rollout_regression:v2` | service owner / release engineer | latency, errors, cache_miss, new_version |
| `collector_queue_pressure` | `telemetry_delivery` | `telemetry_delivery:v1` | observability platform | latency, telemetry_loss |
