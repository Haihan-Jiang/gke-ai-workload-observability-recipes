# Tenant Blast Radius

| Scenario | Tenant tier | Blast radius | Violations |
| --- | --- | --- | --- |
| `baseline` | `standard` | `contained` | none |
| `cache_miss_storm` | `standard` | `contained` | none |
| `dependency_timeout` | `standard` | `tenant_slo_breach` | p95 1320ms exceeds 300ms; error rate 0.5 exceeds 0.05 |
| `rollout_regression` | `premium` | `tenant_slo_breach` | p95 455ms exceeds 220ms; error rate 0.29 exceeds 0.02 |
| `collector_queue_pressure` | `standard` | `tenant_slo_breach` | telemetry loss 0.42 exceeds 0.05 |
