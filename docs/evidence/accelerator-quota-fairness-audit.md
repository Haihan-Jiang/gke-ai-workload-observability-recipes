# Accelerator Quota Fairness Audit

Overall status: **PASS**

This audit checks that GPU/accelerator use is bounded by tenant tier,
that over-quota or over-capacity paths are blocked or reviewed, and
that load shedding protects premium and standard traffic before
best-effort traffic consumes release capacity.

## Summary

- Quotas: `5`
- Candidate quotas: `1`
- Protected tiers: `2`
- Detected negative fixtures: `7`

## Quotas

| Quota | Scenario | Tier | GPU ms | Cost decision | Traffic action |
| --- | --- | --- | ---: | --- | --- |
| `baseline_standard_quota` | `baseline` | `standard` | 18 | `allow` | `no_action` |
| `cache_standard_quota` | `cache_miss_storm` | `standard` | 38 | `allow` | `rate_limit_retrieval` |
| `dependency_standard_quota` | `dependency_timeout` | `standard` | 82 | `allow` | `shed_best_effort` |
| `candidate_premium_quota` | `rollout_regression` | `premium` | 210 | `block_or_review` | `rollback_canary` |
| `telemetry_standard_quota` | `collector_queue_pressure` | `standard` | 62 | `allow` | `protect_telemetry` |

## Checks

| Check | Status |
| --- | --- |
| `quota_inventory` | PASS |
| `accelerator_budget_guard` | PASS |
| `tenant_fairness_contract` | PASS |
| `load_shedding_linkage` | PASS |
| `shadow_candidate_quota` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_candidate_quota` | yes |
| `standard_quota_too_low` | yes |
| `candidate_expected_cost_allows_overage` | yes |
| `premium_not_protected` | yes |
| `best_effort_not_shed` | yes |
| `wrong_traffic_action` | yes |
| `candidate_shadow_not_required` | yes |
