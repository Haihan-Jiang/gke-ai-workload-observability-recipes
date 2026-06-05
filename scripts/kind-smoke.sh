#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cluster_name="${KIND_CLUSTER_NAME:-gke-ai-reliability-lab}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 is required for the kind smoke test" >&2
    exit 1
  fi
}

need kubectl
need kind

if ! kind get clusters | grep -qx "${cluster_name}"; then
  if [ "${CREATE_KIND_CLUSTER:-0}" != "1" ]; then
    echo "kind cluster '${cluster_name}' does not exist." >&2
    echo "Run with CREATE_KIND_CLUSTER=1 to create it." >&2
    exit 1
  fi
  kind create cluster --name "${cluster_name}"
fi

kubectl config use-context "kind-${cluster_name}" >/dev/null
kubectl apply -f "${repo_root}/k8s/gke/namespace.yaml"
kubectl apply -f "${repo_root}/k8s/gke/collector.yaml"

if kubectl api-resources --api-group=opentelemetry.io | grep -q '^instrumentations'; then
  kubectl apply -f "${repo_root}/k8s/gke/instrumentation.yaml"
else
  echo "OpenTelemetry Operator CRDs are not installed; skipping Instrumentation." >&2
fi

kubectl apply -f "${repo_root}/k8s/gke/sample-app.yaml"
kubectl -n telemetry rollout status deploy/otel-collector --timeout=120s
kubectl -n ai-observability-demo rollout status deploy/toy-ai-inference-api --timeout=120s

kubectl -n telemetry port-forward svc/otel-collector 4318:4318 >/tmp/gke-ai-reliability-otel-port-forward.log 2>&1 &
port_forward_pid="$!"
cleanup() {
  kill "${port_forward_pid}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

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
raise SystemExit("collector port-forward did not open 4318")
PY

python3 "${repo_root}/demo/incident_replay.py" \
  --endpoint http://127.0.0.1:4318/v1/traces \
  --output-dir "${repo_root}/out/kind-incident-replay"
python3 "${repo_root}/demo/reliability_gate.py" \
  --summary "${repo_root}/out/kind-incident-replay/summary.json" \
  --slo-config "${repo_root}/config/reliability-slo.json" \
  --output-dir "${repo_root}/out/kind-reliability-gate"

echo "kind smoke passed"
echo "report: ${repo_root}/out/kind-incident-replay/report.md"
echo "gate: ${repo_root}/out/kind-reliability-gate/reliability-gate.md"
