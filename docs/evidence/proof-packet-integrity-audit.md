# Proof Packet Integrity Audit

Overall status: **PASS**

This audit re-checks the evidence provenance manifest against the
current repository tree. It proves that release evidence, generated
artifacts, and source inputs still match the checksums that release
readiness consumes, while keeping release-readiness and provenance
artifacts out of the manifest cycle.

## Summary

- Manifest entries: `282`
- Evidence artifacts: `141`
- Generated artifacts: `4`
- Source inputs: `137`
- Matched digests: `282`
- Missing paths: `0`
- Digest mismatches: `0`
- Circular artifacts: `0`
- Detected negative fixtures: `6`

## Checks

| Check | Status |
| --- | --- |
| `provenance_status_contract` | PASS |
| `manifest_inventory` | PASS |
| `path_safety_contract` | PASS |
| `checksum_contract` | PASS |
| `current_digest_match` | PASS |
| `circular_artifact_boundary` | PASS |
| `validation_command_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `source_digest_drift` | yes |
| `missing_evidence_artifact` | yes |
| `release_readiness_cycle` | yes |
| `absolute_manifest_path` | yes |
| `duplicate_manifest_path` | yes |
| `missing_ci_validation_command` | yes |
