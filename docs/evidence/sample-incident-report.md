# Sample Incident Replay Evidence

This is a committed sample output from the local incident replay. It lets a
reviewer inspect the result without running Docker, GKE, or a cloud account.

![Incident replay dashboard](incident-dashboard.svg)

| Scenario | Requests | Errors | p50 ms | p95 ms | Cache miss rate | Triage signal |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| baseline | 8 | 0 | 45 | 48 | 0.0 | Healthy control group; use as the comparison baseline. |
| cache_miss_storm | 7 | 0 | 206 | 251 | 1.0 | Look for cache.result=miss and longer vector-cache spans before tuning the model path. |
| dependency_timeout | 6 | 3 | 1050 | 1320 | 0.0 | Trace child spans isolate feature-store lookup as the dominant latency source. |
| rollout_regression | 7 | 2 | 370 | 455 | 0.43 | Compare service.version=v2 traces against baseline before rolling forward. |

## How To Read This

- `baseline` is the control group for healthy inference traffic.
- `cache_miss_storm` points to the cache path instead of the model path.
- `dependency_timeout` isolates feature-store latency and user-visible errors.
- `rollout_regression` ties degraded behavior to `service.version=v2`.

## Why It Matters

The evidence is intentionally small, but it is shaped like an SRE debugging
artifact: a scenario, measurable signal, trace attributes, and a concrete
triage decision.
