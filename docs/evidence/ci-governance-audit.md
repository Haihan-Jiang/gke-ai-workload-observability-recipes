# CI Governance Audit

Overall status: **PASS**

This audit checks the GitHub Actions workflow before treating CI as
release-readiness evidence. It requires least-privilege repository
permissions, bounded execution, concurrency cancellation, maintained
Node-runtime action versions, and a stable validation command.

## Summary

| Metric | Value |
| --- | ---: |
| Workflows | 1 |
| Jobs | 1 |
| Actions | 2 |
| Hardened actions | 2 |
| Detected fixtures | 8 |

## Checks

| Check | Status |
| --- | --- |
| `workflow_inventory` | PASS |
| `trigger_surface` | PASS |
| `least_privilege_permissions` | PASS |
| `concurrency_cancellation` | PASS |
| `action_runtime_hygiene` | PASS |
| `job_execution_bounds` | PASS |
| `validation_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_top_level_permissions` | `least_privilege_permissions` | yes |
| `write_all_permissions` | `least_privilege_permissions` | yes |
| `checkout_node20_runtime` | `action_runtime_hygiene` | yes |
| `setup_python_floating_ref` | `action_runtime_hygiene` | yes |
| `missing_concurrency` | `concurrency_cancellation` | yes |
| `missing_timeout` | `job_execution_bounds` | yes |
| `validation_bypass` | `validation_contract` | yes |
| `unsafe_pr_target_trigger` | `trigger_surface` | yes |
