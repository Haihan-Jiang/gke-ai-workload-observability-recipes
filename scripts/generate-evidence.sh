#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

source_dir="out/evidence-source"

python3 demo/incident_replay.py --no-send --output-dir "${source_dir}" >/dev/null
python3 demo/reliability_gate.py \
  --summary "${source_dir}/summary.json" \
  --slo-config config/reliability-slo.json \
  --output-dir docs/evidence >/dev/null
python3 demo/capacity_planner.py \
  --summary "${source_dir}/summary.json" \
  --slo-config config/reliability-slo.json \
  --output-dir docs/evidence >/dev/null
python3 demo/runbook_generator.py \
  --summary "${source_dir}/summary.json" \
  --gate docs/evidence/reliability-gate.json \
  --output-dir docs/evidence >/dev/null
python3 demo/render_incident_evidence.py \
  --input "${source_dir}/summary.json" \
  --output-dir docs/evidence
python3 demo/release_readiness.py \
  --gate docs/evidence/reliability-gate.json \
  --capacity docs/evidence/capacity-plan.json \
  --runbooks docs/evidence/incident-runbooks.json \
  --evidence-dir docs/evidence \
  --output-dir docs/evidence >/dev/null

echo "evidence generated under docs/evidence"
