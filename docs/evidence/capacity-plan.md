# Capacity Plan Evidence

This report converts replayed p95 latency into a rough serving-capacity
check. It is not a cloud cost estimate; it is a deterministic local
sanity check for whether a scenario is a scaling problem or a reliability
problem that must be fixed before adding replicas.

- Target RPS: `100`
- Concurrency per replica: `8`
- Headroom factor: `1.4`
- Replica budget: `12`

| Scenario | Bottleneck | p95 ms | Est. RPS / replica | Required replicas | Warnings |
| --- | --- | ---: | ---: | ---: | --- |
| baseline | normal inference path | 48 | 166.67 | 1 | none |
| cache_miss_storm | vector cache and retrieval path | 251 | 31.87 | 5 | none |
| dependency_timeout | feature-store dependency | 1320 | 6.06 | 24 | do not scale traffic until user-visible errors are isolated; required replicas exceed the demo budget; treat as a dependency or design issue |
| rollout_regression | service rollout and version skew | 455 | 17.58 | 8 | do not scale traffic until user-visible errors are isolated |
| collector_queue_pressure | telemetry collector delivery path | 126 | 63.49 | 3 | fix collector delivery before trusting production dashboards |

## How To Use This

- If only latency is high and there are no errors, test cache and scaling changes.
- If error rate is high, treat the scenario as an incident before scaling traffic.
- If telemetry loss is high, fix collector/exporter delivery before trusting dashboards.
