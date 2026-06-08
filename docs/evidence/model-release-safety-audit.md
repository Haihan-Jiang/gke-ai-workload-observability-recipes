# Model Release Safety Audit

Overall status: **PASS**

This audit checks that model-version rollout decisions are tied to
artifact pinning, offline evaluation, schema compatibility, canary
signals, token/GPU cost deltas, rollback evidence, and observability
labels before production promotion.

## Summary

- Releases: `2`
- Candidate releases: `1`
- Blocked candidates: `1`
- Detected negative fixtures: `7`

## Releases

| Release | Role | Scenario | Model | Version | Release action | Cost decision |
| --- | --- | --- | --- | --- | --- | --- |
| `recommender-small-stable` | `stable` | `baseline` | `recommender-small` | `v1` | `eligible_for_release` | `allow` |
| `recommender-v2-candidate` | `candidate` | `rollout_regression` | `recommender-v2` | `v2` | `block_release_or_rollback` | `block_or_review` |

## Checks

| Check | Status |
| --- | --- |
| `artifact_inventory` | PASS |
| `eval_schema_gate` | PASS |
| `canary_rollout_gate` | PASS |
| `cost_budget_gate` | PASS |
| `release_budget_linkage` | PASS |
| `rollback_contract` | PASS |
| `observability_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Release | Detected |
| --- | --- | --- |
| `missing_candidate_release` | `recommender-v2-candidate` | yes |
| `candidate_artifact_unpinned` | `recommender-v2-candidate` | yes |
| `stable_eval_below_threshold` | `recommender-small-stable` | yes |
| `candidate_canary_too_large` | `recommender-v2-candidate` | yes |
| `wrong_cost_expectation` | `recommender-v2-candidate` | yes |
| `missing_rollback_target` | `recommender-v2-candidate` | yes |
| `wrong_candidate_probe` | `recommender-v2-candidate` | yes |
