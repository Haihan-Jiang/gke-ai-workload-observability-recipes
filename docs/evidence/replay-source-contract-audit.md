# Replay Source Contract Audit

Overall status: **PASS**

This audit validates the generated incident replay summary and OTLP
payloads before downstream reliability, telemetry, and release gates
consume them.

## Summary

- Scenarios: `5`
- Payloads: `5`
- Root spans: `34`
- Total spans: `136`
- Attribute keys: `19`
- Detected negative fixtures: `7`

## Checks

| Check | Status |
| --- | --- |
| `scenario_inventory` | PASS |
| `summary_contract` | PASS |
| `payload_inventory` | PASS |
| `trace_shape_contract` | PASS |
| `attribute_contract` | PASS |
| `scenario_consistency` | PASS |
| `incident_signal_contract` | PASS |
| `payload_privacy_boundary` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_summary_scenario` | yes |
| `missing_summary_field` | yes |
| `missing_payload` | yes |
| `missing_root_attribute` | yes |
| `missing_child_span` | yes |
| `wrong_scenario_attribute` | yes |
| `raw_prompt_attribute` | yes |
