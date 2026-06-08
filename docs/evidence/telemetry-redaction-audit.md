# Telemetry Redaction Audit

Overall status: **PASS**

This audit checks the generated OTLP trace payloads before treating
them as production-style evidence. It allows operational AI metadata
such as token counts, model variant, latency, queue wait, and GPU time,
while blocking prompt text, completion text, request/response bodies,
secrets, direct identifiers, and oversized string attributes.

## Summary

- Payloads: `5`
- Scenarios: `5`
- Attributes inspected: `957`
- Redaction violations: `0`

## Checks

| Check | Status |
| --- | --- |
| `payload_coverage` | PASS |
| `resource_context` | PASS |
| `span_context` | PASS |
| `approved_ai_metadata` | PASS |
| `forbidden_attribute_keys` | PASS |
| `forbidden_attribute_values` | PASS |
| `string_value_budget` | PASS |
