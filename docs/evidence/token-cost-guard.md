# Token Cost Guard

| Scenario | Model variant | Tokens | GPU ms | Cost / 1k req | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `baseline` | `recommender-small` | 282 | 18 | 0.213 | `allow` |
| `cache_miss_storm` | `recommender-small` | 348 | 38 | 0.262 | `allow` |
| `dependency_timeout` | `recommender-small` | 432 | 82 | 0.338 | `allow` |
| `rollout_regression` | `recommender-v2` | 578 | 210 | 0.477 | `block_or_review` |
| `collector_queue_pressure` | `recommender-small` | 336 | 62 | 0.264 | `allow` |
