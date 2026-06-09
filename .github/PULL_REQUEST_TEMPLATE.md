## Summary

Describe the reliability, evidence, policy, manifest, or documentation change.

## Evidence changed

List the committed evidence files, policy files, and source inputs that changed.

## Validation commands

- [ ] `./scripts/generate-evidence.sh`
- [ ] `./scripts/validate.sh`
- [ ] `CI=true ./scripts/validate.sh`

## Boundary / risk notes

State deployment assumptions, local-lab boundaries, and any remaining review risk.

## Checklist

- [ ] I updated policy files when changing audit behavior.
- [ ] I regenerated committed evidence after changing source inputs.
- [ ] I did not add paid cloud dependencies, external credentials, production secrets, or organization-specific endpoints.
- [ ] Security-sensitive changes follow `SECURITY.md`.
