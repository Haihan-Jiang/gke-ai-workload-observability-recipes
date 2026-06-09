# Secret Hygiene Audit

Overall status: **PASS**

This audit scans committed source, manifests, documentation, and
generated evidence for high-confidence secret formats before release
readiness is reported.

## Summary

| Metric | Value |
| --- | ---: |
| Scanned files | 346 |
| Generated evidence files scanned | 141 |
| Deny patterns | 6 |
| Findings | 0 |
| Skipped files | 0 |
| Detected fixtures | 6 |

## Checks

| Check | Status |
| --- | --- |
| `scanned_file_inventory` | PASS |
| `generated_evidence_scan` | PASS |
| `deny_pattern_catalog` | PASS |
| `secret_pattern_scan` | PASS |
| `negative_fixture_coverage` | PASS |

## Negative Fixtures

| Fixture | Pattern | Expected Failed Check | Detected |
| --- | --- | --- | --- |
| `private_key_header_fixture` | `private_key_header` | `secret_pattern_scan` | yes |
| `aws_access_key_fixture` | `aws_access_key_id` | `secret_pattern_scan` | yes |
| `google_api_key_fixture` | `google_api_key` | `secret_pattern_scan` | yes |
| `github_token_fixture` | `github_token` | `secret_pattern_scan` | yes |
| `slack_webhook_fixture` | `slack_webhook` | `secret_pattern_scan` | yes |
| `slack_token_fixture` | `slack_token` | `secret_pattern_scan` | yes |
