# OSS License Audit

Overall status: **PASS**

This audit checks the public open-source compliance boundary for the
lab: Apache-2.0 license text, NOTICE coverage, README license links,
approved GitHub Actions, approved container images, and third-party
reference inventory.

## Summary

| Metric | Value |
| --- | ---: |
| GitHub Actions references | 2 |
| Container image references | 4 |
| Third-party references | 6 |
| Detected fixtures | 6 |

## Checks

| Check | Status |
| --- | --- |
| `license_file` | PASS |
| `notice_file` | PASS |
| `readme_license_reference` | PASS |
| `approved_actions` | PASS |
| `approved_images` | PASS |
| `third_party_reference_inventory` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Expected Failed Check | Detected |
| --- | --- | --- |
| `missing_license` | `license_file` | yes |
| `missing_notice` | `notice_file` | yes |
| `missing_readme_notice_link` | `readme_license_reference` | yes |
| `unapproved_action` | `approved_actions` | yes |
| `unapproved_image` | `approved_images` | yes |
| `notice_missing_third_party` | `notice_file` | yes |
