# ADR 0003: Privacy-safe Incident Replay Boundary

Status: Accepted

## Context

Incident replay is useful only if reviewers can inspect the payloads. Public
payloads must not contain customer data, credentials, private endpoints, exploit
steps, or production traces.

## Decision

Keep incident replay data synthetic, local, and privacy-safe. Payload and trace
contracts must include model, tenant, scenario, and service-version metadata
while rejecting private data, credentials, and unsafe security details.

## Consequences

Synthetic incidents cannot prove real customer traffic behavior, but they make
the debugging model inspectable and keep the public repo safe to fork, run, and
review.

Rejected alternative: import production traces or cloud logs. That would create
privacy, security, and access-control risk in a public repository.

## Evidence

- `docs/evidence/replay-source-contract-audit.md`
- `docs/evidence/secret-hygiene-audit.md`
- `docs/evidence/telemetry-redaction-audit.md`
- `docs/evidence/maintainer-intake-audit.md`

## Release Controls

- `replay_source_contract_audit`
- `secret_hygiene_audit`
- `telemetry_redaction_audit`
- `maintainer_intake_audit`
