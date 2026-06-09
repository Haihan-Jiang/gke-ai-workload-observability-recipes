# Admission Policy Audit

Overall status: **PASS**

This audit verifies that the lab has a Kubernetes admission policy
pack for deployment guardrails and simulates admission decisions
against both the committed manifests and negative fixtures. It is
meant to prove the recipe can prevent later drift, not only detect
drift after a manifest has already changed.

Policy manifest: `policies/admission/gke-ai-inference-admission-policy.yaml`

## Current Deployment Decisions

| Namespace | Deployment | Decision | Failed controls |
| --- | --- | --- | --- |
| `telemetry` | `otel-collector` | `allow` | - |
| `ai-observability-demo` | `toy-ai-inference-api` | `allow` | - |

## Negative Fixtures

| Fixture | Decision | Failed controls |
| --- | --- | --- |
| `missing_owner_label` | `deny` | owner_labels |
| `unpinned_image` | `deny` | digest_pinned_images |
| `latest_tag` | `deny` | allowed_registry |
| `disallowed_registry` | `deny` | allowed_registry |
| `root_pod` | `deny` | restricted_pod_security |
| `privileged_container` | `deny` | restricted_container_security |
| `privilege_escalation` | `deny` | restricted_container_security |
| `missing_resources` | `deny` | container_resources |
| `missing_probes` | `deny` | health_probes |
| `missing_instrumentation` | `deny` | otel_instrumentation |

## Policy Manifest Checks

| Check | Status |
| --- | --- |
| `validating_admission_policy_present` | PASS |
| `validating_admission_policy_binding_present` | PASS |
| `failure_policy_fail` | PASS |
| `deny_action` | PASS |
| `control_owner_labels` | PASS |
| `control_digest_pinned_images` | PASS |
| `control_allowed_registry` | PASS |
| `control_restricted_pod_security` | PASS |
| `control_restricted_container_security` | PASS |
| `control_container_resources` | PASS |
| `control_health_probes` | PASS |
| `control_otel_instrumentation` | PASS |
