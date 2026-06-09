# ADR 0002: Fail-closed Release Readiness

Status: Accepted

## Context

The repo has many generated artifacts. A missing policy input, stale evidence
file, broken provenance link, or untested release control should block a release
claim instead of being treated as a warning.

## Decision

Treat release readiness as a fail-closed gate. Release claims pass only when the
committed evidence, policy inputs, validation commands, provenance, proof packet,
disaster-recovery drill, and release-control ownership all agree.

## Consequences

The release packet is stricter and requires more generated evidence churn after
control changes, but stale or partially generated proof is visible before a PR
is described as release-ready.

Rejected alternative: rely on the unit test suite alone. Unit tests are useful,
but they do not prove that committed evidence, source inputs, and public claims
still match each other.

## Evidence

- `docs/evidence/release-readiness.md`
- `docs/evidence/evidence-provenance.md`
- `docs/evidence/proof-packet-integrity-audit.md`
- `docs/evidence/disaster-recovery-drill.md`
- `docs/evidence/validation-contract-audit.md`

## Release Controls

- `release_control_ownership_audit`
- `evidence_provenance`
- `proof_packet_integrity_audit`
- `disaster_recovery_drill`
- `validation_contract_audit`
