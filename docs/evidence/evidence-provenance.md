# Evidence Provenance

Overall status: **PASS**

This manifest records checksums for committed evidence, generated
Kubernetes/Grafana/OpenSLO artifacts, and source inputs used to build
the lab's release-readiness packet. It makes stale or hand-edited
evidence easier to detect during review.

## Summary

- Evidence artifacts: `60`
- Generated artifacts: `4`
- Source inputs: `40`
- Generator runtime: `python3`
- Environment: `not recorded in committed provenance`

## Checks

| Check | Status |
| --- | --- |
| `required_evidence_present` | PASS |
| `generated_artifacts_present` | PASS |
| `source_inputs_present` | PASS |
| `checksum_coverage` | PASS |
| `no_release_readiness_cycle` | PASS |
| `validation_commands_recorded` | PASS |

## Evidence Artifacts

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `docs/evidence/README.md` | 1828 | `c19c48be847e7bfe...` |
| `docs/evidence/sample-incident-report.md` | 1724 | `59e9fed419453327...` |
| `docs/evidence/sample-summary.json` | 3636 | `a9c0fbbd61757a14...` |
| `docs/evidence/incident-dashboard.svg` | 5392 | `7a3bf4e6a6b905d5...` |
| `docs/evidence/reliability-gate.md` | 2269 | `fdf4578c1e04d987...` |
| `docs/evidence/reliability-gate.json` | 3086 | `8be3c76bddda1ff0...` |
| `docs/evidence/capacity-plan.md` | 1434 | `38e6d8fe2069ded0...` |
| `docs/evidence/capacity-plan.json` | 2180 | `891adf904eb3d54c...` |
| `docs/evidence/incident-runbooks.md` | 2953 | `ed6688f70ce83153...` |
| `docs/evidence/incident-runbooks.json` | 4688 | `9fb15720fa290d57...` |
| `docs/evidence/burn-rate-analysis.md` | 195 | `0b7a6e04425b613f...` |
| `docs/evidence/burn-rate-analysis.json` | 2287 | `3ed8c60b547b1291...` |
| `docs/evidence/rollout-guard.md` | 264 | `d73b44c36dba71e4...` |
| `docs/evidence/rollout-guard.json` | 387 | `e502eea5eda3d254...` |
| `docs/evidence/trace-quality-audit.md` | 338 | `73ec4010be1b9067...` |
| `docs/evidence/trace-quality-audit.json` | 1052 | `b2e7e4afe7303dfc...` |
| `docs/evidence/collector-resilience.md` | 300 | `8e1058cc736b780c...` |
| `docs/evidence/collector-resilience.json` | 320 | `eceac35e826c9c82...` |
| `docs/evidence/incident-correlation.md` | 645 | `64dbe640d11030db...` |
| `docs/evidence/incident-correlation.json` | 1328 | `bc3798beed148dcb...` |
| `docs/evidence/complex-problems.md` | 551 | `220a2b276c1ad733...` |
| `docs/evidence/complex-problems.json` | 1253 | `3326e7c23f26ef19...` |
| `docs/evidence/critical-path-attribution.md` | 413 | `17b9f3a1eec81742...` |
| `docs/evidence/critical-path-attribution.json` | 1556 | `48943addc48dcfa4...` |
| `docs/evidence/evidence-coverage.md` | 451 | `61c8349c8961fb7d...` |
| `docs/evidence/evidence-coverage.json` | 1173 | `f77ce0c8db59026c...` |
| `docs/evidence/hpa-lag-analysis.md` | 415 | `9c5f80bc3e959877...` |
| `docs/evidence/hpa-lag-analysis.json` | 1110 | `d33cc63c4f31e332...` |
| `docs/evidence/tenant-blast-radius.md` | 542 | `82bba5aa390dc75b...` |
| `docs/evidence/tenant-blast-radius.json` | 1110 | `df0e132cc7d291e0...` |
| `docs/evidence/token-cost-guard.md` | 517 | `c26e82448404c261...` |
| `docs/evidence/token-cost-guard.json` | 1327 | `32c80c96004b36f2...` |
| `docs/evidence/detailed-problems.md` | 539 | `78ce6f820cfba3fe...` |
| `docs/evidence/detailed-problems.json` | 1167 | `50b12d7c922963d1...` |
| `docs/evidence/deployment-policy.md` | 1415 | `87d4b5d310290098...` |
| `docs/evidence/deployment-policy.json` | 3414 | `2ae8bb2d23a19799...` |
| `docs/evidence/policy-regression-suite.md` | 1982 | `0d9de009001bd476...` |
| `docs/evidence/policy-regression-suite.json` | 6535 | `7dd9e792da764830...` |
| `docs/evidence/supply-chain-audit.md` | 942 | `41257ce5665a058e...` |
| `docs/evidence/supply-chain-audit.json` | 1667 | `7d881ef96bd2b874...` |
| `docs/evidence/k8s-hardening-audit.md` | 1843 | `04ff59b9155bc9d8...` |
| `docs/evidence/k8s-hardening-audit.json` | 4673 | `40cad4f46752bda1...` |
| `docs/evidence/admission-policy-audit.md` | 1859 | `f9af1e271477a16c...` |
| `docs/evidence/admission-policy-audit.json` | 47340 | `1fd2253203c05806...` |
| `docs/evidence/alerting-rules.md` | 1034 | `dc833704511d7837...` |
| `docs/evidence/alerting-rules.json` | 6615 | `8c9278ce2776866d...` |
| `docs/evidence/grafana-dashboard.md` | 1103 | `5d0c98a3c0e701fb...` |
| `docs/evidence/grafana-dashboard.json` | 1926 | `68f5e1bb13fea33c...` |
| `docs/evidence/openslo-contract.md` | 700 | `9b2366251ff6f451...` |
| `docs/evidence/openslo-contract.json` | 3510 | `ddc38e70e54d1d34...` |
| `docs/evidence/telemetry-redaction-audit.md` | 776 | `35efa6766be8fef1...` |
| `docs/evidence/telemetry-redaction-audit.json` | 1939 | `1373496609126636...` |
| `docs/evidence/telemetry-cost-budget.md` | 1044 | `2b8c54aba1ed3e2e...` |
| `docs/evidence/telemetry-cost-budget.json` | 2677 | `9f4cf6ae138dac05...` |
| `docs/evidence/error-budget-ledger.md` | 1480 | `2a8675408140b55c...` |
| `docs/evidence/error-budget-ledger.json` | 5844 | `79f425445b01cc43...` |
| `docs/evidence/rollback-drill.md` | 3125 | `ae27bc6572e849ec...` |
| `docs/evidence/rollback-drill.json` | 7303 | `cc4aec75bddfde0d...` |
| `docs/evidence/post-incident-review.md` | 4616 | `9b4bdec414410760...` |
| `docs/evidence/post-incident-review.json` | 10972 | `ff1e12e67db2fd06...` |

## Generated Artifacts

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `k8s/gke/alerting-rules.yaml` | 5309 | `54eff2985cc0abda...` |
| `k8s/gke/grafana-dashboard-configmap.yaml` | 12051 | `d7369a9a8293c442...` |
| `dashboards/grafana/gke-ai-inference-reliability.json` | 10359 | `23f2f89bd868a58d...` |
| `slos/openslo/gke-ai-inference-slo.yaml` | 2806 | `1b50b2762030a99e...` |

## Validation Commands

- `./scripts/generate-evidence.sh`
- `./scripts/validate.sh`
- `CI=true ./scripts/validate.sh`
- `python3 -m unittest discover -s tests`
