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

## Ten Concrete Industry Problems

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

## Boundary

The lab is production-oriented, not production-deployed. It gives a reviewer a
repeatable local proof path and GKE-shaped manifests. A real deployment still
needs organization-specific exporters, alert routing, load tests, and security
review.
