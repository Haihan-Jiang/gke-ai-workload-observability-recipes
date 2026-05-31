# Case Study: GKE AI Workload Observability Recipes

## Problem

AI services usually become production problems before they become elegant
architecture problems. A team needs to know whether latency comes from the
model path, a cache, a node, an overloaded dependency, a rollout, or a missing
telemetry path. Without trace context, Kubernetes metadata, and durable
collector delivery, debugging becomes guesswork.

This project turns that operational need into a small runnable reference.

## Design

The project has two layers:

1. A local OTLP demo that proves the trace path without requiring a cloud
   account.
2. Kubernetes/GKE manifests that show the production shape: collector service,
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

## Validation

Current local validation:

```bash
./scripts/validate.sh
```

Runnable local trace demo:

```bash
./scripts/run-local-demo.sh
```

## Upstream Connection

This project is connected to related Google Cloud OSS work in
[GoogleCloudPlatform/opentelemetry-operator-sample](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample).
Those PRs are listed in [google-oss-upstream.md](google-oss-upstream.md).

Pending PRs are described as pending review until they are merged. After a PR
merges, the README can be updated with the exact upstream proof.

## Resume Narrative

Before upstream merge:

> Built a runnable GKE AI workload observability reference project and opened
> related Google Cloud OSS PRs for OpenTelemetry Operator recipes.

After upstream merge:

> Built a runnable GKE AI workload observability reference project and
> contributed related recipes to Google Cloud OSS.

