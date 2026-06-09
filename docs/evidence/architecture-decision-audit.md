# Architecture Decision Audit

Overall status: **PASS**

This audit checks that Architecture Decision Records are accepted,
include rationale and rejected alternatives, link to committed evidence,
and name the release controls that enforce the decision.

## Summary

| Metric | Value |
| --- | ---: |
| Required files | 5 |
| Present files | 5 |
| Decisions | 4 |
| Accepted decisions | 4 |
| Evidence links | 18 |
| Existing evidence links | 18 |
| Release controls | 18 |
| Detected fixtures | 7 |

## Checks

| Check | Status |
| --- | --- |
| `required_files` | PASS |
| `adr_section_contract` | PASS |
| `decision_rationale` | PASS |
| `evidence_linkage` | PASS |
| `release_control_linkage` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_adr_readme` | `required_files` | yes |
| `pending_decision_status` | `adr_section_contract` | yes |
| `missing_decision_section` | `adr_section_contract` | yes |
| `missing_rejected_alternative` | `adr_section_contract` | yes |
| `missing_evidence_link` | `evidence_linkage` | yes |
| `missing_release_control` | `release_control_linkage` | yes |
| `missing_policy_as_code_term` | `decision_rationale` | yes |
