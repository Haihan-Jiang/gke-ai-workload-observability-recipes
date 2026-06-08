# GKE AI Inference Reliability Lab

A production-oriented Kubernetes observability and reliability lab for AI
inference workloads using OpenTelemetry.

The goal is practical: show how a platform/SRE team can replay inference
incidents, validate SLO-style reliability gates, wire Kubernetes metadata, and
keep collector delivery durable before an AI service reaches production.
The second-stage goal is to make the lab look credible from code review, not
only from prose: the repo now includes multi-window burn-rate analysis, canary
rollback decisions, OTLP trace-quality auditing, collector outage modeling,
incident correlation, critical-path attribution, evidence coverage checks,
HPA lag modeling, tenant blast-radius detection, and token/GPU cost guardrails.

This repository is a personal reference project. Related upstream Google Cloud
OpenTelemetry sample PRs are tracked in
[docs/google-oss-upstream.md](docs/google-oss-upstream.md), but pending PRs are
not described as merged.

![Incident replay dashboard](docs/evidence/incident-dashboard.svg)

## What This Demonstrates

- A zero-cost local incident replay with no Python dependencies.
- AI inference scenarios for baseline traffic, cache-miss latency, dependency
  timeout, rollout regression, and collector queue pressure.
- Configurable SLO-style reliability gates that verify the healthy baseline
  and classify failure scenarios by the production signal an SRE would need.
- Capacity-planning evidence that separates scaling problems from reliability
  incidents.
- Generated runbooks for first-response debugging.
- Advanced reliability controls for burn-rate paging, canary rollback, trace
  quality, collector outage resilience, and alert deduplication.
- Detailed inference controls for critical-path attribution, sampling evidence
  coverage, HPA lag, tenant blast radius, and token/GPU cost guardrails.
- A policy-as-code deployment decision that combines SLO, burn-rate, rollout,
  trace, collector, autoscaling, tenant, and cost signals into one promotion
  gate.
- Policy regression fixtures that prove promote, block, and manual-review
  decisions stay stable across release-risk scenarios.
- A release-readiness report that checks committed evidence coverage.
- A generated incident report that turns raw telemetry into a reviewer-friendly
  debugging narrative.
- Committed evidence artifacts so reviewers can inspect the replay result
  without running the lab first.
- A GKE/Kubernetes collector layout with resource context and durable queue
  storage.
- Cross-namespace OpenTelemetry auto-instrumentation references.
- A concise production checklist for SRE/platform review.
- A case study that connects the work to real incident-debugging needs.
- Optional Docker Compose wiring for OpenTelemetry Collector and Jaeger.
- Optional kind smoke test that applies the Kubernetes manifests, port-forwards
  the collector, replays incidents, and runs the reliability gate.

## Quick Start

Validate the repo:

```bash
./scripts/validate.sh
```

Run the local demo:

```bash
./scripts/run-local-demo.sh
```

This replays five AI inference incidents, sends OTLP/HTTP traces, and writes:

```text
out/incident-replay/report.md
out/incident-replay/summary.json
```

Run the reliability gate against the generated replay:

```bash
python3 demo/reliability_gate.py \
  --summary out/incident-replay/summary.json \
  --slo-config config/reliability-slo.json \
  --output-dir out/reliability-gate
```

Generate capacity and runbook evidence:

```bash
python3 demo/capacity_planner.py \
  --summary out/incident-replay/summary.json \
  --slo-config config/reliability-slo.json \
  --output-dir out/capacity-plan

python3 demo/runbook_generator.py \
  --summary out/incident-replay/summary.json \
  --gate out/reliability-gate/reliability-gate.json \
  --output-dir out/incident-runbooks
```

Run the advanced reliability controls:

```bash
python3 demo/incident_replay.py \
  --no-send \
  --output-dir out/incident-replay \
  --payload-dir out/incident-replay-payloads

python3 demo/advanced_reliability.py \
  --summary out/incident-replay/summary.json \
  --payload-dir out/incident-replay-payloads \
  --slo-config config/reliability-slo.json \
  --advanced-config config/advanced-reliability.json \
  --output-dir out/advanced-reliability
```

Run the detailed reliability controls:

```bash
python3 demo/detailed_reliability.py \
  --summary out/incident-replay/summary.json \
  --payload-dir out/incident-replay-payloads \
  --detailed-config config/detailed-reliability.json \
  --output-dir out/detailed-reliability
```

When the Docker daemon is available, the local demo starts an OpenTelemetry
Collector container, sends the replayed traces, prints the collector debug
output, and then cleans up the container. If Docker is not running, it falls
back to a tiny Python OTLP debug receiver so the trace flow is still runnable
without Docker Compose, `kind`, or a cloud account.

## Optional Jaeger UI

For a local trace UI:

```bash
docker compose up -d
python3 demo/incident_replay.py
open http://localhost:16686
```

Search for `toy-ai-inference-api` in Jaeger, then compare the baseline,
cache-miss, dependency-timeout, rollout-regression, and collector-pressure
traces.

## Evidence

The repository includes committed sample evidence generated by the same replay
script:

![Incident replay dashboard](docs/evidence/incident-dashboard.svg)

- [Sample incident report](docs/evidence/sample-incident-report.md)
- [Sample summary JSON](docs/evidence/sample-summary.json)
- [Reliability gate report](docs/evidence/reliability-gate.md)
- [Reliability gate JSON](docs/evidence/reliability-gate.json)
- [Capacity plan](docs/evidence/capacity-plan.md)
- [Incident runbooks](docs/evidence/incident-runbooks.md)
- [Burn rate analysis](docs/evidence/burn-rate-analysis.md)
- [Rollout guard](docs/evidence/rollout-guard.md)
- [Trace quality audit](docs/evidence/trace-quality-audit.md)
- [Collector resilience model](docs/evidence/collector-resilience.md)
- [Incident correlation](docs/evidence/incident-correlation.md)
- [Complex problem coverage](docs/evidence/complex-problems.md)
- [Critical path attribution](docs/evidence/critical-path-attribution.md)
- [Evidence coverage](docs/evidence/evidence-coverage.md)
- [HPA lag analysis](docs/evidence/hpa-lag-analysis.md)
- [Tenant blast radius](docs/evidence/tenant-blast-radius.md)
- [Token cost guard](docs/evidence/token-cost-guard.md)
- [Detailed problem coverage](docs/evidence/detailed-problems.md)
- [Deployment policy decision](docs/evidence/deployment-policy.md)
- [Policy regression suite](docs/evidence/policy-regression-suite.md)
- [Release readiness report](docs/evidence/release-readiness.md)
- [Evidence index](docs/evidence/README.md)

Regenerate the evidence:

```bash
./scripts/generate-evidence.sh
```

## Kind / GKE-Style Smoke

For a stronger local Kubernetes proof, run:

```bash
CREATE_KIND_CLUSTER=1 ./scripts/kind-smoke.sh
```

This applies the GKE-shaped manifests to kind, waits for the collector and
sample inference workload, port-forwards OTLP/HTTP, replays incidents through
the in-cluster collector, and evaluates the same reliability gate.

See [docs/kind-e2e.md](docs/kind-e2e.md).

## Kubernetes / GKE Recipe

The Kubernetes manifests live under [k8s/gke](k8s/gke):

- [namespace.yaml](k8s/gke/namespace.yaml): separates the telemetry control
  plane from the sample workload namespace.
- [collector.yaml](k8s/gke/collector.yaml): collector Deployment, Service,
  RBAC, ConfigMap, and PVC-backed queue storage.
- [instrumentation.yaml](k8s/gke/instrumentation.yaml): cross-namespace
  Python auto-instrumentation reference.
- [sample-app.yaml](k8s/gke/sample-app.yaml): small workload annotated to use
  instrumentation from the telemetry namespace.

These manifests are intentionally small and reviewable. For real production
use, replace the placeholder upstream OTLP endpoint in `collector.yaml` with a
Cloud Trace, Managed Service for Prometheus, or organization-managed collector
gateway exporter.

## Production Checklist

Before adapting this to a real GKE cluster:

1. Confirm which namespace owns the `Instrumentation` resource.
2. Use explicit `namespace/name` instrumentation annotation values across
   namespaces.
3. Mount persistent storage for collector queues before relying on telemetry
   during rollouts.
4. Keep collector RBAC read-only and scoped to required Kubernetes metadata.
5. Decide which exporter is authoritative: debug/local, Google Cloud, or an
   internal telemetry gateway.
6. For private GKE clusters, verify webhook/firewall access for any operators
   or admission webhooks.
7. Treat telemetry as production evidence: validate it during staged rollout,
   not after an incident.

## Case Study

See [docs/case-study.md](docs/case-study.md).

## Industry Map

See [docs/industry-map.md](docs/industry-map.md) for five reference projects,
ten baseline industry problems, five advanced production problems, and the
five more detailed production problems this repo adds on top of the first lab
version.

## Architecture

See [docs/architecture/incident-replay.md](docs/architecture/incident-replay.md).

## Resume Wording

Current wording before upstream merges:

> Built a runnable GKE AI inference reliability lab and opened related Google
> Cloud OSS PRs for OpenTelemetry Operator recipes covering incident replay,
> configurable SLO gates, burn-rate analysis, rollout rollback guards, trace
> quality audits, collector resilience modeling, generated incident runbooks,
> critical-path attribution, HPA lag analysis, tenant blast-radius checks,
> token/GPU guardrails, cross-namespace instrumentation, persistent telemetry
> queues, and Kubernetes metadata.

After an upstream PR merges, update this to:

> Built a runnable GKE AI inference reliability lab for inference services,
> with OpenTelemetry-based traces, Kubernetes metadata enrichment, durable
> collector queues, incident replay scenarios, configurable SLO gates,
> capacity/readiness evidence, burn-rate and canary decision controls, trace
> quality audits, critical-path attribution, HPA lag analysis, tenant blast
> radius checks, token/GPU guardrails, policy-as-code deployment gates,
> generated runbooks, and related Google Cloud OSS recipe contributions.

## License

Apache-2.0; see [LICENSE](LICENSE).
