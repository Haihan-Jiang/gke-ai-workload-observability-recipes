# Disaster Recovery Drill

Overall status: **PASS**

This drill simulates restoring critical release evidence and platform
control-plane artifacts from a backup manifest, then compares restored
files against source SHA-256 checksums. It proves the lab can recover
the evidence needed to explain, block, roll back, or waive a release.

## Summary

- Artifacts: `32`
- Restored: `32`
- Hash matches: `32`
- Generated artifacts: `10`
- Estimated restore: `7 minutes`
- RTO: `15 minutes`
- RPO: `5 minutes`

## Artifact Groups

| Group | Count |
| --- | ---: |
| `deployment_manifests` | 6 |
| `incident_replay_evidence` | 4 |
| `observability_contracts` | 7 |
| `recovery_source_policy` | 4 |
| `release_control_evidence` | 7 |
| `security_policy_evidence` | 4 |

## Checks

| Check | Status |
| --- | --- |
| `critical_artifacts_present` | PASS |
| `restore_hash_match` | PASS |
| `group_coverage` | PASS |
| `generated_artifact_restore` | PASS |
| `rto_budget` | PASS |
| `rpo_budget` | PASS |
| `negative_fixture_coverage` | PASS |
