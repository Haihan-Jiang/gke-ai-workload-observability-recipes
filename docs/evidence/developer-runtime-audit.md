# Developer Runtime Audit

Overall status: **PASS**

This audit checks whether contributors have a stable local runtime
contract and repeatable command entrypoints for validation, evidence
generation, demos, and optional Kubernetes smoke tests.

## Summary

| Metric | Value |
| --- | ---: |
| Required files | 4 |
| Present files | 4 |
| Make targets | 8 |
| PHONY targets | 8 |
| Detected fixtures | 8 |

## Checks

| Check | Status |
| --- | --- |
| `required_files` | PASS |
| `make_target_inventory` | PASS |
| `make_command_contract` | PASS |
| `python_runtime_contract` | PASS |
| `developer_runtime_docs` | PASS |
| `output_boundary` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_makefile` | `required_files` | yes |
| `wrong_python_version` | `python_runtime_contract` | yes |
| `missing_ci_target` | `make_target_inventory` | yes |
| `validation_command_bypass` | `make_command_contract` | yes |
| `missing_python_variable` | `python_runtime_contract` | yes |
| `missing_no_pip_boundary` | `developer_runtime_docs` | yes |
| `missing_output_boundary` | `output_boundary` | yes |
| `missing_kind_optional_docs` | `developer_runtime_docs` | yes |
