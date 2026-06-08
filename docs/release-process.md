# Release Process

This project does not deploy a production service. A release means the local
lab, committed evidence, Kubernetes-shaped manifests, dashboards, SLOs, and
policy checks are internally consistent at a Git revision.

## Release Candidate Steps

1. Regenerate committed evidence:

   ```bash
   ./scripts/generate-evidence.sh
   ```

2. Run the full local validation gate:

   ```bash
   ./scripts/validate.sh
   ```

3. Run the CI-mode evidence stability gate:

   ```bash
   CI=true ./scripts/validate.sh
   ```

4. Review the generated release packet:

   - `docs/evidence/release-readiness.md`
   - `docs/evidence/evidence-provenance.md`
   - `docs/evidence/disaster-recovery-drill.md`
   - `docs/evidence/repository-governance-audit.md`

5. Confirm the pull request CI is green and the PR merge state is clean.

6. Tag the release only after committed evidence and CI agree on the same head
   commit.

## Release Notes

Release notes should state:

- the main reliability or governance capability added
- changed evidence artifacts
- validation commands that passed
- known deployment boundaries or assumptions

## Rollback

If a release candidate fails validation, do not tag it. Fix the source input or
policy, regenerate evidence, and rerun the gates. If an already tagged release
has a broken evidence packet, publish a follow-up tag with corrected evidence
and note the superseded tag in release notes.
