# Critical Path Attribution

| Scenario | Dominant span | Dominance | Actionable |
| --- | --- | ---: | --- |
| `baseline` | `model inference` | 0.667 | True |
| `cache_miss_storm` | `vector-cache lookup` | 0.533 | True |
| `collector_queue_pressure` | `model inference` | 0.755 | True |
| `dependency_timeout` | `feature-store lookup` | 0.857 | True |
| `rollout_regression` | `model inference` | 0.664 | True |
