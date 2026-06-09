# ADR 0004: Policy-as-code Change Control

Status: Accepted

## Context

The lab keeps reliability behavior, governance expectations, and public claims
in many places: Kubernetes manifests, policy JSON, documentation, generated
evidence, tests, and CI. Manual checklists alone are too weak to keep these
surfaces aligned.

## Decision

Put change-control contracts in policy-as-code plus tests. Each new release
surface should have a policy file, executable audit, negative fixtures,
committed evidence, release-readiness check, and traceability entry before the
public README claims it.

## Consequences

Adding a control requires touching several files, but the repo gains an
inspectable chain from policy input to generated evidence to public claim.

Rejected alternative: document the intended behavior only in prose. Prose is
useful for orientation, but without a runnable contract it drifts quickly.

## Evidence

- `docs/evidence/evidence-pipeline-audit.md`
- `docs/evidence/evidence-schema-audit.md`
- `docs/evidence/control-traceability-audit.md`
- `docs/evidence/public-claim-evidence-audit.md`
- `docs/evidence/release-notes-contract-audit.md`

## Release Controls

- `evidence_pipeline_audit`
- `evidence_schema_audit`
- `control_traceability_audit`
- `public_claim_evidence_audit`
- `release_notes_contract_audit`
