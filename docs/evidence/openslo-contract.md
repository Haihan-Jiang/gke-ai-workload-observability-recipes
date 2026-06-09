# OpenSLO Contract Evidence

Overall status: **PASS**

This generated contract makes the lab's SLO machine-readable. It ties
the service objective to Prometheus SLI queries, scenario coverage,
telemetry-quality evidence, alerting rules, dashboards, release
readiness, and runbooks.

## Contract

- Name: `gke-ai-inference-availability`
- Service: `toy-ai-inference-api`
- Target: `99.5%`
- Time window: `30d`

## Checks

| Check | Status |
| --- | --- |
| `openslo_shape` | PASS |
| `objective_target` | PASS |
| `prometheus_ratio_metric` | PASS |
| `latency_guardrails` | PASS |
| `scenario_coverage` | PASS |
| `operational_links` | PASS |
| `telemetry_quality` | PASS |
| `yaml_rendered` | PASS |
