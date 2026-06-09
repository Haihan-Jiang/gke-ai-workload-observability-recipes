# Shadow Traffic Replay Audit

Overall status: **PASS**

This audit checks that shadow traffic for an AI inference candidate is
isolated from users, privacy-safe, sampled enough to be useful, compared
against rollout and cost gates, and linked to rollback/probe evidence.

## Summary

- Replays: `2`
- Candidate replays: `1`
- Blocked shadow candidates: `1`
- Detected negative fixtures: `7`

## Replays

| Replay | Role | Scenario | Shadow % | Served to users | Expected action |
| --- | --- | --- | ---: | --- | --- |
| `stable_baseline_shadow` | `stable` | `baseline` | 5 | `False` | `eligible_for_release` |
| `candidate_v2_shadow` | `candidate` | `rollout_regression` | 5 | `False` | `block_release_or_rollback` |

## Checks

| Check | Status |
| --- | --- |
| `shadow_inventory` | PASS |
| `isolation_contract` | PASS |
| `privacy_contract` | PASS |
| `candidate_comparison_gate` | PASS |
| `cost_budget_gate` | PASS |
| `rollback_probe_linkage` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Replay | Detected |
| --- | --- | --- |
| `missing_candidate_shadow` | `candidate_v2_shadow` | yes |
| `candidate_shadow_serves_users` | `candidate_v2_shadow` | yes |
| `candidate_shadow_too_large` | `candidate_v2_shadow` | yes |
| `candidate_shadow_stores_prompt` | `candidate_v2_shadow` | yes |
| `wrong_rollout_decision` | `candidate_v2_shadow` | yes |
| `wrong_cost_decision` | `candidate_v2_shadow` | yes |
| `wrong_candidate_probe` | `candidate_v2_shadow` | yes |
