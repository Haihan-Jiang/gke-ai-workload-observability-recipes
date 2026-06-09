# Deployment Policy Decision

Decision: **block_production_promotion**

This policy-as-code report combines replay evidence into a production
promotion decision. It is intentionally stricter than a demo summary:
a release can have valid telemetry and still be blocked by burn-rate,
tenant impact, or cost signals.

## Controls

| Control | Severity | Reason |
| --- | --- | --- |
| `reliability_gate` | `pass` | SLO gate passed. |
| `burn_rate` | `block` | One or more burn-rate windows require paging. |
| `rollout_guard` | `block` | Canary rollout guard recommends rollback. |
| `trace_quality` | `pass` | Trace evidence has required resource, root-span, and child-span fields. |
| `collector_resilience` | `pass` | Collector queue and persistent storage are inside modeled outage budget. |
| `hpa_lag` | `review` | Some scenarios are not solved by autoscaling and need dependency or rollout remediation. |
| `tenant_blast_radius` | `block` | Tenant SLO breach detected. |
| `token_cost_guard` | `review` | Token/GPU cost policy requires review. |

## Operator Actions

- Freeze rollout until burn-rate paging windows return below threshold.
- Rollback or hold the candidate version before expanding traffic.
- Separate dependency or rollout remediation from autoscaling changes.
- Protect impacted tenant tier before aggregate service promotion.
- Review token/GPU regression before approving the model variant.
