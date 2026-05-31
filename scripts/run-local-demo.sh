#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to send the demo OTLP trace" >&2
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
container_name="gke-ai-observability-otelcol"
receiver_pid=""
report_dir="${repo_root}/out/incident-replay"

cleanup() {
  if command -v docker >/dev/null 2>&1; then
    docker rm -f "${container_name}" >/dev/null 2>&1 || true
  fi
  if [ -n "${receiver_pid}" ]; then
    kill "${receiver_pid}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

wait_for_port() {
  python3 - <<'PY'
import socket
import time

deadline = time.time() + 30
while time.time() < deadline:
    try:
        with socket.create_connection(("127.0.0.1", 4318), timeout=1):
            raise SystemExit(0)
    except OSError:
        time.sleep(0.5)
raise SystemExit("OTLP receiver did not open port 4318 in time")
PY
}

cleanup

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  docker run \
    --detach \
    --name "${container_name}" \
    --publish 4318:4318 \
    --volume "${repo_root}/collector/local-demo.yaml:/etc/otelcol/config.yaml:ro" \
    otel/opentelemetry-collector-contrib:0.112.0 \
    --config=/etc/otelcol/config.yaml >/dev/null
  wait_for_port
  python3 "${repo_root}/demo/incident_replay.py" --output-dir "${report_dir}"
  sleep 2

  echo
  echo "collector debug output:"
  docker logs "${container_name}" 2>&1 | tail -n 120
else
  echo "Docker daemon is not available; using the Python OTLP debug receiver."
  python3 "${repo_root}/demo/otlp_debug_receiver.py" &
  receiver_pid="$!"
  wait_for_port
  python3 "${repo_root}/demo/incident_replay.py" --output-dir "${report_dir}"
  sleep 1
fi

echo
echo "incident replay report: ${report_dir}/report.md"
