# Kind / GKE-Style Smoke Test

The default CI path stays zero-cost and does not require Docker, `kind`, GKE, or
a cloud account. For stronger local proof, this repo also includes an optional
Kubernetes smoke test that applies the GKE-shaped manifests to a local kind
cluster, port-forwards the collector, replays inference incidents, and evaluates
the reliability gate.

## What It Proves

- The Kubernetes manifests are applyable together.
- The collector Deployment starts with PVC-backed file storage configured.
- The sample inference workload rolls out in a separate namespace.
- OTLP/HTTP traces can flow through the in-cluster collector.
- The same SLO-style reliability gate passes after the Kubernetes replay.

## Run

Create a disposable kind cluster and run the smoke test:

```bash
CREATE_KIND_CLUSTER=1 ./scripts/kind-smoke.sh
```

Reuse an existing cluster named `gke-ai-reliability-lab`:

```bash
./scripts/kind-smoke.sh
```

Use a custom cluster name:

```bash
KIND_CLUSTER_NAME=my-lab ./scripts/kind-smoke.sh
```

## Outputs

```text
out/kind-incident-replay/report.md
out/kind-incident-replay/summary.json
out/kind-reliability-gate/reliability-gate.md
out/kind-reliability-gate/reliability-gate.json
```

## Notes

- If OpenTelemetry Operator CRDs are not installed, the script skips
  `Instrumentation` and still validates collector delivery plus workload
  rollout.
- The checked-in `k8s/gke` manifests intentionally keep the upstream exporter
  as a placeholder. Replace it with Cloud Trace, Managed Service for
  Prometheus, or an internal collector gateway before using the pattern in a
  real GKE environment.
- The local kind smoke is a stronger proof than YAML parsing, but it is not a
  claim that this repo has been production deployed.
