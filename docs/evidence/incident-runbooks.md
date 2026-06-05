# Incident Runbooks

These runbooks are generated from the replay output. They keep the lab
grounded in operational actions instead of stopping at dashboards.

## baseline

- Problem: `P01`
- Owner: SRE / platform
- Trigger: Healthy control group; use as the comparison baseline.
- p95 latency: `48 ms`
- Error rate: `0.0`
- Telemetry loss rate: `0.0`

First checks:
- Confirm p95 latency and error rate match the healthy control group.
- Verify traces include k8s namespace, service.version, cache.result, and incident.scenario.

Mitigation: Use as the comparison group before changing traffic or rollout policy.

## cache_miss_storm

- Problem: `P02`
- Owner: Inference platform / retrieval owner
- Trigger: Look for cache.result=miss and longer vector-cache spans before tuning the model path.
- p95 latency: `251 ms`
- Error rate: `0.0`
- Telemetry loss rate: `0.0`

First checks:
- Filter traces where cache.result=miss.
- Compare vector-cache lookup span time against model inference span time.
- Check whether a rollout, embedding-version change, or cache eviction preceded the storm.

Mitigation: Warm or pin the retrieval cache, reduce cache churn, and protect the model path with rate limits.

## dependency_timeout

- Problem: `P03`
- Owner: Feature platform / dependency owner
- Trigger: Trace child spans isolate feature-store lookup as the dominant latency source.
- p95 latency: `1320 ms`
- Error rate: `0.5`
- Telemetry loss rate: `0.0`

First checks:
- Inspect feature-store lookup child spans for timeout or retry patterns.
- Compare dependency latency against root inference latency.
- Check dependency saturation before scaling the inference deployment.

Mitigation: Fail closed with a fallback feature set, cap retries, and page the dependency owner.

## rollout_regression

- Problem: `P04`
- Owner: Service owner / release engineer
- Trigger: Compare service.version=v2 traces against baseline before rolling forward.
- p95 latency: `455 ms`
- Error rate: `0.29`
- Telemetry loss rate: `0.0`

First checks:
- Split traces by service.version.
- Compare v2 latency and errors against the baseline v1 group.
- Check deployment events, image digest, and config changes for the affected version.

Mitigation: Pause rollout, shift traffic back to the stable version, and keep the failing traces for review.

## collector_queue_pressure

- Problem: `P05`
- Owner: Observability platform
- Trigger: Separate app health from telemetry delivery; inspect collector queue, retry, and exporter backpressure.
- p95 latency: `126 ms`
- Error rate: `0.0`
- Telemetry loss rate: `0.42`

First checks:
- Check collector queue depth, retry counts, and exporter backpressure.
- Confirm the application remains healthy while telemetry loss increases.
- Validate persistent queue storage and collector resource requests.

Mitigation: Scale or restart collectors, protect queue storage, and reduce exporter pressure before declaring dashboards healthy.
