# Industry Map And Feature Backlog

This lab is not trying to replace a serving platform or a full observability
stack. It fills the gap between those systems: a small, runnable reliability
exercise that shows how an SRE or platform engineer can detect and explain
inference incidents before a service reaches production.

## Five Reference Projects

| Project | Why It Is Relevant | Gap This Lab Covers |
| --- | --- | --- |
| [OpenTelemetry Demo](https://opentelemetry.io/docs/demo/) | End-to-end demo for seeing OpenTelemetry in action across services. | This lab focuses the demo shape on AI inference incidents and reviewer-friendly SRE evidence. |
| [GoogleCloudPlatform/microservices-demo](https://github.com/GoogleCloudPlatform/microservices-demo) | Kubernetes-first sample app for microservices, Istio, and gRPC. | This lab keeps the same runnable-sample spirit but narrows it to inference reliability signals. |
| [KServe](https://github.com/kserve/kserve) | Kubernetes-native generative and predictive inference serving platform. | This lab does not serve real models; it validates the incident and reliability evidence around model-serving paths. |
| [vLLM Production Stack](https://github.com/vllm-project/production-stack) | Kubernetes-native stack for cluster-wide LLM serving. | This lab adds a lightweight local reliability gate that can be understood without GPUs or a paid cluster. |
| [kube-prometheus](https://github.com/prometheus-operator/kube-prometheus) | End-to-end Kubernetes monitoring manifests, dashboards, and alerting rules. | This lab complements cluster monitoring with trace-driven inference triage and runbooks. |

## Ten Concrete Industry Problems Covered By The First Feature Set

| ID | Problem | Why It Hurts In Production | Lab Coverage |
| --- | --- | --- | --- |
| P01 | No healthy control group | Teams cannot tell whether a new incident is worse than normal traffic. | `baseline` replay, reliability gate, capacity plan. |
| P02 | Cache or retrieval misses look like model latency | Teams over-scale expensive model workers when the retrieval path is the bottleneck. | `cache_miss_storm` replay and runbook. |
| P03 | Feature-store or dependency timeout | Root latency hides inside downstream child spans. | `dependency_timeout` replay and runbook. |
| P04 | Bad rollout increases p95 and errors | Aggregated dashboards hide the failing version. | `rollout_regression` replay with `service.version=v2`. |
| P05 | Collector queue pressure drops telemetry | The app can be healthy while dashboards silently lose evidence. | `collector_queue_pressure` replay and gate. |
| P06 | Cross-namespace instrumentation is misconfigured | Workloads run, but traces never appear because the annotation points to the wrong namespace. | `k8s/gke/instrumentation.yaml` and production checklist. |
| P07 | Kubernetes metadata is missing | Traces cannot be mapped back to namespace, deployment, pod, or rollout. | Collector resource enrichment and replay resource attributes. |
| P08 | Autoscaling lacks a capacity sanity check | Teams add replicas without knowing whether the scenario is scalable or a dependency failure. | `demo/capacity_planner.py`. |
| P09 | SLO thresholds live only in prose | Reviewers cannot repeat the gate or change the production profile. | `config/reliability-slo.json` and `demo/reliability_gate.py`. |
| P10 | Incident response lacks reusable runbooks | A dashboard exists, but the first responder still has to invent the response. | `demo/runbook_generator.py`. |

## Five Feature Contributions In This Repository

1. **Configurable reliability SLOs**
   - Artifact: [config/reliability-slo.json](../config/reliability-slo.json)
   - Code: [demo/reliability_gate.py](../demo/reliability_gate.py)
   - Covers: P01, P09

2. **Telemetry-delivery incident replay**
   - Artifact: `collector_queue_pressure` scenario in [demo/incident_replay.py](../demo/incident_replay.py)
   - Evidence: [sample summary JSON](evidence/sample-summary.json)
   - Covers: P05, P07

3. **Capacity planning evidence**
   - Code: [demo/capacity_planner.py](../demo/capacity_planner.py)
   - Evidence: [capacity plan](evidence/capacity-plan.md)
   - Covers: P02, P03, P08

4. **Generated incident runbooks**
   - Code: [demo/runbook_generator.py](../demo/runbook_generator.py)
   - Evidence: [incident runbooks](evidence/incident-runbooks.md)
   - Covers: P02, P03, P04, P05, P10

5. **Release readiness aggregation**
   - Code: [demo/release_readiness.py](../demo/release_readiness.py)
   - Evidence: [release readiness report](evidence/release-readiness.md)
   - Covers: P01, P08, P09, P10

## Five More Complex Problems Covered By The Advanced Feature Set

| ID | Problem | Why It Is Harder | Lab Coverage |
| --- | --- | --- | --- |
| C01 | Multi-window SLO burn rate | A short incident can burn the error budget even when daily averages look fine. | [burn-rate analysis](evidence/burn-rate-analysis.md) |
| C02 | Automated canary rollback decision | A new version must be compared against baseline on latency, errors, cache, and telemetry before rollout expands. | [rollout guard](evidence/rollout-guard.md) |
| C03 | Trace completeness and cardinality audit | Traces can exist but be unusable if key attributes are missing or high-cardinality labels explode storage. | [trace quality audit](evidence/trace-quality-audit.md) |
| C04 | Collector outage and queue resilience | Persistent queue sizing must survive exporter outages without losing the traces needed for incident review. | [collector resilience](evidence/collector-resilience.md) |
| C05 | Incident correlation and deduplication | One root cause can emit latency, error, rollout, and telemetry alerts that must be grouped for the responder. | [incident correlation](evidence/incident-correlation.md) |

## Advanced Feature Contributions

1. **Multi-window burn-rate analysis**
   - Code: [demo/advanced_reliability.py](../demo/advanced_reliability.py)
   - Config: [config/advanced-reliability.json](../config/advanced-reliability.json)
   - Evidence: [burn-rate analysis](evidence/burn-rate-analysis.md)

2. **Canary rollout guard**
   - Code: [demo/advanced_reliability.py](../demo/advanced_reliability.py)
   - Evidence: [rollout guard](evidence/rollout-guard.md)

3. **OTLP trace quality and cardinality audit**
   - Code: [demo/advanced_reliability.py](../demo/advanced_reliability.py)
   - Input: per-scenario OTLP payloads emitted by [demo/incident_replay.py](../demo/incident_replay.py)
   - Evidence: [trace quality audit](evidence/trace-quality-audit.md)

4. **Collector outage resilience model**
   - Code: [demo/advanced_reliability.py](../demo/advanced_reliability.py)
   - Evidence: [collector resilience](evidence/collector-resilience.md)

5. **Incident correlation and deduplication**
   - Code: [demo/advanced_reliability.py](../demo/advanced_reliability.py)
   - Evidence: [incident correlation](evidence/incident-correlation.md)

## Five More Detailed Problems Covered By The Third Feature Set

| ID | Problem | Why It Is More Detailed | Lab Coverage |
| --- | --- | --- | --- |
| C06 | Critical-path span attribution | It inspects child span durations instead of only scenario-level p95 latency. | [critical-path attribution](evidence/critical-path-attribution.md) |
| C07 | Tail-sampling evidence coverage | It checks whether error, high-latency, and telemetry-loss traces are preserved. | [evidence coverage](evidence/evidence-coverage.md) |
| C08 | Autoscaler lag and cold-start recovery | It separates scale-up actions from dependency/rollout problems that scaling cannot solve. | [HPA lag analysis](evidence/hpa-lag-analysis.md) |
| C09 | Tenant blast-radius detection | It checks tier-specific SLOs instead of relying on aggregate service health. | [tenant blast radius](evidence/tenant-blast-radius.md) |
| C10 | Token and GPU cost guardrail | It links prompt size, output tokens, model variant, and GPU time to rollout review. | [token cost guard](evidence/token-cost-guard.md) |

## Detailed Feature Contributions

1. **Critical-path span attribution**
   - Code: [demo/detailed_reliability.py](../demo/detailed_reliability.py)
   - Input: OTLP child spans emitted by [demo/incident_replay.py](../demo/incident_replay.py)
   - Evidence: [critical-path attribution](evidence/critical-path-attribution.md)

2. **Tail-sampling evidence coverage**
   - Code: [demo/detailed_reliability.py](../demo/detailed_reliability.py)
   - Evidence: [evidence coverage](evidence/evidence-coverage.md)

3. **HPA lag and cold-start analysis**
   - Code: [demo/detailed_reliability.py](../demo/detailed_reliability.py)
   - Config: [config/detailed-reliability.json](../config/detailed-reliability.json)
   - Evidence: [HPA lag analysis](evidence/hpa-lag-analysis.md)

4. **Tenant blast-radius detection**
   - Code: [demo/detailed_reliability.py](../demo/detailed_reliability.py)
   - Evidence: [tenant blast radius](evidence/tenant-blast-radius.md)

5. **Token and GPU cost guardrail**
   - Code: [demo/detailed_reliability.py](../demo/detailed_reliability.py)
   - Evidence: [token cost guard](evidence/token-cost-guard.md)

## Security, Policy, Privacy, And Evidence Governance Added By The Fourth Feature Set

| ID | Problem | Why It Matters In Production | Lab Coverage |
| --- | --- | --- | --- |
| C11 | Inference traces can leak prompts, responses, secrets, or direct identifiers | AI observability needs enough metadata for SRE triage without exporting customer text or credentials into tracing backends. | [Telemetry redaction audit](evidence/telemetry-redaction-audit.md) |
| C12 | Trace volume can overwhelm observability budgets | AI inference traces often include multiple child spans and expensive high-signal incidents; teams need sampling and retention budgets before exporting everything. | [Telemetry cost budget](evidence/telemetry-cost-budget.md) |
| C13 | Sample manifests can hide floating image risk | Reviewers need to see that even demo deployment recipes avoid `latest` tags and pin runtime artifacts by digest before being adapted to production. | [Supply chain audit](evidence/supply-chain-audit.md) |
| C14 | Manifest drift can bypass review after the first audit | Platform teams need admission controls that block unsafe deployment changes at create/update time instead of discovering the drift after rollout. | [Admission policy audit](evidence/admission-policy-audit.md) |
| C15 | Manual release exceptions can bypass reliability gates | SRE teams need bounded waiver requests with owner, approver, expiry, rollback, RCA, evidence, and budget acknowledgement instead of informal approvals. | [Release waiver governance](evidence/release-waiver-governance.md) |
| C16 | Release evidence can be lost or restored incorrectly | Incident response and release review need recoverable evidence and control-plane artifacts with checksum verification inside RTO/RPO targets. | [Disaster recovery drill](evidence/disaster-recovery-drill.md) |
| C17 | Observability artifacts can drift while each one still passes alone | Alert rules, dashboards, OpenSLO contracts, and runbooks need to describe the same scenario set, severities, links, and first-response contract. | [Observability drift audit](evidence/observability-drift-audit.md) |
| C18 | Alerts can fire without an executable on-call response path | Production teams need page/ticket routing, acknowledgement SLAs, escalation, rollback evidence, and RCA evidence tied to each alert scenario. | [Incident response drill](evidence/incident-response-drill.md) |
| C19 | Critical AI dependencies can fail without an explicit operating contract | Vector cache, feature store, model runtime, and telemetry exporter paths need owners, timeout/retry/fallback controls, alert routing, trace attributes, and release actions. | [Dependency contract audit](evidence/dependency-contract-audit.md) |
| C20 | Rollouts can pass static checks without a black-box preflight signal | Teams need synthetic probes that exercise baseline health, dependency failures, canary regressions, and telemetry delivery before real users discover the issue. | [Synthetic probe audit](evidence/synthetic-probe-audit.md) |
| C21 | Model releases can pass deployment checks while the model itself is unsafe | AI inference releases need pinned model artifacts, eval thresholds, schema compatibility, canary evidence, cost deltas, rollback targets, and trace labels before promotion. | [Model release safety audit](evidence/model-release-safety-audit.md) |
| C22 | Shadow traffic can accidentally affect users or leak prompts | Candidate inference paths need no-user-serving guarantees, disabled writes/side effects, privacy-safe telemetry, rollout comparison, cost checks, probes, and rollback linkage. | [Shadow traffic replay audit](evidence/shadow-traffic-replay-audit.md) |
| C23 | Overload mitigation can punish the wrong traffic | AI inference systems need explicit load-shedding and fallback policies that protect higher-priority tenants, shed best-effort traffic first, and tie cost/capacity pressure back to release action. | [Load shedding policy audit](evidence/load-shedding-policy-audit.md) |
| C24 | Regional failover can restore artifacts but still route unsafe traffic | Failover decisions need DR RTO/RPO, standby capacity, probes, load shedding, rollback, runbook ownership, and Kubernetes controls to agree before traffic moves. | [Regional failover audit](evidence/regional-failover-audit.md) |
| C25 | Accelerator quota overuse can starve high-priority inference tenants | GPU/accelerator quota needs tenant reservations, cost review, load shedding, shadow candidate checks, and release blocking to agree before traffic expands. | [Accelerator quota fairness audit](evidence/accelerator-quota-fairness-audit.md) |
| C26 | GKE samples can accidentally normalize static keys or broad identity scope | Production recipes need Workload Identity binding, explicit service account token boundaries, least-privilege RBAC, static credential rejection, and TLS exporter transport. | [Workload Identity audit](evidence/workload-identity-audit.md) |
| C27 | Namespaces can allow runaway AI workloads despite per-pod resource settings | GKE recipes need ResourceQuota and LimitRange controls that cover current workloads with headroom, default missing requests, and keep object counts bounded. | [Namespace resource audit](evidence/namespace-resource-audit.md) |
| C28 | Workloads can pass static checks but still fail node or zone maintenance | Production GKE recipes need explicit replica floors, PDB coverage, topology spread constraints, selector alignment, and owner labels before rollout evidence is trusted. | [Availability topology audit](evidence/availability-topology-audit.md) |
| C29 | HPA lag can be analyzed offline while manifests still lack a real scaling policy | Production GKE recipes need an actual HPA with bounded replicas, resource metrics, matching requests, and scale behavior before autoscaling claims are trusted. | [Autoscaling policy audit](evidence/autoscaling-policy-audit.md) |
| C30 | Workload traffic can drift outside the intended telemetry path | Production GKE recipes need egress and ingress NetworkPolicy boundaries so sample workloads can reach telemetry and DNS without normalizing unrestricted namespace traffic. | [Network boundary audit](evidence/network-boundary-audit.md) |
| C31 | Sampling can hide the traces needed for AI incident debugging | Production OpenTelemetry collectors need tail-sampling rules that retain errors, dependency timeouts, rollout regressions, and collector-pressure traces while keeping healthy baseline volume bounded. | [Telemetry sampling audit](evidence/telemetry-sampling-audit.md) |
| C32 | Collector failures can hide the telemetry pipeline's own outage | Production observability needs collector internal metrics scraped and exported through the same durable metrics path so queue, exporter, and receiver failures are visible before telemetry disappears. | [Collector self-observability audit](evidence/collector-self-observability-audit.md) |
| C33 | AI and telemetry workloads can land on the wrong node pools | GKE recipes need non-preempting PriorityClasses, soft node-pool affinity, and bounded tolerations so scheduling intent is explicit without making local smoke tests unschedulable. | [Scheduling placement audit](evidence/scheduling-placement-audit.md) |

## Fourth Feature Contribution

1. **Telemetry redaction audit**
   - Code: [demo/telemetry_redaction_audit.py](../demo/telemetry_redaction_audit.py)
   - Config: [config/telemetry-redaction-policy.json](../config/telemetry-redaction-policy.json)
   - Input: per-scenario OTLP payloads emitted by [demo/incident_replay.py](../demo/incident_replay.py)
   - Evidence: [telemetry redaction audit](evidence/telemetry-redaction-audit.md)

2. **Telemetry cost budget**
   - Code: [demo/telemetry_cost_budget.py](../demo/telemetry_cost_budget.py)
   - Config: [config/telemetry-cost-policy.json](../config/telemetry-cost-policy.json)
   - Input: per-scenario OTLP payload sizes and span counts emitted by [demo/incident_replay.py](../demo/incident_replay.py)
   - Evidence: [telemetry cost budget](evidence/telemetry-cost-budget.md)

3. **Supply-chain image audit**
   - Code: [demo/supply_chain_audit.py](../demo/supply_chain_audit.py)
   - Config: [config/supply-chain-policy.json](../config/supply-chain-policy.json)
   - Input: GKE-shaped collector and sample workload manifests under [k8s/gke](../k8s/gke)
   - Evidence: [supply chain audit](evidence/supply-chain-audit.md)

4. **Kubernetes admission policy audit**
   - Code: [demo/admission_policy_audit.py](../demo/admission_policy_audit.py)
   - Config: [config/admission-policy.json](../config/admission-policy.json)
   - Policy: [gke-ai-inference-admission-policy.yaml](../policies/admission/gke-ai-inference-admission-policy.yaml)
   - Evidence: [admission policy audit](evidence/admission-policy-audit.md)

5. **Release waiver governance**
   - Code: [demo/release_waiver_governance.py](../demo/release_waiver_governance.py)
   - Policy: [config/release-waiver-policy.json](../config/release-waiver-policy.json)
   - Register: [config/release-waivers.json](../config/release-waivers.json)
   - Evidence: [release waiver governance](evidence/release-waiver-governance.md)

6. **Disaster recovery drill**
   - Code: [demo/disaster_recovery_drill.py](../demo/disaster_recovery_drill.py)
   - Policy: [config/disaster-recovery-policy.json](../config/disaster-recovery-policy.json)
   - Evidence: [disaster recovery drill](evidence/disaster-recovery-drill.md)

7. **Observability drift audit**
   - Code: [demo/observability_drift_audit.py](../demo/observability_drift_audit.py)
   - Policy: [config/observability-drift-policy.json](../config/observability-drift-policy.json)
   - Inputs: [alerting rules](evidence/alerting-rules.md), [Grafana dashboard evidence](evidence/grafana-dashboard.md), [OpenSLO contract evidence](evidence/openslo-contract.md), and [incident runbooks](evidence/incident-runbooks.md)
   - Evidence: [observability drift audit](evidence/observability-drift-audit.md)

8. **Incident response drill**
   - Code: [demo/incident_response_drill.py](../demo/incident_response_drill.py)
   - Policy: [config/incident-response-policy.json](../config/incident-response-policy.json)
   - Inputs: [alerting rules](evidence/alerting-rules.md), [incident runbooks](evidence/incident-runbooks.md), [incident correlation](evidence/incident-correlation.md), [rollback drill](evidence/rollback-drill.md), and [post-incident review](evidence/post-incident-review.md)
   - Evidence: [incident response drill](evidence/incident-response-drill.md)

9. **Dependency contract audit**
   - Code: [demo/dependency_contract_audit.py](../demo/dependency_contract_audit.py)
   - Policy: [config/dependency-contract-policy.json](../config/dependency-contract-policy.json)
   - Inputs: [critical-path attribution](evidence/critical-path-attribution.md), [alerting rules](evidence/alerting-rules.md), [incident runbooks](evidence/incident-runbooks.md), [error-budget ledger](evidence/error-budget-ledger.md), and [rollback drill](evidence/rollback-drill.md)
   - Evidence: [dependency contract audit](evidence/dependency-contract-audit.md)

10. **Synthetic probe audit**
    - Code: [demo/synthetic_probe_audit.py](../demo/synthetic_probe_audit.py)
    - Policy: [config/synthetic-probe-policy.json](../config/synthetic-probe-policy.json)
    - Inputs: [sample summary](evidence/sample-summary.json), [alerting rules](evidence/alerting-rules.md), [dependency contract audit](evidence/dependency-contract-audit.md), [incident response drill](evidence/incident-response-drill.md), [rollback drill](evidence/rollback-drill.md), and [error-budget ledger](evidence/error-budget-ledger.md)
    - Evidence: [synthetic probe audit](evidence/synthetic-probe-audit.md)

11. **Model release safety audit**
    - Code: [demo/model_release_safety_audit.py](../demo/model_release_safety_audit.py)
    - Policy: [config/model-release-policy.json](../config/model-release-policy.json)
    - Inputs: [rollout guard](evidence/rollout-guard.md), [trace quality audit](evidence/trace-quality-audit.md), [token cost guard](evidence/token-cost-guard.md), [error-budget ledger](evidence/error-budget-ledger.md), [rollback drill](evidence/rollback-drill.md), and [synthetic probe audit](evidence/synthetic-probe-audit.md)
    - Evidence: [model release safety audit](evidence/model-release-safety-audit.md)

12. **Shadow traffic replay audit**
    - Code: [demo/shadow_traffic_replay_audit.py](../demo/shadow_traffic_replay_audit.py)
    - Policy: [config/shadow-traffic-policy.json](../config/shadow-traffic-policy.json)
    - Inputs: [sample summary](evidence/sample-summary.json), [telemetry redaction audit](evidence/telemetry-redaction-audit.md), [rollout guard](evidence/rollout-guard.md), [token cost guard](evidence/token-cost-guard.md), [synthetic probe audit](evidence/synthetic-probe-audit.md), and [model release safety audit](evidence/model-release-safety-audit.md)
    - Evidence: [shadow traffic replay audit](evidence/shadow-traffic-replay-audit.md)

13. **Load shedding policy audit**
    - Code: [demo/load_shedding_policy_audit.py](../demo/load_shedding_policy_audit.py)
    - Policy: [config/load-shedding-policy.json](../config/load-shedding-policy.json)
    - Inputs: [capacity plan](evidence/capacity-plan.md), [tenant blast radius](evidence/tenant-blast-radius.md), [token cost guard](evidence/token-cost-guard.md), [error-budget ledger](evidence/error-budget-ledger.md), [synthetic probe audit](evidence/synthetic-probe-audit.md), and [incident runbooks](evidence/incident-runbooks.md)
    - Evidence: [load shedding policy audit](evidence/load-shedding-policy-audit.md)

14. **Regional failover audit**
    - Code: [demo/regional_failover_audit.py](../demo/regional_failover_audit.py)
    - Policy: [config/regional-failover-policy.json](../config/regional-failover-policy.json)
    - Inputs: [capacity plan](evidence/capacity-plan.md), [error-budget ledger](evidence/error-budget-ledger.md), [rollback drill](evidence/rollback-drill.md), [disaster recovery drill](evidence/disaster-recovery-drill.md), [synthetic probe audit](evidence/synthetic-probe-audit.md), [load shedding policy audit](evidence/load-shedding-policy-audit.md), [incident runbooks](evidence/incident-runbooks.md), and [Kubernetes manifest hardening audit](evidence/k8s-hardening-audit.md)
    - Evidence: [regional failover audit](evidence/regional-failover-audit.md)

15. **Accelerator quota fairness audit**
    - Code: [demo/accelerator_quota_fairness_audit.py](../demo/accelerator_quota_fairness_audit.py)
    - Policy: [config/accelerator-quota-policy.json](../config/accelerator-quota-policy.json)
    - Inputs: [capacity plan](evidence/capacity-plan.md), [tenant blast radius](evidence/tenant-blast-radius.md), [token cost guard](evidence/token-cost-guard.md), [load shedding policy audit](evidence/load-shedding-policy-audit.md), [shadow traffic replay audit](evidence/shadow-traffic-replay-audit.md), and [model release safety audit](evidence/model-release-safety-audit.md)
    - Evidence: [accelerator quota fairness audit](evidence/accelerator-quota-fairness-audit.md)

16. **Workload Identity audit**
    - Code: [demo/workload_identity_audit.py](../demo/workload_identity_audit.py)
    - Policy: [config/workload-identity-policy.json](../config/workload-identity-policy.json)
    - Inputs: GKE-shaped collector and sample workload manifests under [k8s/gke](../k8s/gke)
    - Evidence: [Workload Identity audit](evidence/workload-identity-audit.md)

17. **Namespace resource audit**
    - Code: [demo/namespace_resource_audit.py](../demo/namespace_resource_audit.py)
    - Policy: [config/namespace-resource-policy.json](../config/namespace-resource-policy.json)
    - Inputs: GKE-shaped namespace, collector, and sample workload manifests under [k8s/gke](../k8s/gke)
    - Evidence: [namespace resource audit](evidence/namespace-resource-audit.md)

18. **Availability topology audit**
    - Code: [demo/availability_topology_audit.py](../demo/availability_topology_audit.py)
    - Policy: [config/availability-topology-policy.json](../config/availability-topology-policy.json)
    - Inputs: GKE-shaped collector and sample workload manifests under [k8s/gke](../k8s/gke)
    - Evidence: [availability topology audit](evidence/availability-topology-audit.md)

19. **Autoscaling policy audit**
    - Code: [demo/autoscaling_policy_audit.py](../demo/autoscaling_policy_audit.py)
    - Policy: [config/autoscaling-policy.json](../config/autoscaling-policy.json)
    - Inputs: sample inference workload HPA and Deployment in [sample-app.yaml](../k8s/gke/sample-app.yaml)
    - Evidence: [autoscaling policy audit](evidence/autoscaling-policy-audit.md)

20. **Network boundary audit**
    - Code: [demo/network_boundary_audit.py](../demo/network_boundary_audit.py)
    - Policy: [config/network-boundary-policy.json](../config/network-boundary-policy.json)
    - Inputs: workload and collector NetworkPolicies under [k8s/gke](../k8s/gke)
    - Evidence: [network boundary audit](evidence/network-boundary-audit.md)

21. **Telemetry sampling audit**
    - Code: [demo/telemetry_sampling_audit.py](../demo/telemetry_sampling_audit.py)
    - Policy: [config/telemetry-sampling-policy.json](../config/telemetry-sampling-policy.json)
    - Inputs: collector ConfigMap and trace pipeline in [collector.yaml](../k8s/gke/collector.yaml)
    - Evidence: [telemetry sampling audit](evidence/telemetry-sampling-audit.md)

22. **Collector self-observability audit**
    - Code: [demo/collector_self_observability_audit.py](../demo/collector_self_observability_audit.py)
    - Policy: [config/collector-self-observability-policy.json](../config/collector-self-observability-policy.json)
    - Inputs: collector ConfigMap and metrics pipeline in [collector.yaml](../k8s/gke/collector.yaml)
    - Evidence: [collector self-observability audit](evidence/collector-self-observability-audit.md)

23. **Scheduling placement audit**
    - Code: [demo/scheduling_placement_audit.py](../demo/scheduling_placement_audit.py)
    - Policy: [config/scheduling-placement-policy.json](../config/scheduling-placement-policy.json)
    - Inputs: [scheduling.yaml](../k8s/gke/scheduling.yaml), [collector.yaml](../k8s/gke/collector.yaml), and [sample-app.yaml](../k8s/gke/sample-app.yaml)
    - Evidence: [scheduling placement audit](evidence/scheduling-placement-audit.md)

## Boundary

The lab is production-oriented, not production-deployed. It gives a reviewer a
repeatable local proof path and GKE-shaped manifests. A real deployment still
needs organization-specific exporters, alert routing, load tests, and security
review.
