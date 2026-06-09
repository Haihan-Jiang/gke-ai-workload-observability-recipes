# Documentation Link Integrity Audit

Overall status: **PASS**

This audit checks committed Markdown documentation links without
network access. Local repository links must resolve, local Markdown
anchors must exist, paths must stay inside the repository, and external
links must use approved schemes.

## Summary

- Markdown files: `82`
- Local links: `545`
- External links: `14`
- Image links: `3`
- Missing targets: `0`
- Bad anchors: `0`
- Bad schemes: `0`
- Detected negative fixtures: `6`

## Checks

| Check | Status |
| --- | --- |
| `required_file_inventory` | PASS |
| `markdown_inventory` | PASS |
| `path_safety` | PASS |
| `scheme_contract` | PASS |
| `local_link_targets` | PASS |
| `anchor_targets` | PASS |
| `link_volume_contract` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Detected |
| --- | --- |
| `missing_required_file` | yes |
| `broken_local_link` | yes |
| `unsafe_parent_path` | yes |
| `file_uri_link` | yes |
| `unsupported_external_scheme` | yes |
| `missing_anchor` | yes |
