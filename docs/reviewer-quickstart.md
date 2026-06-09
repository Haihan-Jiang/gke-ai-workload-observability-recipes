# Reviewer Quickstart

This page is the shortest review path for the GKE AI Inference Reliability
Lab. It is intended for a reviewer who wants to verify that the committed
evidence, source inputs, and public claims agree at the current head.

## 10-Minute Reviewer Path

Run the same release path used by contributors:

```bash
make evidence
make validate
make ci
```

The direct command equivalents are:

```bash
./scripts/generate-evidence.sh
./scripts/validate.sh
CI=true ./scripts/validate.sh
```

`make evidence` regenerates committed evidence under `docs/evidence`.
`make validate` runs the full local validation gate. `make ci` runs the
CI-mode stability gate and fails when committed evidence drifts from the
current head.

## Minimal Evidence Packet

Inspect these files first:

- [release readiness](evidence/release-readiness.md): `docs/evidence/release-readiness.md`
- [evidence provenance](evidence/evidence-provenance.md): `docs/evidence/evidence-provenance.md`
- [proof packet integrity audit](evidence/proof-packet-integrity-audit.md): `docs/evidence/proof-packet-integrity-audit.md`
- [validation contract audit](evidence/validation-contract-audit.md): `docs/evidence/validation-contract-audit.md`
- [documentation link integrity audit](evidence/documentation-link-integrity-audit.md): `docs/evidence/documentation-link-integrity-audit.md`
- [public claim evidence audit](evidence/public-claim-evidence-audit.md): `docs/evidence/public-claim-evidence-audit.md`
- [reviewer reproducibility audit](evidence/reviewer-reproducibility-audit.md): `docs/evidence/reviewer-reproducibility-audit.md`

These artifacts answer three review questions:

- Are release-readiness checks passing for this source tree?
- Do source inputs, generated artifacts, and committed evidence still match?
- Do README and industry-map claims stay inside the lab boundary?

## Release Controls To Check

The reviewer path is enforced by these release-readiness controls:

- `validation_contract_audit`
- `evidence_provenance`
- `proof_packet_integrity_audit`
- `documentation_link_integrity_audit`
- `public_claim_evidence_audit`
- `reviewer_reproducibility_audit`

## Boundary Check

This repository is a personal reference project. It is production-oriented,
not production-deployed. The quickstart requires no cloud account, No paid services,
no external credentials, and no production secrets. Optional deployment
adaptations still need organization-specific exporters, alert routing, load
tests, and security review.
