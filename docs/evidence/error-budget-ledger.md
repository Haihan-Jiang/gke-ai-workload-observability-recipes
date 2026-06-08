# Error Budget Ledger

Overall status: **PASS**

This ledger turns the OpenSLO objective into a replay-level budget
accounting artifact. It estimates which scenarios stay inside budget,
which need manual SRE review, and which should block a rollout or
trigger rollback before production promotion.

## Objective

- Target: `99.5%`
- Time window: `30d`
- Budgeting method: `Occurrences`
- Allowed bad-event fraction: `0.005`
- Latency envelope: `p95 <= 100 ms`

## Ledger

| Scenario | Allowed | Used | Ratio | Decision | Release action | Sources |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `baseline` | 1 | 0 | 0.0 | `within_budget` | `eligible_for_release` | errors=0, latency=0, telemetry=0 |
| `cache_miss_storm` | 1 | 5 | 5.0 | `manual_review_required` | `require_sre_review_before_rollout` | errors=0, latency=5, telemetry=0 |
| `dependency_timeout` | 1 | 9 | 9.0 | `budget_exhausted` | `block_release_or_rollback` | errors=3, latency=6, telemetry=0 |
| `rollout_regression` | 1 | 8 | 8.0 | `budget_exhausted` | `block_release_or_rollback` | errors=2, latency=6, telemetry=0 |
| `collector_queue_pressure` | 1 | 5 | 5.0 | `manual_review_required` | `require_sre_review_before_rollout` | errors=0, latency=2, telemetry=3 |

## Checks

| Check | Status |
| --- | --- |
| `objective_target` | PASS |
| `scenario_coverage` | PASS |
| `baseline_within_budget` | PASS |
| `incident_budget_pressure` | PASS |
| `release_action_mapping` | PASS |
| `math_consistency` | PASS |
