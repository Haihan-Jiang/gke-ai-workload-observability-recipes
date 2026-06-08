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
python3 demo/deployment_policy.py \
  --gate docs/evidence/reliability-gate.json \
  --burn-rate docs/evidence/burn-rate-analysis.json \
  --rollout-guard docs/evidence/rollout-guard.json \
  --trace-quality docs/evidence/trace-quality-audit.json \
  --collector-resilience docs/evidence/collector-resilience.json \
  --hpa-lag docs/evidence/hpa-lag-analysis.json \
  --tenant-blast-radius docs/evidence/tenant-blast-radius.json \
  --token-cost-guard docs/evidence/token-cost-guard.json \
  --output-dir docs/evidence >/dev/null
python3 demo/policy_regression_suite.py \
  --fixtures config/deployment-policy-fixtures.json \
  --output-dir docs/evidence >/dev/null
python3 demo/k8s_hardening_audit.py \
  --policy config/k8s-hardening-policy.json \
  --repo-root . \
  --output-dir docs/evidence >/dev/null
python3 demo/alerting_rules.py \
  --slo-config config/reliability-slo.json \
  --policy config/alerting-policy.json \
  --output-dir docs/evidence \
  --manifest k8s/gke/alerting-rules.yaml >/dev/null
python3 demo/grafana_dashboard.py \
  --slo-config config/reliability-slo.json \
  --alert-policy config/alerting-policy.json \
  --dashboard-policy config/dashboard-policy.json \
  --output-dir docs/evidence \
  --dashboard dashboards/grafana/gke-ai-inference-reliability.json \
  --config-map k8s/gke/grafana-dashboard-configmap.yaml >/dev/null
python3 demo/render_incident_evidence.py \
  --input "${source_dir}/summary.json" \
  --output-dir docs/evidence
python3 demo/release_readiness.py \
  --gate docs/evidence/reliability-gate.json \
  --capacity docs/evidence/capacity-plan.json \
  --runbooks docs/evidence/incident-runbooks.json \
  --advanced docs/evidence/complex-problems.json \
  --detailed docs/evidence/detailed-problems.json \
  --policy docs/evidence/deployment-policy.json \
  --policy-regression docs/evidence/policy-regression-suite.json \
  --k8s-hardening docs/evidence/k8s-hardening-audit.json \
  --alerting docs/evidence/alerting-rules.json \
  --dashboard docs/evidence/grafana-dashboard.json \
  --evidence-dir docs/evidence \
  --output-dir docs/evidence >/dev/null

echo "evidence generated under docs/evidence"
