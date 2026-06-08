# Developer Runtime

This repository is intentionally lightweight. The main validation and evidence
tools use the Python standard library only, with Ruby used for YAML parsing in
the local validators.

## Required Tools

- Python 3.12 or newer; CI runs Python 3.12.
- Ruby, used to parse Kubernetes and GitHub Actions YAML.
- Git, used by the CI-mode evidence stability check.
- Make, used as the stable local command entrypoint.

No pip dependencies are required for the committed validation path.

## Standard Commands

```bash
make evidence
make validate
make ci
make test
```

These targets wrap the underlying scripts:

- `make evidence` runs `./scripts/generate-evidence.sh`
- `make validate` runs `./scripts/validate.sh`
- `make ci` runs `CI=true ./scripts/validate.sh`
- `make test` runs `python3 -m unittest discover -s tests`

Optional runtime checks:

- `make demo` runs the local incident replay demo.
- `make kind-smoke` runs the kind/Kubernetes smoke path and requires Docker,
  kind, and kubectl.

## Output Boundary

Generated local output belongs under `out/`. The committed evidence packet
lives under `docs/evidence/` and should be regenerated through
`make evidence`, not edited by hand.
