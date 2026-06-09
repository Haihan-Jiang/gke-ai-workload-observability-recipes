# Reviewer Reproducibility Audit

Overall status: **PASS**

This audit checks that reviewers have a short current-head proof path,
including reproducible commands, committed evidence packet links,
release-readiness control linkage, and project boundary language.

## Summary

| Metric | Value |
| --- | ---: |
| Required files | 8 |
| Present files | 8 |
| Commands | 6 |
| Evidence paths | 6 |
| Existing evidence paths | 6 |
| Boundary terms | 7 |
| Release controls | 6 |
| Detected fixtures | 6 |

## Checks

| Check | Status |
| --- | --- |
| `required_files` | PASS |
| `reviewer_command_contract` | PASS |
| `evidence_packet_contract` | PASS |
| `review_boundary_contract` | PASS |
| `release_control_linkage` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_reviewer_quickstart` | `required_files` | yes |
| `missing_ci_command` | `reviewer_command_contract` | yes |
| `missing_provenance_packet_link` | `evidence_packet_contract` | yes |
| `missing_no_cloud_boundary` | `review_boundary_contract` | yes |
| `missing_proof_packet_control` | `release_control_linkage` | yes |
| `missing_current_head_phrase` | `review_boundary_contract` | yes |
