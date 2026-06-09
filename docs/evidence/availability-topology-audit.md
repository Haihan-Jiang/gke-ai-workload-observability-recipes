# Availability Topology Audit

Overall status: **PASS**

This audit checks whether the GKE recipe has explicit availability
and voluntary-disruption boundaries. It verifies replica floors,
PodDisruptionBudget coverage, topology spread constraints for the
multi-replica inference workload, selector alignment, and owner labels.

## Summary

- Workloads: `2`
- PodDisruptionBudgets: `2`
- Topology spread constraints: `2`
- Detected negative fixtures: `7`

## Workloads

| Workload | Mode | Replicas | PDB | minAvailable | Topology keys |
| --- | --- | ---: | --- | ---: | --- |
| `telemetry/otel-collector` | `guarded_singleton` | 1 | `otel-collector` | 1 | - |
| `ai-observability-demo/toy-ai-inference-api` | `multi_replica` | 2 | `toy-ai-inference-api` | 1 | `topology.kubernetes.io/zone`, `kubernetes.io/hostname` |

## Checks

| Check | Status |
| --- | --- |
| `workload_inventory` | PASS |
| `replica_policy` | PASS |
| `pdb_coverage` | PASS |
| `topology_spread_coverage` | PASS |
| `spread_selector_matches_pod_labels` | PASS |
| `availability_label_governance` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `collector_replicas_zero` | yes |
| `missing_sample_pdb` | yes |
| `sample_pdb_min_equals_replicas` | yes |
| `missing_sample_zone_spread` | yes |
| `wrong_sample_hostname_spread_key` | yes |
| `sample_spread_selector_mismatch` | yes |
| `missing_sample_pdb_owner_label` | yes |
