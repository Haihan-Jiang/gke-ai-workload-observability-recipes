# Rollback Drill Evidence

Overall status: **PASS**

This report turns the release gate, error-budget ledger, and generated
runbooks into an incident-response drill. It checks whether the lab has
named owners, rollback/manual-review paths, and an RTO-bounded timeline
for each non-healthy replay scenario.

## Summary

- Deployment decision: `block_production_promotion`
- RTO: `15 minutes`
- RPO: `5 minutes`
- Drills: `4`
- Rollback required: `2`
- Manual review: `2`

## Drills

| Scenario | Response | Owner | Complete by | Within RTO | Release action |
| --- | --- | --- | ---: | --- | --- |
| `cache_miss_storm` | `manual_review` | Inference platform / retrieval owner | 12m | True | `require_sre_review_before_rollout` |
| `dependency_timeout` | `rollback_required` | Feature platform / dependency owner | 13m | True | `block_release_or_rollback` |
| `rollout_regression` | `rollback_required` | Service owner / release engineer | 11m | True | `block_release_or_rollback` |
| `collector_queue_pressure` | `manual_review` | Observability platform | 14m | True | `require_sre_review_before_rollout` |

## Timeline Detail

### cache_miss_storm

- T+0m `detect`: alert fires or release gate blocks promotion from generated evidence
- T+3m `acknowledge`: incident commander assigns scenario owner and freezes rollout expansion
- T+9m `mitigate`: hold rollout, warm the retrieval cache, and reduce cache churn before resuming traffic expansion
- T+12m `verify`: re-run evidence generation and confirm SLO budget, alerts, dashboard, and runbook status

### dependency_timeout

- T+0m `detect`: alert fires or release gate blocks promotion from generated evidence
- T+2m `acknowledge`: incident commander assigns scenario owner and freezes rollout expansion
- T+9m `mitigate`: fail closed with fallback features, cap retries, and page the dependency owner before allowing production promotion
- T+13m `verify`: re-run evidence generation and confirm SLO budget, alerts, dashboard, and runbook status

### rollout_regression

- T+0m `detect`: alert fires or release gate blocks promotion from generated evidence
- T+2m `acknowledge`: incident commander assigns scenario owner and freezes rollout expansion
- T+7m `mitigate`: rollback the candidate version or shift traffic back to the stable service version
- T+11m `verify`: re-run evidence generation and confirm SLO budget, alerts, dashboard, and runbook status

### collector_queue_pressure

- T+0m `detect`: alert fires or release gate blocks promotion from generated evidence
- T+4m `acknowledge`: incident commander assigns scenario owner and freezes rollout expansion
- T+10m `mitigate`: protect persistent collector queues, reduce exporter pressure, and verify telemetry delivery before trusting dashboards
- T+14m `verify`: re-run evidence generation and confirm SLO budget, alerts, dashboard, and runbook status

## Checks

| Check | Status |
| --- | --- |
| `scenario_coverage` | PASS |
| `runbook_linkage` | PASS |
| `rollback_path` | PASS |
| `manual_review_path` | PASS |
| `rto_coverage` | PASS |
| `owner_coverage` | PASS |
| `release_policy_linkage` | PASS |
