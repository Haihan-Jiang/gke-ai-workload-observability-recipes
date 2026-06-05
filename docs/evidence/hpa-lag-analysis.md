# HPA Lag Analysis

| Scenario | Required replicas | Missing | Recovery sec | Decision |
| --- | ---: | ---: | ---: | --- |
| `baseline` | 1 | 0 | 0 | `steady_state` |
| `cache_miss_storm` | 4 | 2 | 105 | `scale` |
| `dependency_timeout` | 17 | 15 | 345 | `fix_dependency_or_rollout` |
| `rollout_regression` | 6 | 4 | 165 | `fix_dependency_or_rollout` |
| `collector_queue_pressure` | 2 | 0 | 0 | `steady_state` |
