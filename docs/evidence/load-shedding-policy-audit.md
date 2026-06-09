# Load Shedding Policy Audit

Overall status: **PASS**

This audit checks that overload and incident paths have explicit
graceful-degradation decisions before release promotion. The policy
links capacity warnings, tenant blast radius, token/GPU cost review,
error-budget release actions, preflight probes, and runbook ownership.

## Summary

- Actions: `5`
- Protective actions: `4`
- Detected negative fixtures: `5`

## Actions

| Action | Scenario | Traffic action | Protected tiers | Shed tiers | Release action |
| --- | --- | --- | --- | --- | --- |
| `baseline_no_shed` | `baseline` | `no_action` | `premium, standard` | `none` | `eligible_for_release` |
| `cache_retrieval_rate_limit` | `cache_miss_storm` | `rate_limit_retrieval` | `premium, standard` | `best_effort` | `require_sre_review_before_rollout` |
| `feature_store_fail_closed` | `dependency_timeout` | `shed_best_effort` | `premium, standard` | `best_effort` | `block_release_or_rollback` |
| `canary_rollback_and_model_fallback` | `rollout_regression` | `rollback_canary` | `premium, standard` | `best_effort` | `block_release_or_rollback` |
| `telemetry_queue_protection` | `collector_queue_pressure` | `protect_telemetry` | `premium, standard` | `best_effort` | `require_sre_review_before_rollout` |

## Checks

| Check | Status |
| --- | --- |
| `action_inventory` | PASS |
| `capacity_guardrail` | PASS |
| `tenant_priority_contract` | PASS |
| `cost_guardrail_linkage` | PASS |
| `release_probe_runbook_linkage` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Scenario | Detected |
| --- | --- | --- |
| `missing_dependency_action` | `dependency_timeout` | yes |
| `scale_only_dependency_timeout` | `dependency_timeout` | yes |
| `shed_premium_canary` | `rollout_regression` | yes |
| `missing_cost_review` | `rollout_regression` | yes |
| `wrong_release_action` | `dependency_timeout` | yes |
