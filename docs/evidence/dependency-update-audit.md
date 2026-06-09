# Dependency Update Audit

Overall status: **PASS**

This audit checks that dependency update automation, review limits,
validation documentation, and release-control linkage stay in sync
before dependency-maintenance claims are trusted.

## Summary

- Updates configured: `1`
- Ecosystems covered: `1`
- Weekly schedules: `1`
- Labels configured: `2`
- Validation terms: `8`
- Release controls linked: `6`
- Detected negative fixtures: `7`

## Updates

| Ecosystem | Directory | Interval | Open PR limit |
| --- | --- | --- | ---: |
| `github-actions` | `/` | `weekly` | `5` |

## Checks

| Check | Status |
| --- | --- |
| `config_file_contract` | PASS |
| `ecosystem_contract` | PASS |
| `schedule_contract` | PASS |
| `review_boundary_contract` | PASS |
| `validation_linkage` | PASS |
| `release_control_linkage` | PASS |
| `negative_fixture_coverage` | PASS |
