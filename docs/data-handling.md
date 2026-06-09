# Data Handling and Retention Register

This register defines what data the local GKE AI inference reliability lab may
commit, retain, and expose in review evidence. The lab is production-oriented,
not production-deployed, and the committed replay data must remain synthetic,
local, and safe for a public repository.

## Scope

- Applies to generated incident replay payloads, committed evidence reports,
  Kubernetes sample manifests, contributor intake templates, security intake
  paths, and release-readiness proof packets.
- Does not authorize collection of production traffic, user prompts,
  responses, credentials, customer identifiers, or third-party confidential
  data.
- Reviewers can validate this boundary with `make evidence`, `make validate`,
  and `CI=true ./scripts/validate.sh`.

## Data Classes

### DC-01: Synthetic incident metadata

- Owner: release-evidence
- Retention: committed current-head evidence until replaced by regenerated
  proof-packet evidence.
- Allowed data: local replay scenario IDs, synthetic tenant IDs, synthetic
  trace IDs, status codes, latency buckets, and error counters.
- Forbidden data: production traces, customer identifiers, raw IP addresses,
  request bodies, and exported cloud account data.
- Handling controls: local replay only, no cloud account,
  synthetic scenario IDs, and no production data.
- Evidence: [replay source contract audit](evidence/replay-source-contract-audit.md)
  (`docs/evidence/replay-source-contract-audit.md`),
  [evidence provenance](evidence/evidence-provenance.md)
  (`docs/evidence/evidence-provenance.md`),
  [proof packet integrity audit](evidence/proof-packet-integrity-audit.md)
  (`docs/evidence/proof-packet-integrity-audit.md`)
- Release controls: `replay_source_contract_audit`, `evidence_provenance`,
  `proof_packet_integrity_audit`

### DC-02: AI model and tenant labels

- Owner: mlops-release
- Retention: committed only as bounded labels, not prompts or responses.
- Allowed data: model_version, tenant_tier, request priority, token counts,
  and accelerator budget labels.
- Forbidden data: no prompt text, no response text, no embeddings,
  no user-provided documents, and no customer account names.
- Handling controls: telemetry redaction, model release safety,
  shadow traffic isolation, disabled writes and side effects, and no prompt/response storage.
- Evidence: [telemetry redaction audit](evidence/telemetry-redaction-audit.md)
  (`docs/evidence/telemetry-redaction-audit.md`),
  [model release safety audit](evidence/model-release-safety-audit.md)
  (`docs/evidence/model-release-safety-audit.md`),
  [shadow traffic replay audit](evidence/shadow-traffic-replay-audit.md)
  (`docs/evidence/shadow-traffic-replay-audit.md`)
- Release controls: `telemetry_redaction_audit`,
  `model_release_safety_audit`, `shadow_traffic_replay_audit`

### DC-03: Trace attributes and span metrics

- Owner: sre-platform
- Retention: retention_days=7 budget for generated trace volume assumptions.
- Allowed data: p95 latency, error count, telemetry loss rate, span kind,
  dependency name, rollout version, and sampling policy outcome.
- Forbidden data: full payload capture, long-term baseline retention,
  unsampled healthy traffic replay, and unbounded high-cardinality attributes.
- Handling controls: bounded sampling, trace retention control,
  retention_days=7, telemetry cost budget, and observability drift checks.
- Evidence: [telemetry cost budget](evidence/telemetry-cost-budget.md)
  (`docs/evidence/telemetry-cost-budget.md`),
  [telemetry sampling audit](evidence/telemetry-sampling-audit.md)
  (`docs/evidence/telemetry-sampling-audit.md`),
  [observability drift audit](evidence/observability-drift-audit.md)
  (`docs/evidence/observability-drift-audit.md`)
- Release controls: `telemetry_cost_budget`, `telemetry_sampling_audit`,
  `observability_drift_audit`

### DC-04: Telemetry exporter configuration

- Owner: security-review
- Retention: configuration may be committed; credentials must not be committed.
- Allowed data: exporter endpoint shape, queue/retry settings,
  Workload Identity binding, and network policy intent.
- Forbidden data: static credentials, bearer tokens, webhook URLs, private
  keys, service account keys, and production exporter secrets.
- Handling controls: no static credentials, Workload Identity,
  authoritative upstream exporter, network egress restrictions, and secret hygiene scanning.
- Evidence: [Workload Identity audit](evidence/workload-identity-audit.md)
  (`docs/evidence/workload-identity-audit.md`),
  [telemetry exporter authority audit](evidence/telemetry-exporter-authority-audit.md)
  (`docs/evidence/telemetry-exporter-authority-audit.md`),
  [secret hygiene audit](evidence/secret-hygiene-audit.md)
  (`docs/evidence/secret-hygiene-audit.md`)
- Release controls: `workload_identity_audit`,
  `telemetry_exporter_authority_audit`, `secret_hygiene_audit`

### DC-05: Public evidence artifacts

- Owner: release-evidence
- Retention: current-head evidence only; regenerate before release review.
- Allowed data: checksums, generated artifacts, policy decisions, source
  inputs, validation commands, and release-readiness summaries.
- Forbidden data: stale proof packets, circular proof artifacts,
  hand-edited generated JSON, and untracked source inputs.
- Handling controls: evidence provenance, proof packet integrity,
  validation contract checks, no circular artifacts, and CI-mode committed evidence drift checks.
- Evidence: [evidence provenance](evidence/evidence-provenance.md)
  (`docs/evidence/evidence-provenance.md`),
  [proof packet integrity audit](evidence/proof-packet-integrity-audit.md)
  (`docs/evidence/proof-packet-integrity-audit.md`),
  [validation contract audit](evidence/validation-contract-audit.md)
  (`docs/evidence/validation-contract-audit.md`)
- Release controls: `evidence_provenance`, `proof_packet_integrity_audit`,
  `validation_contract_audit`

### DC-06: Contributor and security intake data

- Owner: security-review
- Retention: public issues must contain reproducible evidence only; sensitive
  reports must use private vulnerability reporting.
- Allowed data: reproduction steps, expected behavior, validation commands,
  component names, and evidence links.
- Forbidden data: no secrets in public issues, no credentials in pull requests,
  no private vulnerability details in public templates, and no customer data.
- Handling controls: private vulnerability reporting, no-secret boundaries,
  support boundary, reproducible evidence only, and public claim boundaries.
- Evidence: [maintainer intake audit](evidence/maintainer-intake-audit.md)
  (`docs/evidence/maintainer-intake-audit.md`),
  [security response audit](evidence/security-response-audit.md)
  (`docs/evidence/security-response-audit.md`),
  [public claim evidence audit](evidence/public-claim-evidence-audit.md)
  (`docs/evidence/public-claim-evidence-audit.md`)
- Release controls: `maintainer_intake_audit`, `security_response_audit`,
  `public_claim_evidence_audit`

## Retention Boundaries

- Local replay payloads are regenerated from synthetic fixtures and can be
  replaced by `make evidence`.
- Trace retention assumptions are capped by retention_days=7 in the telemetry
  cost policy.
- Public evidence artifacts are current-head proof packets, not durable
  operational records.
- Sensitive vulnerability reports are excluded from public issue templates and
  routed to private vulnerability reporting.

## Forbidden Data

- Production user prompts, responses, embeddings, request bodies, credentials,
  customer identifiers, raw IP addresses, private keys, service account keys,
  bearer tokens, webhook URLs, and private vulnerability details must not be
  committed.
- The evidence packet must not claim real production telemetry, real customer
  data, or external security review completion.

## Release Gate Bindings

The release gate must include `data_handling_audit` and must keep telemetry
redaction, replay source contract, secret hygiene, Workload Identity, telemetry
exporter authority, telemetry cost, telemetry sampling, shadow traffic,
provenance, proof-packet integrity, validation contract, maintainer intake,
security response, public-claim evidence, and observability drift controls
passing before data-handling claims are trusted.

## Review Cadence

- Every release: regenerate evidence and run `CI=true ./scripts/validate.sh`.
- On new telemetry fields: update this register, the telemetry redaction
  policy, negative fixtures, schema contract, and release-control ownership.
- On new public templates: re-check no-secret boundaries and private
  vulnerability reporting routes.
