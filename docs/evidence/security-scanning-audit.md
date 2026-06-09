# Security Scanning Audit

Overall status: **PASS**

This audit checks that CodeQL static analysis is configured with safe
triggers, least privilege, Python language coverage, security query
suites, and release-control linkage before security-scanning claims
are trusted.

## Summary

- Workflows: `1`
- Jobs: `1`
- Languages: `1`
- CodeQL actions: `2`
- Query suites: `2`
- Release controls linked: `6`
- Detected negative fixtures: `8`

## Checks

| Check | Status |
| --- | --- |
| `workflow_inventory` | PASS |
| `trigger_contract` | PASS |
| `permission_contract` | PASS |
| `concurrency_contract` | PASS |
| `job_contract` | PASS |
| `codeql_action_contract` | PASS |
| `query_suite_contract` | PASS |
| `release_control_linkage` | PASS |
| `negative_fixture_coverage` | PASS |
