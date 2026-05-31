#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

python3 -m py_compile demo/send_otlp_trace.py demo/otlp_debug_receiver.py

if command -v ruby >/dev/null 2>&1; then
  yaml_files="$(find collector k8s -type f \( -name '*.yaml' -o -name '*.yml' \) | sort)"
  if [ -n "${yaml_files}" ]; then
    ruby -ryaml -e 'ARGV.each { |f| YAML.load_stream(File.read(f)); puts "ok #{f}" }' ${yaml_files}
  fi
else
  echo "ruby not found; skipping YAML parse validation" >&2
fi

echo "validation complete"
