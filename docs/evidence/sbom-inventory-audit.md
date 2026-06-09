# SBOM Inventory Audit

Overall status: **PASS**

This audit generates and validates a local CycloneDX-style SBOM
inventory for third-party GitHub Actions, container images, and
runtime tools used by the lab validation path.

## Summary

| Metric | Value |
| --- | ---: |
| Components | 8 |
| GitHub Actions | 2 |
| Container images | 4 |
| Runtime tools | 2 |
| Source path links | 9 |
| Detected fixtures | 6 |

## Checks

| Check | Status |
| --- | --- |
| `component_discovery` | PASS |
| `sbom_component_coverage` | PASS |
| `cyclonedx_shape` | PASS |
| `source_traceability` | PASS |
| `runtime_boundary` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_action_component` | `sbom_component_coverage` | yes |
| `missing_image_component` | `sbom_component_coverage` | yes |
| `duplicate_bom_ref` | `cyclonedx_shape` | yes |
| `missing_source_path` | `source_traceability` | yes |
| `python_runtime_mismatch` | `runtime_boundary` | yes |
| `uninventoried_action_reference` | `sbom_component_coverage` | yes |
