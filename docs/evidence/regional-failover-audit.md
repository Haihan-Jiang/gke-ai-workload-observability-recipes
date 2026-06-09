# Regional Failover Audit

Overall status: **PASS**

This audit checks whether regional or zonal failover decisions are
connected to disaster recovery, capacity risk, synthetic probes,
load-shedding actions, runbook ownership, rollback evidence, and
Kubernetes control-plane hardening.

## Summary

- Events: `5`
- Standby regions: `2`
- Detected negative fixtures: `5`

## Events

| Event | Scenario | Standby region | Standby replicas | Release action |
| --- | --- | --- | ---: | --- |
| `evidence_control_plane_restore` | `baseline` | `us-west1` | 2 | `eligible_for_release` |
| `retrieval_cache_region_failover` | `cache_miss_storm` | `us-west1` | 6 | `require_sre_review_before_rollout` |
| `feature_store_region_failover` | `dependency_timeout` | `us-east1` | 12 | `block_release_or_rollback` |
| `canary_region_rollback` | `rollout_regression` | `us-west1` | 8 | `block_release_or_rollback` |
| `telemetry_region_failover` | `collector_queue_pressure` | `us-east1` | 4 | `require_sre_review_before_rollout` |

## Checks

| Check | Status |
| --- | --- |
| `failover_inventory` | PASS |
| `dr_recovery_contract` | PASS |
| `capacity_failover_guard` | PASS |
| `traffic_safety_linkage` | PASS |
| `rollback_observability_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_telemetry_failover` | yes |
| `restore_exceeds_rto` | yes |
| `standby_capacity_too_small` | yes |
| `wrong_release_action` | yes |
| `missing_collector_queue_control` | yes |
