# Pod Security Admission Audit

Overall status: **PASS**

This audit verifies that namespaces enforce the Kubernetes restricted
Pod Security Admission profile and that collector/workload pod templates
remain compatible with that profile.

## Summary

- Namespaces: `2`
- Workloads: `2`
- Restricted namespaces: `2`
- Restricted workloads: `2`
- Detected negative fixtures: `10`

## Workloads

| Workload | PSA labels | Pod security | Container security | Volumes |
| --- | --- | --- | --- | --- |
| `telemetry/otel-collector` | PASS | PASS | PASS | PASS |
| `ai-observability-demo/toy-ai-inference-api` | PASS | PASS | PASS | PASS |

## Checks

| Check | Status |
| --- | --- |
| `namespace_psa_labels` | PASS |
| `namespace_label_governance` | PASS |
| `restricted_pod_security` | PASS |
| `restricted_container_security` | PASS |
| `restricted_volume_types` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `telemetry_missing_enforce_label` | yes |
| `workload_enforce_baseline` | yes |
| `telemetry_missing_warn_version` | yes |
| `collector_privileged_container` | yes |
| `sample_allows_privilege_escalation` | yes |
| `collector_adds_net_raw` | yes |
| `sample_host_network` | yes |
| `collector_host_path_volume` | yes |
| `sample_missing_seccomp` | yes |
| `collector_run_as_root` | yes |
