# Threat Model Audit

Overall status: **PASS**

This audit checks that the lab threat model has explicit assets,
trust boundaries, abuse cases, owners, residual risk statements,
committed evidence links, and release-readiness control bindings.

## Summary

| Metric | Value |
| --- | ---: |
| Required files | 5 |
| Present files | 5 |
| Assets | 6 |
| Trust boundaries | 6 |
| Threats | 6 |
| Mitigations | 29 |
| Owners | 6 |
| Residual risk statements | 6 |
| Evidence links | 19 |
| Existing evidence links | 19 |
| Release controls | 19 |
| Detected fixtures | 7 |

## Checks

| Check | Status |
| --- | --- |
| `required_files` | PASS |
| `scope_boundary_contract` | PASS |
| `threat_register_contract` | PASS |
| `mitigation_contract` | PASS |
| `residual_risk_contract` | PASS |
| `evidence_linkage` | PASS |
| `release_control_linkage` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_threat_model_document` | `required_files` | yes |
| `missing_telemetry_export_boundary` | `scope_boundary_contract` | yes |
| `missing_prompt_leakage_threat` | `threat_register_contract` | yes |
| `missing_tailored_mitigation` | `mitigation_contract` | yes |
| `missing_redaction_evidence_link` | `evidence_linkage` | yes |
| `missing_identity_release_control` | `release_control_linkage` | yes |
| `missing_residual_risk_statement` | `residual_risk_contract` | yes |
