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
