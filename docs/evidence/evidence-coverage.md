# Evidence Coverage

| Scenario | Root spans | Expected reasons | Observed reasons | Status |
| --- | ---: | --- | --- | --- |
| `baseline` | 8 | none | none | PASS |
| `cache_miss_storm` | 7 | none | none | PASS |
| `collector_queue_pressure` | 6 | telemetry_loss | telemetry_loss | PASS |
| `dependency_timeout` | 6 | error, high_latency | error, high_latency | PASS |
| `rollout_regression` | 7 | error, high_latency | error, high_latency | PASS |
