#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

source_dir="out/evidence-source"
payload_dir="${source_dir}/payloads"

python3 demo/incident_replay.py --no-send --output-dir "${source_dir}" --payload-dir "${payload_dir}" >/dev/null
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
python3 demo/advanced_reliability.py \
  --summary "${source_dir}/summary.json" \
  --payload-dir "${payload_dir}" \
  --slo-config config/reliability-slo.json \
  --advanced-config config/advanced-reliability.json \
  --output-dir docs/evidence >/dev/null
python3 demo/detailed_reliability.py \
  --summary "${source_dir}/summary.json" \
  --payload-dir "${payload_dir}" \
  --detailed-config config/detailed-reliability.json \
  --output-dir docs/evidence >/dev/null
python3 demo/render_incident_evidence.py \
  --input "${source_dir}/summary.json" \
  --output-dir docs/evidence
python3 demo/release_readiness.py \
  --gate docs/evidence/reliability-gate.json \
  --capacity docs/evidence/capacity-plan.json \
  --runbooks docs/evidence/incident-runbooks.json \
  --advanced docs/evidence/complex-problems.json \
  --detailed docs/evidence/detailed-problems.json \
  --evidence-dir docs/evidence \
  --output-dir docs/evidence >/dev/null

echo "evidence generated under docs/evidence"
