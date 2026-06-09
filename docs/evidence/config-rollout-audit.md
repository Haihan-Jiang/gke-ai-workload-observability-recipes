# Config Rollout Audit

Overall status: **PASS**

This audit verifies that the collector ConfigMap is bound to Deployment
rollouts through a pod-template checksum, that the reviewed config is
mounted read-only at the path used by the collector process, and that
the config does not embed restricted inline literals.

## Summary

- ConfigMaps: `1`
- Deployments: `1`
- Checksum annotations: `1`
- Read-only config mounts: `1`
- Inline markers: `0`
- Detected negative fixtures: `10`
- Config hash: `64d88167c358c61a25a3fd0076c1dd3e6b783a90a70d080cb9dfa5b0944458b6`

## Checks

| Check | Status |
| --- | --- |
| `config_map_schema` | PASS |
| `checksum_rollout_binding` | PASS |
| `config_path_alignment` | PASS |
| `config_volume_mount_safety` | PASS |
| `config_inline_value_hygiene` | PASS |
| `config_label_governance` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_config_map` | yes |
| `missing_config_key` | yes |
| `missing_checksum_annotation` | yes |
| `stale_checksum_annotation` | yes |
| `config_changed_without_checksum` | yes |
| `writable_config_mount` | yes |
| `wrong_config_arg` | yes |
| `inline_restricted_literal` | yes |
| `missing_config_map_owner_label` | yes |
| `missing_deployment_owner_label` | yes |
