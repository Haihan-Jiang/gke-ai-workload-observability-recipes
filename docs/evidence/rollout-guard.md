# Rollout Guard

- Baseline: `baseline`
- Candidate: `rollout_regression` / `v2`
- p95 ratio: `9.48`
- error rate delta: `0.29`
- decision: **ROLLBACK**

Violations:
- p95 ratio 9.48 exceeds 3.0
- error delta 0.29 exceeds 0.05
- cache miss delta 0.43 exceeds 0.25
