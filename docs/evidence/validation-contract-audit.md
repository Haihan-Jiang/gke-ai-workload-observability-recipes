# Validation Contract Audit

Overall status: **PASS**

This audit treats the validation scripts as release-critical evidence.
It proves that generated evidence scripts, Python compile coverage,
policy JSON validation, committed evidence JSON validation, and
release-readiness arguments stay synchronized.

## Summary

- Py-compiled demo scripts: `65`
- Generation scripts: `63`
- Direct validation scripts: `62`
- Policy JSON files validated: `58`
- Committed evidence JSON files validated: `73`
- Release-readiness arguments: `62`
- Detected negative fixtures: `6`

## Checks

| Check | Status |
| --- | --- |
| `py_compile_contract` | PASS |
| `generation_validation_contract` | PASS |
| `policy_json_contract` | PASS |
| `committed_json_contract` | PASS |
| `release_readiness_argument_contract` | PASS |
| `required_command_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_py_compile_script` | yes |
| `missing_direct_validation_script` | yes |
| `missing_policy_json_validation` | yes |
| `missing_committed_json_validation` | yes |
| `missing_release_readiness_argument` | yes |
| `missing_required_validate_command` | yes |
