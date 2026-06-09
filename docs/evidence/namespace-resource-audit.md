# Namespace Resource Audit

Overall status: **PASS**

This audit checks namespace-level ResourceQuota and LimitRange controls
for the telemetry plane and sample AI workload namespace. It verifies
that quotas exist, cover current Deployment resource use with headroom,
and include container defaults and sane CPU/memory bounds.

## Summary

- Namespaces: `2`
- Checks: `8`
- Detected negative fixtures: `8`

## Namespaces

| Namespace | Role | ResourceQuota | LimitRange | Pods used | CPU request m | Memory request Mi |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `telemetry` | `telemetry` | `telemetry-resource-quota` | `telemetry-limit-range` | 1 | 100 | 256 |
| `ai-observability-demo` | `workload` | `ai-workload-resource-quota` | `ai-workload-limit-range` | 2 | 100 | 128 |

## Checks

| Check | Status |
| --- | --- |
| `namespace_inventory` | PASS |
| `namespace_governance_labels` | PASS |
| `namespace_resource_quota` | PASS |
| `quota_covers_workloads` | PASS |
| `namespace_limit_range` | PASS |
| `container_defaulting` | PASS |
| `limit_range_sane_bounds` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_telemetry_quota` | yes |
| `missing_workload_limit_range` | yes |
| `telemetry_cpu_quota_too_low` | yes |
| `workload_memory_quota_too_low` | yes |
| `missing_quota_services_key` | yes |
| `missing_container_default_request` | yes |
| `limit_range_max_below_default` | yes |
| `namespace_missing_owner_label` | yes |
