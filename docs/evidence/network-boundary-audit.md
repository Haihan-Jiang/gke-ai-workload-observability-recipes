# Network Boundary Audit

Overall status: **PASS**

This audit checks that the sample inference workload has bounded
egress to telemetry and DNS, while the collector keeps inbound OTLP
traffic scoped to workload namespaces. It also rejects allow-all egress
rules and verifies NetworkPolicy owner labels.

## Summary

- NetworkPolicies: `2`
- Workload egress rules: `2`
- Detected negative fixtures: `10`

## Checks

| Check | Status |
| --- | --- |
| `workload_egress_policy` | PASS |
| `workload_policy_selector` | PASS |
| `workload_egress_policy_type` | PASS |
| `telemetry_egress` | PASS |
| `telemetry_ports` | PASS |
| `dns_egress` | PASS |
| `deny_unbounded_egress` | PASS |
| `collector_ingress_boundary` | PASS |
| `network_policy_label_governance` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_workload_egress_policy` | yes |
| `workload_policy_wrong_selector` | yes |
| `missing_egress_policy_type` | yes |
| `missing_telemetry_egress` | yes |
| `wrong_telemetry_namespace_selector` | yes |
| `missing_otlp_http_port` | yes |
| `missing_dns_egress` | yes |
| `allow_all_egress` | yes |
| `collector_ingress_wrong_namespace_selector` | yes |
| `missing_workload_policy_owner_label` | yes |
