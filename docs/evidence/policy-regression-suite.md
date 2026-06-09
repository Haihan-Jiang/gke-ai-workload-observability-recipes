# Policy Regression Suite

Overall status: **PASS**

This suite protects the deployment policy from silent drift. Each
fixture starts from the same clean release evidence and changes one
production signal to prove that promote, block, and manual-review
decisions remain stable.

## Fixtures

| Fixture | Expected | Actual | Status |
| --- | --- | --- | --- |
| `clean_release` | `promote` | `promote` | PASS |
| `burn_rate_page` | `block_production_promotion` | `block_production_promotion` | PASS |
| `slo_gate_failure` | `block_production_promotion` | `block_production_promotion` | PASS |
| `rollout_rollback` | `block_production_promotion` | `block_production_promotion` | PASS |
| `trace_quality_gap` | `block_production_promotion` | `block_production_promotion` | PASS |
| `collector_data_loss` | `block_production_promotion` | `block_production_promotion` | PASS |
| `tenant_slo_breach` | `block_production_promotion` | `block_production_promotion` | PASS |
| `hpa_and_cost_review` | `manual_review_required` | `manual_review_required` | PASS |

## Controls Under Test

- `burn_rate`
- `collector_resilience`
- `hpa_lag`
- `reliability_gate`
- `rollout_guard`
- `tenant_blast_radius`
- `token_cost_guard`
- `trace_quality`

## Operator Action Coverage

### clean_release
- none

### burn_rate_page
- Freeze rollout until burn-rate paging windows return below threshold.

### slo_gate_failure
- Resolve `reliability_gate` before production promotion.

### rollout_rollback
- Rollback or hold the candidate version before expanding traffic.

### trace_quality_gap
- Fix trace resource/span attributes before relying on incident evidence.

### collector_data_loss
- Increase collector queue/storage or reduce outage exposure.

### tenant_slo_breach
- Protect impacted tenant tier before aggregate service promotion.

### hpa_and_cost_review
- Separate dependency or rollout remediation from autoscaling changes.
- Review token/GPU regression before approving the model variant.
