# Related Google Cloud OSS Work

Checked: 2026-05-31

Repository:
[GoogleCloudPlatform/opentelemetry-operator-sample](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample)

Current status: pending review. Do not describe these PRs as merged until the
upstream repository shows them merged.

| PR | Current status | What it adds |
|---|---|---|
| [#133](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample/pull/133) | open, review required | Migrates Beyla AppArmor profile usage. |
| [#134](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample/pull/134) | open, review required | Migrates OpenTelemetryCollector manifests to v1beta1. |
| [#135](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample/pull/135) | open, review required | Documents Artifact Registry Docker auth setup. |
| [#136](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample/pull/136) | open, review required | Uses PVC-backed storage for persistent collector queues. |
| [#137](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample/pull/137) | open, review required | Documents cross-namespace instrumentation references. |
| [#138](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample/pull/138) | open, review required | Adds sidecar resource detection recipe. |
| [#139](https://github.com/GoogleCloudPlatform/opentelemetry-operator-sample/pull/139) | open, review required | Adds Kubernetes cluster receiver recipe. |

Refresh command:

```bash
gh pr list -R GoogleCloudPlatform/opentelemetry-operator-sample \
  --author '@me' \
  --state open \
  --json number,title,state,isDraft,reviewDecision,headRefName,updatedAt,url
```

