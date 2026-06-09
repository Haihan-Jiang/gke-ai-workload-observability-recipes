# Public Claim Evidence Audit

Overall status: **PASS**

This audit verifies that public README and industry-map claims are
backed by committed evidence, release-readiness source checks, and
explicit boundary language.

## Summary

- Claims checked: `17`
- Evidence-backed claims: `17`
- Release checks referenced: `17`
- Boundary statements: `3`
- Surfaces checked: `2`
- Detected negative fixtures: `6`

## Checks

| Check | Status |
| --- | --- |
| `claim_text_contract` | PASS |
| `evidence_status_contract` | PASS |
| `evidence_metric_contract` | PASS |
| `release_check_contract` | PASS |
| `boundary_language_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_readme_claim` | yes |
| `failed_evidence_status` | yes |
| `low_evidence_metric` | yes |
| `missing_release_check` | yes |
| `missing_boundary_statement` | yes |
| `forbidden_public_claim` | yes |
