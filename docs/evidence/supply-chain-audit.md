# Supply Chain Audit

Overall status: **PASS**

This audit checks Kubernetes image references before treating the
manifests as production-style deployment evidence. It requires
digest-pinned images, non-floating tags, an explicit pull policy,
allowed registries, and ownership labels on workload artifacts.

## Images

| Namespace | Deployment | Container | Image |
| --- | --- | --- | --- |
| `telemetry` | `otel-collector` | `otel-collector` | `otel/opentelemetry-collector-contrib:0.112.0@sha256:2203eea06554f892c765d6eff8069cdf64ae8d4516526d03cab4a70e82775495` |
| `ai-observability-demo` | `toy-ai-inference-api` | `app` | `python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203` |

## Checks

| Check | Status |
| --- | --- |
| `image_coverage` | PASS |
| `digest_pinning` | PASS |
| `forbidden_tags` | PASS |
| `allowed_registries` | PASS |
| `pull_policy` | PASS |
| `artifact_owner_labels` | PASS |
