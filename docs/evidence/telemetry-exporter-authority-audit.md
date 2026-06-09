# Telemetry Exporter Authority Audit

Overall status: **PASS**

This audit verifies that the collector has an explicit authoritative
upstream telemetry exporter, keeps local debug export bounded, and
uses queued retry delivery for traces and metrics.

## Summary

| Metric | Value |
| --- | ---: |
| Exporters | 2 |
| Authoritative pipelines | 2 |
| Local debug pipelines | 2 |
| Queued exporters | 1 |
| Retry-enabled exporters | 1 |
| Detected fixtures | 8 |

## Checks

| Check | Status |
| --- | --- |
| `collector_config_map` | PASS |
| `exporter_authority_annotations` | PASS |
| `authoritative_pipeline_path` | PASS |
| `local_debug_boundary` | PASS |
| `secure_upstream_endpoint` | PASS |
| `queued_delivery_boundary` | PASS |
| `production_replacement_docs` | PASS |
| `negative_fixture_coverage` | PASS |

## Pipelines

| Pipeline | Exporters |
| --- | --- |
| `traces` | `debug, otlphttp/upstream` |
| `metrics` | `debug, otlphttp/upstream` |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_authoritative_exporter_annotation` | `exporter_authority_annotations` | yes |
| `debug_declared_authoritative` | `exporter_authority_annotations` | yes |
| `traces_missing_authoritative_exporter` | `authoritative_pipeline_path` | yes |
| `metrics_debug_only` | `local_debug_boundary` | yes |
| `insecure_http_upstream` | `secure_upstream_endpoint` | yes |
| `localhost_upstream` | `secure_upstream_endpoint` | yes |
| `disabled_upstream_queue` | `queued_delivery_boundary` | yes |
| `missing_replacement_docs` | `production_replacement_docs` | yes |
