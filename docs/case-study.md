# Case Study: GKE AI Inference Reliability Lab

## Problem

AI services usually become production problems before they become elegant
architecture problems. A team needs to know whether latency comes from the
model path, a cache, a node, an overloaded dependency, a rollout, or a missing
telemetry path. Without trace context, Kubernetes metadata, and durable
collector delivery, debugging becomes guesswork.

This project turns that operational need into a runnable inference reliability
lab.

## Design

The project has four layers:

1. A local OTLP demo that proves the trace path without requiring a cloud
   account.
2. Incident replay scenarios that show how latency, dependency errors, and
   rollout regressions appear in traces.
3. Reliability gates that verify healthy baseline behavior and classify the
   expected incident signals.
4. Kubernetes/GKE manifests that show the production shape: collector service,
   resource enrichment, Kubernetes metadata, read-only RBAC, persistent queue
   storage, and cross-namespace instrumentation references.

## Why It Is Useful

The repo is intentionally narrow. It does not try to become a full observability
platform. It gives SRE/platform engineers a reviewed starting point for the
parts that are easy to get wrong:

- instrumentation references across namespaces;
- collector queues that survive rollout churn;
- Kubernetes metadata enrichment;
- a clear separation between sample workload and telemetry control plane;
- a checklist that can be reviewed during production readiness.
- incident reports that connect telemetry attributes to SRE triage decisions.

## Incident Replay

The v2 lab replays four scenarios:

| Scenario | Failure mode | Primary signal |
| --- | --- | --- |
| `baseline` | healthy inference path | normal latency and cache hits |
| `cache_miss_storm` | vector cache misses | `cache.result=miss`, high p95 latency |
| `dependency_timeout` | feature-store timeout | dependency child span dominates trace time |
| `rollout_regression` | bad service version | `service.version=v2`, elevated latency and errors |

The replay writes `out/incident-replay/report.md` and
`out/incident-replay/summary.json`. The reliability gate then writes
`out/reliability-gate/reliability-gate.md` and
`out/reliability-gate/reliability-gate.json`. That makes the repo useful as a
portfolio artifact: a reviewer can run it, inspect the generated report, and
see how the observability design supports incident debugging.

The repository also commits a sample output under [evidence](evidence/README.md)
so a reviewer can inspect the result before running anything locally:

- [sample incident report](evidence/sample-incident-report.md)
- [sample summary JSON](evidence/sample-summary.json)
- [reliability gate report](evidence/reliability-gate.md)
- [incident replay dashboard](evidence/incident-dashboard.svg)

## Validation

Current local validation:

```bash
./scripts/validate.sh
```

Runnable local trace demo:

```bash
./scripts/run-local-demo.sh
```

Generate the report without sending OTLP:

```bash
python3 demo/incident_replay.py --no-send
```

Run the reliability gate:

```bash
python3 demo/reliability_gate.py \
  --summary out/incident-replay/summary.json \
  --output-dir out/reliability-gate
```

## Upstream Connection

This project is connected to related Google Cloud OSS work in
[GoogleCloudPlatform/opentelemetry-operator-sample](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample).
Those PRs are listed in [google-oss-upstream.md](google-oss-upstream.md).

Pending PRs are described as pending review until they are merged. After a PR
merges, the README can be updated with the exact upstream proof.

## Resume Narrative

Before upstream merge:

> Built a runnable GKE AI inference reliability lab and opened related Google
> Cloud OSS PRs for OpenTelemetry Operator recipes, with local incident replay
> for AI inference latency and rollout failures.

After upstream merge:

> Built a runnable GKE AI inference reliability lab for inference services,
> with OpenTelemetry-based traces, Kubernetes metadata enrichment, durable
> collector queues, incident replay scenarios, SLO-style reliability gates, and
> related Google Cloud OSS recipe contributions.
