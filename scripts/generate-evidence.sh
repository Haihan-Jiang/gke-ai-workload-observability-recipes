#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

source_dir="out/evidence-source"

python3 demo/incident_replay.py --no-send --output-dir "${source_dir}" >/dev/null
python3 demo/render_incident_evidence.py \
  --input "${source_dir}/summary.json" \
  --output-dir docs/evidence

echo "evidence generated under docs/evidence"
