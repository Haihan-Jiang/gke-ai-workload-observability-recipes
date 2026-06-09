# Security Policy

This repository is a local reliability lab, but security issues can still
matter because the manifests, workflows, and policies are intended to be copied
or adapted.

## Reporting

Do not open a public issue with exploit details, credentials, tokens, private
data, or a working abuse path. Use GitHub private vulnerability reporting if it
is available for this repository. If a private channel is not available, open a
minimal public issue asking for a private reporting path and omit sensitive
details.

## Supported Scope

Security-sensitive reports include:

- secrets, credentials, or private data committed to the repo
- workflow permissions that allow unexpected writes or secret exposure
- Kubernetes manifests that normalize privileged containers, broad RBAC, static
  cloud keys, unrestricted egress, or unsafe admission-policy bypasses
- generated evidence that contains prompts, responses, direct identifiers, or
  secret-like values

Reports about real production deployments are out of scope for this lab unless
they map back to committed code, manifests, policy, or documentation here.

## Handling Expectations

Security fixes should include a regression test or audit fixture whenever
possible. If a fix changes generated evidence, regenerate the evidence and run
the full validation commands from `CONTRIBUTING.md`.

## Response SLAs

Every security report is triaged by severity before release readiness is
claimed. The clock starts when the report reaches a private reporting channel.

| Severity | Examples | Triage SLA | Target action |
| --- | --- | ---: | --- |
| Critical | Credential exposure, public exploit path, write-capable workflow escape | triage within 24 hours | block release and prepare a fix or rollback within 72 hours |
| High | Privileged manifest drift, broad RBAC, unsafe admission bypass | triage within 48 hours | block affected release path until fixed or waived |
| Medium | Evidence leak without exploitable credentials, missing security fixture | triage within 120 hours | require fix or explicit release waiver before tag |
| Low | Documentation ambiguity or hardening improvement without active exposure | triage within 240 hours | track in the next routine governance pass |

Critical and High reports block release promotion unless the fix, rollback, or
time-bound waiver is linked from the release evidence packet. Security fixes
must include a regression test or audit fixture where the repo can express the
failure mode locally.

## Disclosure and Updates

Keep reporter updates private until a fix or mitigation is available. Do not publish exploit details until a fix is available, and keep credentials, tokens, private data, and working abuse paths out of public issues, release notes, and
generated evidence.

When a fix ships, add a coordinated disclosure update that states the affected surface, severity, evidence regenerated, validation commands run, and any
follow-up release or rollback action. The `security-response-audit` must pass
before release readiness can claim the security-response workflow is current.
