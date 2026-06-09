# Post-Incident Review Packet

Overall status: **PASS**

This packet turns replayed reliability incidents into review-ready RCA
records. It ties customer-impact signals, root-cause grouping, rollback
timelines, corrective actions, and preventive controls back to the
generated release evidence.

## Summary

- Deployment decision: `block_production_promotion`
- Reviews: `4`
- Corrective actions: `8`
- Preventive controls: `6`

## Reviews

### cache_miss_storm

- Severity: `SEV-2`
- Owner: Inference platform / retrieval owner
- Root cause: `cache_miss_storm`
- Dedupe key: `cache_miss_storm:v1`
- Budget used events: `5`
- Release action: `require_sre_review_before_rollout`

Corrective actions:
- `cache_miss_storm-A1` Add cache-warm validation before increasing traffic. Owner: Inference platform / retrieval owner; due: 7d
- `cache_miss_storm-A2` Track cache miss rate as a release blocker in the rollout checklist. Owner: Inference platform / retrieval owner; due: 14d

Timeline:
- T+0m `detect`: alert fires or release gate blocks promotion from generated evidence
- T+3m `acknowledge`: incident commander assigns scenario owner and freezes rollout expansion
- T+9m `mitigate`: hold rollout, warm the retrieval cache, and reduce cache churn before resuming traffic expansion
- T+12m `verify`: re-run evidence generation and confirm SLO budget, alerts, dashboard, and runbook status

### dependency_timeout

- Severity: `SEV-1`
- Owner: Feature platform / dependency owner
- Root cause: `dependency_timeout`
- Dedupe key: `dependency_timeout:v1`
- Budget used events: `9`
- Release action: `block_release_or_rollback`

Corrective actions:
- `dependency_timeout-A1` Add bounded retry and fallback-feature behavior for feature-store timeouts. Owner: Feature platform / dependency owner; due: 7d
- `dependency_timeout-A2` Page the dependency owner when feature-store latency breaches the SLO envelope. Owner: Feature platform / dependency owner; due: 14d

Timeline:
- T+0m `detect`: alert fires or release gate blocks promotion from generated evidence
- T+2m `acknowledge`: incident commander assigns scenario owner and freezes rollout expansion
- T+9m `mitigate`: fail closed with fallback features, cap retries, and page the dependency owner before allowing production promotion
- T+13m `verify`: re-run evidence generation and confirm SLO budget, alerts, dashboard, and runbook status

### rollout_regression

- Severity: `SEV-1`
- Owner: Service owner / release engineer
- Root cause: `rollout_regression`
- Dedupe key: `rollout_regression:v2`
- Budget used events: `8`
- Release action: `block_release_or_rollback`

Corrective actions:
- `rollout_regression-A1` Require canary comparison against the stable service version before promotion. Owner: Service owner / release engineer; due: 7d
- `rollout_regression-A2` Keep rollback instructions tied to service.version and image digest evidence. Owner: Service owner / release engineer; due: 14d

Timeline:
- T+0m `detect`: alert fires or release gate blocks promotion from generated evidence
- T+2m `acknowledge`: incident commander assigns scenario owner and freezes rollout expansion
- T+7m `mitigate`: rollback the candidate version or shift traffic back to the stable service version
- T+11m `verify`: re-run evidence generation and confirm SLO budget, alerts, dashboard, and runbook status

### collector_queue_pressure

- Severity: `SEV-2`
- Owner: Observability platform
- Root cause: `telemetry_delivery`
- Dedupe key: `telemetry_delivery:v1`
- Budget used events: `5`
- Release action: `require_sre_review_before_rollout`

Corrective actions:
- `collector_queue_pressure-A1` Validate persistent collector queue storage before declaring dashboards healthy. Owner: Observability platform; due: 7d
- `collector_queue_pressure-A2` Add telemetry-loss checks to release review so app health and evidence health are separated. Owner: Observability platform; due: 14d

Timeline:
- T+0m `detect`: alert fires or release gate blocks promotion from generated evidence
- T+4m `acknowledge`: incident commander assigns scenario owner and freezes rollout expansion
- T+10m `mitigate`: protect persistent collector queues, reduce exporter pressure, and verify telemetry delivery before trusting dashboards
- T+14m `verify`: re-run evidence generation and confirm SLO budget, alerts, dashboard, and runbook status

## Checks

| Check | Status |
| --- | --- |
| `review_coverage` | PASS |
| `required_sections` | PASS |
| `action_item_coverage` | PASS |
| `preventive_control_coverage` | PASS |
| `release_evidence_linkage` | PASS |
| `severity_assignment` | PASS |
