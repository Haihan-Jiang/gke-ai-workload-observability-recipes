#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

python3 -m py_compile \
  demo/send_otlp_trace.py \
  demo/otlp_debug_receiver.py \
  demo/incident_replay.py \
  demo/render_incident_evidence.py

python3 demo/incident_replay.py --no-send --output-dir out/incident-replay-validate >/dev/null
./scripts/generate-evidence.sh >/dev/null
python3 -m json.tool docs/evidence/sample-summary.json >/dev/null

if [ "${CI:-}" = "true" ] && command -v git >/dev/null 2>&1; then
  git diff --exit-code -- docs/evidence
fi

if command -v ruby >/dev/null 2>&1; then
  yaml_files="$(find .github collector k8s -type f \( -name '*.yaml' -o -name '*.yml' \) 2>/dev/null | sort)"
  if [ -f docker-compose.yaml ]; then
    yaml_files="${yaml_files}
docker-compose.yaml"
  fi
  if [ -n "${yaml_files}" ]; then
    ruby -ryaml -e 'ARGV.each { |f| YAML.load_stream(File.read(f)); puts "ok #{f}" }' ${yaml_files}
  fi
else
  echo "ruby not found; skipping YAML parse validation" >&2
fi

echo "validation complete"
