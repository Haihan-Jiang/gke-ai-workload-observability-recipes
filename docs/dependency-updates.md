# Dependency Update Governance

This repository keeps dependency update automation narrow and reviewable. The
current dependency surface is intentionally small: GitHub Actions runtimes,
container images referenced by the sample manifests, and standard-library
Python scripts.

## Update Contract

| Surface | Automation | Review Boundary | Validation |
| --- | --- | --- | --- |
| GitHub Actions | Dependabot weekly updates for `.github/workflows` | Use `dependencies` and `maintenance` labels, keep open pull requests bounded, and require normal PR review. | Run `./scripts/validate.sh` and `CI=true ./scripts/validate.sh`. |
| Kubernetes images | Manual update with digest-pinned image references | Update SBOM, supply-chain, and manifest hardening evidence together. | Regenerate evidence and verify supply-chain audit, SBOM inventory, and proof-packet integrity. |
| Python scripts | No third-party runtime dependencies | New dependencies need an SBOM entry, license check, and validation contract update. | Run full unit tests and release readiness before merging. |

## Release Requirements

- Dependency update pull requests must keep release-readiness evidence green.
- GitHub Actions updates must stay on maintained major versions and preserve
  least-privilege permissions, concurrency cancellation, and the validation
  command.
- Container-image updates must stay digest-pinned and keep explicit pull
  policy, allowed registry, SBOM, and supply-chain evidence synchronized.
- New package-manager ecosystems must be added to Dependabot or documented as
  manually reviewed before public release claims are trusted.
- Security-sensitive dependency updates use private reporting guidance when
  they reveal vulnerability details before a fix is available.
- Proof packets must be regenerated so provenance and checksum manifests match
  the current dependency-update policy.
