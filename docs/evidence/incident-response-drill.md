# Incident Response Drill

Overall status: **PASS**

This drill verifies the executable response path behind the lab's
generated alerts. It checks that each alert has a runbook owner, an
SLA-bound acknowledgement/mitigation/verification path, escalation
steps, and incident evidence for rollback and post-incident review.

## Summary

- Responses: `5`
- Incident responses: `4`
- Page routes: `4`
- Ticket routes: `1`
- Detected negative fixtures: `5`

## Routes

| Scenario | Severity | Owner | Ack | Mitigate | Verify |
| --- | --- | --- | ---: | ---: | ---: |
| `baseline` | `page` | SRE / platform | 3m/5m | 12m/15m | 18m/30m |
| `cache_miss_storm` | `ticket` | Inference platform / retrieval owner | 3m/30m | 9m/120m | 12m/240m |
| `dependency_timeout` | `page` | Feature platform / dependency owner | 2m/5m | 9m/15m | 13m/30m |
| `rollout_regression` | `page` | Service owner / release engineer | 2m/5m | 7m/15m | 11m/30m |
| `collector_queue_pressure` | `page` | Observability platform | 4m/5m | 10m/15m | 14m/30m |

## Checks

| Check | Status |
| --- | --- |
| `route_coverage` | PASS |
| `owner_coverage` | PASS |
| `timeline_phase_coverage` | PASS |
| `response_sla` | PASS |
| `escalation_coverage` | PASS |
| `incident_evidence_linkage` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Scenario | Detected |
| --- | --- | --- |
| `missing_runbook_owner` | `dependency_timeout` | yes |
| `slow_page_ack` | `rollout_regression` | yes |
| `missing_escalation` | `page` | yes |
| `missing_post_incident_review` | `collector_queue_pressure` | yes |
| `unknown_alert_severity` | `dependency_timeout` | yes |
