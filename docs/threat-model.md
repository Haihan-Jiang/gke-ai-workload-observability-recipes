# Threat Model and Risk Register

This threat model covers the local GKE AI inference reliability lab and the
committed evidence packet used to review it. The lab is production-oriented,
not production-deployed, so the model focuses on controls that can be verified
locally before any real cluster adaptation.

## Scope and Assets

- A1: incident replay traces
- A2: AI inference request metadata
- A3: telemetry exporter credentials and identity
- A4: Kubernetes admission controls
- A5: model release artifacts
- A6: committed evidence packet

## Trust Boundaries

- TB-01: Local replay to committed evidence boundary
- TB-02: Workload namespace to telemetry collector boundary
- TB-03: Telemetry export boundary
- TB-04: Admission control boundary
- TB-05: Public repository review boundary
- TB-06: Model rollout promotion boundary

## Risk Register

### TM-01: Unauthorized telemetry export route

- Asset: A3 telemetry exporter credentials and identity
- Trust boundary: TB-03: Telemetry export boundary
- Abuse case: a local debug exporter or broad network rule becomes the only
  trusted delivery path for traces and metrics.
- Owner: security-review
- Mitigations: authoritative upstream exporter, bounded local debug export,
  queued retry delivery, workload identity binding, and namespace egress restrictions.
- Evidence: [telemetry exporter authority audit](evidence/telemetry-exporter-authority-audit.md)
  (`docs/evidence/telemetry-exporter-authority-audit.md`),
  [network boundary audit](evidence/network-boundary-audit.md)
  (`docs/evidence/network-boundary-audit.md`),
  [Workload Identity audit](evidence/workload-identity-audit.md)
  (`docs/evidence/workload-identity-audit.md`)
- Release controls: `telemetry_exporter_authority_audit`,
  `network_boundary_audit`, `workload_identity_audit`
- Residual risk: low after exporter authority, identity binding, and network
  egress controls.

### TM-02: Admission bypass or private cluster webhook dependency

- Asset: A4 Kubernetes admission controls
- Trust boundary: TB-04: Admission control boundary
- Abuse case: sample manifests appear protected while pods bypass restricted
  admission or require an unreachable private-cluster webhook.
- Owner: security-review
- Mitigations: restricted Pod Security Admission, native admission policy,
  fail-closed admission binding, and optional operator skip paths.
- Evidence: [Pod Security Admission audit](evidence/pod-security-admission-audit.md)
  (`docs/evidence/pod-security-admission-audit.md`),
  [admission policy audit](evidence/admission-policy-audit.md)
  (`docs/evidence/admission-policy-audit.md`),
  [private cluster admission boundary audit](evidence/private-cluster-admission-boundary-audit.md)
  (`docs/evidence/private-cluster-admission-boundary-audit.md`)
- Release controls: `pod_security_admission_audit`,
  `admission_policy_audit`, `private_cluster_admission_boundary_audit`
- Residual risk: low after native admission controls and private-cluster
  dependency checks.

### TM-03: Prompt/response leakage through telemetry

- Asset: A2 AI inference request metadata
- Trust boundary: TB-02: Workload namespace to telemetry collector boundary
- Abuse case: trace payloads retain prompt text, response text, tokens, or
  secrets while still looking like useful observability evidence.
- Owner: security-review
- Mitigations: telemetry redaction, replay source contract checks,
  secret hygiene scanning, safe model and tenant labels, and no prompt/response storage in committed evidence.
- Evidence: [telemetry redaction audit](evidence/telemetry-redaction-audit.md)
  (`docs/evidence/telemetry-redaction-audit.md`),
  [replay source contract audit](evidence/replay-source-contract-audit.md)
  (`docs/evidence/replay-source-contract-audit.md`),
  [secret hygiene audit](evidence/secret-hygiene-audit.md)
  (`docs/evidence/secret-hygiene-audit.md`)
- Release controls: `telemetry_redaction_audit`,
  `replay_source_contract_audit`, `secret_hygiene_audit`
- Residual risk: low after redaction, replay contract, and secret-hygiene
  controls.

### TM-04: Supply chain image drift or unapproved runtime

- Asset: A5 model release artifacts
- Trust boundary: TB-05: Public repository review boundary
- Abuse case: sample deployment recipes normalize floating images, unapproved
  actions, unclear license terms, or runtime tools that reviewers cannot trace.
- Owner: security-review
- Mitigations: digest-pinned images, approved action inventory,
  CycloneDX-style SBOM inventory, Apache-2.0 license and NOTICE coverage, and
  source-file traceability for third-party references.
- Evidence: [supply chain audit](evidence/supply-chain-audit.md)
  (`docs/evidence/supply-chain-audit.md`),
  [SBOM inventory audit](evidence/sbom-inventory-audit.md)
  (`docs/evidence/sbom-inventory-audit.md`),
  [OSS license audit](evidence/oss-license-audit.md)
  (`docs/evidence/oss-license-audit.md`)
- Release controls: `supply_chain_audit`, `sbom_inventory_audit`,
  `oss_license_audit`
- Residual risk: low after image pinning, SBOM inventory, and license review.

### TM-05: Model rollout causes unsafe capacity or tenant impact

- Asset: A5 model release artifacts
- Trust boundary: TB-06: Model rollout promotion boundary
- Abuse case: a candidate model or accelerator change expands before capacity,
  tenant priority, cost, and fallback behavior are proven.
- Owner: mlops-release
- Mitigations: model release safety, accelerator quota fairness,
  load-shedding policy, tenant blast-radius checks, and rollback evidence.
- Evidence: [model release safety audit](evidence/model-release-safety-audit.md)
  (`docs/evidence/model-release-safety-audit.md`),
  [accelerator quota fairness audit](evidence/accelerator-quota-fairness-audit.md)
  (`docs/evidence/accelerator-quota-fairness-audit.md`),
  [load-shedding policy audit](evidence/load-shedding-policy-audit.md)
  (`docs/evidence/load-shedding-policy-audit.md`)
- Release controls: `model_release_safety_audit`,
  `accelerator_quota_fairness_audit`, `load_shedding_policy_audit`
- Residual risk: medium until real tenant traffic and capacity telemetry are
  validated in the target cluster.

### TM-06: Evidence packet tampering or stale proof

- Asset: A6 committed evidence packet
- Trust boundary: TB-01: Local replay to committed evidence boundary
- Abuse case: a reviewer trusts stale generated evidence, missing source
  inputs, or circular proof artifacts after the repository changes.
- Owner: release-evidence
- Mitigations: evidence provenance, proof packet integrity,
  validation contract checks, control traceability, and CI-mode committed evidence drift checks.
- Evidence: [evidence provenance](evidence/evidence-provenance.md)
  (`docs/evidence/evidence-provenance.md`),
  [proof packet integrity audit](evidence/proof-packet-integrity-audit.md)
  (`docs/evidence/proof-packet-integrity-audit.md`),
  [validation contract audit](evidence/validation-contract-audit.md)
  (`docs/evidence/validation-contract-audit.md`),
  [control traceability audit](evidence/control-traceability-audit.md)
  (`docs/evidence/control-traceability-audit.md`)
- Release controls: `evidence_provenance`, `proof_packet_integrity_audit`,
  `validation_contract_audit`, `control_traceability_audit`
- Residual risk: low after current-head provenance and proof-packet checks.

## Release Gate Bindings

The release gate must include `threat_model_audit` as a tier-0 evidence control
and must also keep the referenced security, identity, network, admission,
privacy, supply-chain, model-release, validation, traceability, provenance, and
proof-packet controls passing.

## Review Cadence

- Every release: regenerate evidence, run `make validate`, and run
  `CI=true ./scripts/validate.sh`.
- Monthly: review residual risk text against new threat classes and new
  cluster assumptions.
- On control change: update this threat model, the policy file, the negative
  fixtures, and the release-control ownership entry together.
