# Repository Governance Audit

Overall status: **PASS**

This audit checks whether the public repository has enough governance
surface for contributors and reviewers to understand validation,
security reporting, ownership, release evidence, and project
boundaries.

## Summary

| Metric | Value |
| --- | ---: |
| Required files | 6 |
| Present files | 6 |
| CODEOWNERS patterns | 9 |
| Owned patterns | 9 |
| Detected fixtures | 8 |

## Checks

| Check | Status |
| --- | --- |
| `required_files` | PASS |
| `contribution_workflow` | PASS |
| `security_reporting` | PASS |
| `release_process` | PASS |
| `codeowners_coverage` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_contributing` | `required_files` | yes |
| `missing_security_private_channel` | `security_reporting` | yes |
| `missing_ci_mode_validation` | `contribution_workflow` | yes |
| `missing_release_evidence_review` | `release_process` | yes |
| `missing_default_codeowner` | `codeowners_coverage` | yes |
| `wrong_codeowner` | `codeowners_coverage` | yes |
| `missing_no_paid_dependency_boundary` | `contribution_workflow` | yes |
| `missing_clean_merge_state_step` | `release_process` | yes |
