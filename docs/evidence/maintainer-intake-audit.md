# Maintainer Intake Audit

Overall status: **PASS**

This audit checks that public issue, pull request, and support intake
surfaces ask for reproducible evidence, validation commands, security
routing, no-secret boundaries, and support expectations before the
repository is treated as maintainer-ready.

## Summary

| Metric | Value |
| --- | ---: |
| Required files | 6 |
| Present files | 6 |
| Issue templates | 2 |
| PR validation commands | 3 |
| Support terms | 5 |
| Detected fixtures | 6 |

## Checks

| Check | Status |
| --- | --- |
| `required_files` | PASS |
| `issue_intake_contract` | PASS |
| `feature_request_contract` | PASS |
| `issue_security_boundary` | PASS |
| `pull_request_validation_contract` | PASS |
| `support_boundary` | PASS |
| `contribution_summary_linkage` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_bug_template` | `required_files` | yes |
| `missing_no_secret_bug_text` | `issue_intake_contract` | yes |
| `missing_feature_validation_plan` | `feature_request_contract` | yes |
| `missing_security_redirect` | `issue_security_boundary` | yes |
| `missing_ci_validation_command` | `pull_request_validation_contract` | yes |
| `missing_support_boundary` | `support_boundary` | yes |
