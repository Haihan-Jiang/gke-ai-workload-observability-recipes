# Data Handling Audit

Overall status: **PASS**

This audit checks that public data-handling claims have explicit data
classes, owners, retention statements, forbidden-data boundaries,
committed evidence links, and release-readiness control bindings.

## Summary

| Metric | Value |
| --- | ---: |
| Required files | 6 |
| Present files | 6 |
| Data classes | 6 |
| Handling terms | 54 |
| Retention terms | 6 |
| Owners | 6 |
| Evidence links | 18 |
| Existing evidence links | 18 |
| Release controls | 18 |
| Detected fixtures | 7 |

## Checks

| Check | Status |
| --- | --- |
| `required_files` | PASS |
| `data_class_contract` | PASS |
| `handling_contract` | PASS |
| `retention_contract` | PASS |
| `owner_contract` | PASS |
| `evidence_linkage` | PASS |
| `release_control_linkage` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_data_handling_document` | `required_files` | yes |
| `missing_model_label_class` | `data_class_contract` | yes |
| `missing_prompt_forbidden_term` | `handling_contract` | yes |
| `missing_retention_budget` | `retention_contract` | yes |
| `missing_redaction_evidence_link` | `evidence_linkage` | yes |
| `missing_exporter_release_control` | `release_control_linkage` | yes |
| `missing_security_owner` | `owner_contract` | yes |
