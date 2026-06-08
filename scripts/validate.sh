#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

python3 -m py_compile \
  demo/send_otlp_trace.py \
  demo/otlp_debug_receiver.py \
  demo/incident_replay.py \
  demo/advanced_reliability.py \
  demo/detailed_reliability.py \
  demo/deployment_policy.py \
  demo/policy_regression_suite.py \
  demo/k8s_hardening_audit.py \
  demo/alerting_rules.py \
  demo/grafana_dashboard.py \
  demo/capacity_planner.py \
  demo/runbook_generator.py \
  demo/release_readiness.py \
  demo/reliability_gate.py \
  demo/render_incident_evidence.py

python3 demo/incident_replay.py \
  --no-send \
  --output-dir out/incident-replay-validate \
  --payload-dir out/incident-replay-payloads-validate >/dev/null
python3 -m json.tool config/reliability-slo.json >/dev/null
python3 -m json.tool config/advanced-reliability.json >/dev/null
python3 -m json.tool config/detailed-reliability.json >/dev/null
python3 -m json.tool config/deployment-policy-fixtures.json >/dev/null
python3 -m json.tool config/k8s-hardening-policy.json >/dev/null
python3 -m json.tool config/alerting-policy.json >/dev/null
python3 -m json.tool config/dashboard-policy.json >/dev/null
python3 demo/reliability_gate.py \
  --summary out/incident-replay-validate/summary.json \
  --slo-config config/reliability-slo.json \
  --output-dir out/reliability-gate-validate >/dev/null
python3 demo/capacity_planner.py \
  --summary out/incident-replay-validate/summary.json \
  --slo-config config/reliability-slo.json \
  --output-dir out/capacity-plan-validate >/dev/null
python3 demo/runbook_generator.py \
  --summary out/incident-replay-validate/summary.json \
  --gate out/reliability-gate-validate/reliability-gate.json \
  --output-dir out/incident-runbooks-validate >/dev/null
python3 demo/advanced_reliability.py \
  --summary out/incident-replay-validate/summary.json \
  --payload-dir out/incident-replay-payloads-validate \
  --slo-config config/reliability-slo.json \
  --advanced-config config/advanced-reliability.json \
  --output-dir out/advanced-reliability-validate >/dev/null
python3 demo/detailed_reliability.py \
  --summary out/incident-replay-validate/summary.json \
  --payload-dir out/incident-replay-payloads-validate \
  --detailed-config config/detailed-reliability.json \
  --output-dir out/detailed-reliability-validate >/dev/null
python3 demo/deployment_policy.py \
  --gate out/reliability-gate-validate/reliability-gate.json \
  --burn-rate out/advanced-reliability-validate/burn-rate-analysis.json \
  --rollout-guard out/advanced-reliability-validate/rollout-guard.json \
  --trace-quality out/advanced-reliability-validate/trace-quality-audit.json \
  --collector-resilience out/advanced-reliability-validate/collector-resilience.json \
  --hpa-lag out/detailed-reliability-validate/hpa-lag-analysis.json \
  --tenant-blast-radius out/detailed-reliability-validate/tenant-blast-radius.json \
  --token-cost-guard out/detailed-reliability-validate/token-cost-guard.json \
  --output-dir out/deployment-policy-validate >/dev/null
python3 demo/policy_regression_suite.py \
  --fixtures config/deployment-policy-fixtures.json \
  --output-dir out/policy-regression-suite-validate >/dev/null
python3 demo/k8s_hardening_audit.py \
  --policy config/k8s-hardening-policy.json \
  --repo-root . \
  --output-dir out/k8s-hardening-audit-validate >/dev/null
python3 demo/alerting_rules.py \
  --slo-config config/reliability-slo.json \
  --policy config/alerting-policy.json \
  --output-dir out/alerting-rules-validate \
  --manifest out/alerting-rules-validate/alerting-rules.yaml >/dev/null
python3 demo/grafana_dashboard.py \
  --slo-config config/reliability-slo.json \
  --alert-policy config/alerting-policy.json \
  --dashboard-policy config/dashboard-policy.json \
  --output-dir out/grafana-dashboard-validate \
  --dashboard out/grafana-dashboard-validate/grafana-dashboard.json \
  --config-map out/grafana-dashboard-validate/grafana-dashboard-configmap.yaml >/dev/null
./scripts/generate-evidence.sh >/dev/null
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
  --output-dir out/release-readiness-validate >/dev/null
python3 -m json.tool docs/evidence/sample-summary.json >/dev/null
python3 -m json.tool docs/evidence/reliability-gate.json >/dev/null
python3 -m json.tool docs/evidence/capacity-plan.json >/dev/null
python3 -m json.tool docs/evidence/incident-runbooks.json >/dev/null
python3 -m json.tool docs/evidence/release-readiness.json >/dev/null
python3 -m json.tool docs/evidence/burn-rate-analysis.json >/dev/null
python3 -m json.tool docs/evidence/rollout-guard.json >/dev/null
python3 -m json.tool docs/evidence/trace-quality-audit.json >/dev/null
python3 -m json.tool docs/evidence/collector-resilience.json >/dev/null
python3 -m json.tool docs/evidence/incident-correlation.json >/dev/null
python3 -m json.tool docs/evidence/complex-problems.json >/dev/null
python3 -m json.tool docs/evidence/critical-path-attribution.json >/dev/null
python3 -m json.tool docs/evidence/evidence-coverage.json >/dev/null
python3 -m json.tool docs/evidence/hpa-lag-analysis.json >/dev/null
python3 -m json.tool docs/evidence/tenant-blast-radius.json >/dev/null
python3 -m json.tool docs/evidence/token-cost-guard.json >/dev/null
python3 -m json.tool docs/evidence/detailed-problems.json >/dev/null
python3 -m json.tool docs/evidence/deployment-policy.json >/dev/null
python3 -m json.tool docs/evidence/policy-regression-suite.json >/dev/null
python3 -m json.tool docs/evidence/k8s-hardening-audit.json >/dev/null
python3 -m json.tool docs/evidence/alerting-rules.json >/dev/null
python3 -m json.tool docs/evidence/grafana-dashboard.json >/dev/null
python3 -m json.tool dashboards/grafana/gke-ai-inference-reliability.json >/dev/null
python3 -m unittest discover -s tests

if [ "${CI:-}" = "true" ] && command -v git >/dev/null 2>&1; then
  git diff --exit-code -- docs/evidence k8s/gke/alerting-rules.yaml k8s/gke/grafana-dashboard-configmap.yaml dashboards/grafana/gke-ai-inference-reliability.json
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
