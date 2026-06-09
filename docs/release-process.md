# Release Process

This project does not deploy a production service. A release means the local
lab, committed evidence, Kubernetes-shaped manifests, dashboards, SLOs, and
policy checks are internally consistent at a Git revision.

## Release Candidate Steps

1. Regenerate committed evidence:

   ```bash
   make evidence
   ```

2. Run the full local validation gate:

   ```bash
   make validate
   ```

3. Run the CI-mode evidence stability gate:

   ```bash
   make ci
   ```

4. Review the generated release packet:

   - `docs/evidence/release-readiness.md`
   - `docs/evidence/evidence-provenance.md`
   - `docs/evidence/proof-packet-integrity-audit.md`
   - `docs/evidence/disaster-recovery-drill.md`
   - `docs/evidence/repository-governance-audit.md`
   - `docs/evidence/developer-runtime-audit.md`
   - `docs/evidence/security-response-audit.md`
   - `docs/evidence/security-response-audit.json`
   - `docs/evidence/architecture-decision-audit.md`
   - `docs/evidence/maintainer-intake-audit.md`
   - `docs/evidence/public-claim-evidence-audit.md`
   - `docs/evidence/release-notes-contract-audit.md`

5. Confirm the pull request CI is green and the PR merge state is clean.

6. Tag the release only after committed evidence and CI agree on the same head
   commit.

If a release candidate contains a security fix, verify the severity tier,
private reporter update, regression test or audit fixture, regenerated
evidence, and coordinated disclosure update before tagging.

## Release Notes

Release notes should state:

- the main reliability or governance capability added
- changed evidence artifacts
- validation commands that passed
- known deployment boundaries or assumptions

Use the concrete validation command names where applicable:

- `make evidence`
- `make validate`
- `make ci`
- `./scripts/generate-evidence.sh`
- `./scripts/validate.sh`
- `CI=true ./scripts/validate.sh`

## Rollback

If a release candidate fails validation, do not tag it. Fix the source input or
policy, regenerate evidence, and rerun the gates. If an already tagged release
has a broken evidence packet, publish a follow-up tag with corrected evidence
and note the superseded tag in release notes.
