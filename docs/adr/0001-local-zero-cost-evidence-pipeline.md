# ADR 0001: Local Zero-cost Evidence Pipeline

Status: Accepted

## Context

The lab has to be reviewable by maintainers, recruiters, and portfolio readers
without requiring a GKE cluster, paid Google Cloud resources, Docker, or private
credentials. The repository still needs to show realistic SRE signals: replayed
incidents, SLO-style gates, runbooks, dashboards, OpenSLO contracts, and release
controls.

## Decision

Keep the primary evidence pipeline deterministic, local, and zero-cost. The
default proof path is `./scripts/generate-evidence.sh` plus
`./scripts/validate.sh`, with all release artifacts committed under
`docs/evidence/`.

## Consequences

This makes the repo easy to inspect and run in CI, but it means cloud-specific
runtime behavior is represented by fixtures and policy checks rather than a live
production cluster.

Rejected alternative: make GKE, managed Prometheus, and cloud credentials part
of the default validation path. That would make the public project harder to
review and would break the zero-cost contribution boundary.

## Evidence

- `docs/evidence/reliability-gate.md`
- `docs/evidence/capacity-plan.md`
- `docs/evidence/incident-runbooks.md`
- `docs/evidence/developer-runtime-audit.md`

## Release Controls

- `reliability_gate`
- `capacity_plan`
- `runbook_coverage`
- `developer_runtime_audit`
