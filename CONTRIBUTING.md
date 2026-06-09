# Contributing

This project is a reliability lab, so changes should be reviewable as code and
as generated evidence. A contribution is ready when a reviewer can reproduce
the same release packet locally.

## Local Validation

Before opening a pull request, run:

```bash
make evidence
make validate
make ci
```

`make evidence` refreshes committed evidence under `docs/evidence`. `make ci`
verifies that generated evidence is stable against the committed files.

## Pull Request Checklist

- Keep changes scoped to one reliability, policy, or documentation concern.
- Update policy files when changing audit behavior.
- Add or update unit tests for new checks and negative fixtures.
- Regenerate committed evidence after changing replay logic, policies,
  manifests, dashboards, SLOs, workflow files, or governance docs.
- Security-sensitive changes must follow SECURITY.md and keep the
  security-response-audit evidence aligned with private reporting, severity
  SLAs, fix evidence, and disclosure updates.
- Summarize which evidence changed and which validation commands were run.

## Evidence Rules

Evidence files are committed intentionally. Do not hand-edit generated evidence
without also updating the generator, policy, or source input that explains the
change.

Generated JSON should stay machine-readable and deterministic. Generated
Markdown should summarize the same facts for reviewers.

## Repository Boundaries

This is a local, zero-cost lab. Do not add paid cloud dependencies, external
credentials, production secrets, or organization-specific endpoints. Keep
examples portable unless a document explicitly marks a step as deployment-only.
