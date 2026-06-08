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
It also includes supply-chain, Kubernetes hardening, and admission-policy
evidence so reviewers can see how deployment drift would be blocked before a
bad manifest reaches a cluster.
Release waiver governance is included so manual exceptions stay bounded,
approved, time-limited, and linked back to rollback and RCA evidence.
Disaster recovery drill evidence verifies that critical release artifacts can
be restored with matching checksums inside the recovery objective.
Observability drift audit evidence checks that alerting rules, Grafana
dashboards, OpenSLO contracts, and runbooks continue to describe the same
scenario set and response contract.
Incident response drill evidence checks that alert routes, runbook owners,
acknowledgement SLAs, escalation, rollback drills, and post-incident reviews
form an executable on-call path.
Dependency contract evidence checks that vector cache, feature store, model
runtime, and telemetry exporter failures have owners, timeout/retry/fallback
controls, alert routes, and release actions.
Synthetic probe evidence checks that preflight probes cover healthy baseline,
dependency failure, canary regression, and telemetry-delivery paths before
release promotion.
Load-shedding policy evidence checks that overload and incident paths protect
high-priority tenants, shed best-effort traffic first, use fallback behavior,
and link cost, capacity, runbook, probe, and release-action evidence.
Regional failover evidence checks that zone or region failure decisions are
connected to DR RTO/RPO, standby capacity, synthetic probes, load shedding,
rollback, runbook ownership, and Kubernetes control-plane hardening.

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
- A supply-chain audit that verifies Kubernetes image references are
  digest-pinned, non-floating, explicitly pulled, and owner-labeled.
- Kubernetes manifest hardening evidence for probes, resource budgets,
  restricted collector security context, disruption protection, and
  NetworkPolicy boundaries.
- A Kubernetes admission policy pack and simulated admission audit that allow
  the committed deployments while denying drift fixtures for unpinned images,
  privileged containers, missing probes/resources, bad registries, and missing
  OpenTelemetry instrumentation.
- Generated SLO alerting rules that connect latency, dependency, rollout,
  cache, and telemetry-loss signals to severities, runbooks, and dashboard
  hints.
- A generated Grafana dashboard and ConfigMap that cover every replayed SLO
  scenario with Prometheus queries and runbook links.
- An OpenSLO-style SLO contract that ties the service objective to Prometheus
  SLI queries, telemetry-quality evidence, alerting, dashboard, release gate,
  and runbooks.
- An observability drift audit that compares alerting rules, dashboard
  scenario coverage, OpenSLO links, runbook coverage, and negative drift
  fixtures before the release-readiness gate passes.
- A telemetry redaction audit that proves trace payloads keep safe AI metadata
  while blocking prompt text, response bodies, secrets, and direct identifiers.
- A telemetry cost budget that estimates sampled trace ingest and retained
  storage from generated OTLP payload size and span volume.
- An error-budget ledger that maps replayed incidents to allowed bad events,
  consumed budget, release actions, and rollback/manual-review decisions.
- A rollback drill that turns the release gate, error budget, and runbooks into
  named-owner incident timelines with RTO/RPO checks.
- A post-incident review packet that links impact, root cause, timeline,
  corrective actions, and preventive controls back to generated evidence.
- An incident response drill that verifies page/ticket routes, on-call
  acknowledgement SLAs, escalation stages, owners, rollback evidence, and RCA
  evidence for each replayed alert scenario.
- A dependency contract audit that links critical AI inference dependencies to
  owners, timeout/retry/fallback controls, trace attributes, alerts, runbooks,
  error-budget decisions, and rollback/manual-review actions.
- A synthetic probe audit that verifies preflight probes for baseline,
  dependency, canary, and telemetry-delivery paths before release promotion.
- A load-shedding policy audit that ties capacity warnings, tenant blast
  radius, token/GPU cost review, graceful degradation, preflight probes,
  runbook ownership, and error-budget release actions into one gate.
- A regional failover audit that checks standby-region coverage, DR/RTO/RPO,
  capacity guardrails, traffic-safety linkage, rollback, and Kubernetes
  control-plane readiness for failover decisions.
- Release waiver governance that conditionally approves bounded manual-review
  exceptions while denying production-promotion overrides for budget-exhausted
  incidents.
- A disaster recovery drill that restores critical release evidence,
  Kubernetes/Grafana/OpenSLO artifacts, admission policy, and source policy
  files with SHA-256 verification inside the configured RTO/RPO.
- An evidence provenance manifest with SHA-256 checksums for generated
  evidence, Kubernetes/Grafana/OpenSLO artifacts, and source inputs.
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
- [Supply chain audit](docs/evidence/supply-chain-audit.md)
- [Kubernetes manifest hardening audit](docs/evidence/k8s-hardening-audit.md)
- [Admission policy audit](docs/evidence/admission-policy-audit.md)
- [SLO alerting rules](docs/evidence/alerting-rules.md)
- [Grafana dashboard evidence](docs/evidence/grafana-dashboard.md)
- [OpenSLO contract evidence](docs/evidence/openslo-contract.md)
- [Observability drift audit](docs/evidence/observability-drift-audit.md)
- [Telemetry redaction audit](docs/evidence/telemetry-redaction-audit.md)
- [Telemetry cost budget](docs/evidence/telemetry-cost-budget.md)
- [Error budget ledger](docs/evidence/error-budget-ledger.md)
- [Rollback drill](docs/evidence/rollback-drill.md)
- [Post-incident review](docs/evidence/post-incident-review.md)
- [Incident response drill](docs/evidence/incident-response-drill.md)
- [Dependency contract audit](docs/evidence/dependency-contract-audit.md)
- [Synthetic probe audit](docs/evidence/synthetic-probe-audit.md)
- [Load shedding policy audit](docs/evidence/load-shedding-policy-audit.md)
- [Regional failover audit](docs/evidence/regional-failover-audit.md)
- [Release waiver governance](docs/evidence/release-waiver-governance.md)
- [Disaster recovery drill](docs/evidence/disaster-recovery-drill.md)
- [Evidence provenance](docs/evidence/evidence-provenance.md)
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
- [alerting-rules.yaml](k8s/gke/alerting-rules.yaml): optional
  PrometheusRule alerts for the replayed SLO scenarios when Prometheus
  Operator CRDs are installed.
- [grafana-dashboard-configmap.yaml](k8s/gke/grafana-dashboard-configmap.yaml):
  Grafana dashboard-as-code ConfigMap for clusters that import dashboards from
  labeled ConfigMaps.
- [gke-ai-inference-slo.yaml](slos/openslo/gke-ai-inference-slo.yaml):
  OpenSLO-style service objective contract for platform review.
- [gke-ai-inference-admission-policy.yaml](policies/admission/gke-ai-inference-admission-policy.yaml):
  native Kubernetes ValidatingAdmissionPolicy and binding for deployment
  guardrails.

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
4. Pin workload and collector images by digest before using the manifests as
   production deployment evidence.
5. Keep collector RBAC read-only and scoped to required Kubernetes metadata.
6. Keep collector health probes, resource budgets, security context,
   disruption budget, and NetworkPolicy aligned with the manifest audit.
7. Keep the admission policy audit aligned with digest pinning, restricted
   security context, probes, resources, registry allowlists, and
   instrumentation requirements.
8. Keep alert labels, runbook links, and dashboard hints aligned with the SLO
   alerting evidence before routing pages.
9. Keep Grafana dashboard panels aligned with SLO scenarios and runbook links.
10. Keep the OpenSLO contract aligned with Prometheus SLI queries, runbooks,
   alerting, dashboard, and release-readiness evidence.
11. Run the observability drift audit after changing alert rules, Grafana
   panels, OpenSLO links, runbooks, or scenario names.
12. Audit trace payloads for prompt, response, secret, and direct-identifier
   leakage before using inference telemetry as production evidence.
13. Keep trace sampling and retention budgets explicit before routing all
    inference telemetry into a paid backend.
14. Keep the error-budget ledger aligned with the SLO target before treating a
   canary or dependency incident as release-safe.
15. Run the rollback drill after changing release gates, runbooks, or SLO
    budget policy so owner and RTO assumptions stay explicit.
16. Keep post-incident reviews tied to replayed evidence, rollback timelines,
    and corrective actions instead of treating them as narrative-only notes.
17. Run the incident response drill after changing alert severities, runbooks,
    escalation policy, rollback timelines, or RCA requirements.
18. Keep dependency contracts aligned with timeout/retry/fallback policy,
    trace attributes, runbook owners, alert severities, and release actions.
19. Keep synthetic probes aligned with baseline health, dependency failure,
    canary version, telemetry delivery, alert routing, rollback, and
    error-budget actions.
20. Keep load-shedding policy aligned with capacity warnings, tenant tiers,
    fallback behavior, token/GPU cost review, preflight probes, runbook owners,
    and release actions.
21. Keep regional failover policy aligned with DR RTO/RPO, standby capacity,
    synthetic probes, load shedding, rollback paths, runbook owners, and
    Kubernetes control-plane hardening.
22. Keep release waivers bounded by owner, approver, expiry, rollback drill,
    post-incident review, linked evidence, and acknowledged error-budget
    impact.
23. Verify disaster recovery after changing evidence, generated manifests,
    dashboards, SLO contracts, admission policies, or release control files.
24. Regenerate evidence provenance after changing evidence scripts, generated
    manifests, or policy files so reviewers can detect stale artifacts.
25. Decide which exporter is authoritative: debug/local, Google Cloud, or an
   internal telemetry gateway.
26. For private GKE clusters, verify webhook/firewall access for any operators
   or admission webhooks.
27. Treat telemetry as production evidence: validate it during staged rollout,
   not after an incident.

## Case Study

See [docs/case-study.md](docs/case-study.md).

## Industry Map

See [docs/industry-map.md](docs/industry-map.md) for five reference projects,
ten baseline industry problems, five advanced production problems, five more
detailed production problems, and the evidence-governance problems this repo
adds on top of the first lab version.

## Architecture

See [docs/architecture/incident-replay.md](docs/architecture/incident-replay.md).

## Resume Wording

Current wording before upstream merges:

> Built a runnable GKE AI inference reliability lab and opened related Google
> Cloud OSS PRs for OpenTelemetry Operator recipes covering incident replay,
> configurable SLO gates, burn-rate analysis, rollout rollback guards, trace
> quality audits, collector resilience modeling, generated incident runbooks,
> critical-path attribution, HPA lag analysis, tenant blast-radius checks,
> token/GPU guardrails, release waiver governance, disaster recovery drills,
> observability drift auditing, incident response drill validation,
> dependency contract auditing, synthetic probe auditing, load-shedding policy
> auditing, regional failover auditing, telemetry redaction and cost audits,
> supply-chain image checks,
> cross-namespace instrumentation, persistent telemetry queues, and Kubernetes
> metadata.

After an upstream PR merges, update this to:

> Built a runnable GKE AI inference reliability lab for inference services,
> with OpenTelemetry-based traces, Kubernetes metadata enrichment, durable
> collector queues, incident replay scenarios, configurable SLO gates,
> capacity/readiness evidence, burn-rate and canary decision controls, trace
> quality audits, critical-path attribution, HPA lag analysis, tenant blast
> radius checks, token/GPU guardrails, policy-as-code deployment gates,
> admission-policy simulation, release waiver governance, disaster recovery
> drills, observability drift auditing, incident response drill validation,
> dependency contract auditing, synthetic probe auditing, load-shedding policy
> auditing, regional failover auditing, telemetry redaction and cost audits,
> supply-chain image checks,
> generated runbooks, and related Google Cloud OSS recipe contributions.

## License

Apache-2.0; see [LICENSE](LICENSE).
