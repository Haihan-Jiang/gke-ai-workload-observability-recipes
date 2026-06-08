# Release Waiver Governance

Overall status: **PASS**

This audit checks release exception requests against generated
deployment, error-budget, rollback, and post-incident evidence. It
allows only bounded manual-review exceptions and denies
production-promotion overrides for budget-exhausted scenarios.

## Summary

- Deployment decision: `block_production_promotion`
- Waivers: `4`
- Conditional approvals: `2`
- Denied overrides: `2`
- Invalid waivers: `0`
- Unsafe approvals: `0`

## Waiver Decisions

| Waiver | Scenario | Ledger decision | Governance decision | Failed checks |
| --- | --- | --- | --- | --- |
| `WVR-CACHE-001` | `cache_miss_storm` | `manual_review_required` | `conditionally_approved` | - |
| `WVR-COLLECTOR-001` | `collector_queue_pressure` | `manual_review_required` | `conditionally_approved` | - |
| `WVR-DEPENDENCY-001` | `dependency_timeout` | `budget_exhausted` | `denied_override` | - |
| `WVR-ROLLOUT-001` | `rollout_regression` | `budget_exhausted` | `denied_override` | - |

## Negative Fixtures

| Fixture | Decision | Failed checks |
| --- | --- | --- |
| `expired` | `invalid_request` | validity_window |
| `missing_approver` | `invalid_request` | owner_approvals |
| `missing_evidence` | `invalid_request` | evidence_linkage |
| `missing_rollback_link` | `invalid_request` | scenario_linkage |
| `missing_review_link` | `invalid_request` | scenario_linkage |
| `excessive_duration` | `invalid_request` | validity_window |
| `understated_budget` | `invalid_request` | budget_acknowledgement |
| `unknown_scenario` | `invalid_request` | known_scenario, validity_window, scenario_linkage, budget_acknowledgement |

## Checks

| Check | Status |
| --- | --- |
| `waiver_coverage` | PASS |
| `conditional_approval_path` | PASS |
| `deny_override_path` | PASS |
| `no_invalid_waivers` | PASS |
| `no_unsafe_approvals` | PASS |
| `negative_fixture_coverage` | PASS |
| `release_policy_linkage` | PASS |
