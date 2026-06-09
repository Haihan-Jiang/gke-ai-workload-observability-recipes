# Architecture Decision Records

These ADRs capture the project-level decisions behind the reliability lab. They
are intentionally tied to committed evidence and release-readiness checks so a
reviewer can inspect both the rationale and the proof surface.

| ADR | Decision |
| --- | --- |
| [ADR 0001](0001-local-zero-cost-evidence-pipeline.md) | Keep the primary reliability evidence local and zero-cost. |
| [ADR 0002](0002-fail-closed-release-readiness.md) | Treat release readiness as a fail-closed evidence gate. |
| [ADR 0003](0003-privacy-safe-incident-replay-boundary.md) | Keep incident replay data synthetic and privacy-safe. |
| [ADR 0004](0004-policy-as-code-change-control.md) | Put change-control contracts in policy-as-code plus tests. |
