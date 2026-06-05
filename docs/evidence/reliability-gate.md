# Reliability Gate Evidence

Overall status: **PASS**

This gate turns the replay into an SRE-style reliability check. The lab
does not merely generate traces; it verifies that healthy traffic stays
inside the control SLO and that failure scenarios are classified by the
signal a production team would need during incident triage.

| Gate | Status | Intent |
| --- | --- | --- |
| `healthy_baseline` | pass | The control group should stay inside the inference SLO. |
| `cache_miss_storm_detected` | pass | Cache miss storms should be classified as latency incidents, not model incidents. |
| `dependency_timeout_detected` | pass | Feature-store timeouts should be visible as dependency-driven errors. |
| `rollout_regression_detected` | pass | A bad service version should be separable from baseline traffic. |

## Checks

### healthy_baseline

- PASS: baseline has no user-visible errors
- PASS: baseline p95 latency is <= 100 ms
- PASS: baseline cache miss rate is low

### cache_miss_storm_detected

- PASS: cache miss storm has no synthetic upstream errors
- PASS: cache miss rate is high enough to explain latency
- PASS: cache miss storm breaches the latency SLO

### dependency_timeout_detected

- PASS: dependency timeout creates user-visible errors
- PASS: dependency timeout error rate is material
- PASS: dependency timeout p95 latency is clearly degraded

### rollout_regression_detected

- PASS: rollout regression is tied to service.version=v2
- PASS: rollout regression creates user-visible errors
- PASS: rollout regression breaches the latency SLO

## Resume-Safe Claim

> Built a runnable GKE AI inference reliability lab with OpenTelemetry
> traces, Kubernetes metadata, durable collector queues, incident replay,
> and SLO-style reliability gates for SRE debugging workflows.
