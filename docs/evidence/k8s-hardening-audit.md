# Kubernetes Manifest Hardening Audit

Overall status: **PASS**

This audit checks that the GKE-style manifests include the production
controls a platform team would expect before using telemetry as release
evidence: resource budgets, health probes, restricted collector
security context, durable queues, disruption protection, and network
policy boundaries.

## Checks

| Check | Status | Reason |
| --- | --- | --- |
| `namespace_labels` | PASS | Namespaces carry ownership and role labels for policy selection. |
| `collector_readonly_rbac` | PASS | Collector has a service account with explicit read-only cluster metadata RBAC. |
| `collector_resources` | PASS | Collector container declares CPU and memory requests and limits. |
| `collector_probes` | PASS | Collector exposes readiness and liveness probes backed by the health_check extension. |
| `collector_security_context` | PASS | Collector pod and container security contexts use non-root, RuntimeDefault seccomp, no privilege escalation, and dropped capabilities. |
| `collector_durable_queue` | PASS | Collector has PVC-backed file storage, queued export, retry, and health check configuration. |
| `collector_pdb` | PASS | Collector has a PodDisruptionBudget to prevent voluntary disruption from evicting the only collector. |
| `collector_network_policy` | PASS | Collector ingress is scoped by NetworkPolicy to OTLP ports from workload namespaces. |
| `sample_workload_resources` | PASS | Sample workload has CPU and memory requests and limits so scheduler pressure is represented in the recipe. |
| `sample_workload_probes` | PASS | Sample workload has readiness and liveness probes for staged rollout behavior. |
| `sample_workload_security_context` | PASS | Sample workload runs as non-root with RuntimeDefault seccomp, no privilege escalation, and dropped capabilities. |
