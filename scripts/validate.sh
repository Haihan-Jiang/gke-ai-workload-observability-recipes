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
  demo/supply_chain_audit.py \
  demo/k8s_hardening_audit.py \
  demo/namespace_resource_audit.py \
  demo/availability_topology_audit.py \
  demo/autoscaling_policy_audit.py \
  demo/scheduling_placement_audit.py \
  demo/rollout_safety_audit.py \
  demo/network_boundary_audit.py \
  demo/collector_self_observability_audit.py \
  demo/telemetry_sampling_audit.py \
  demo/workload_identity_audit.py \
  demo/admission_policy_audit.py \
  demo/alerting_rules.py \
  demo/grafana_dashboard.py \
  demo/openslo_contract.py \
  demo/observability_drift_audit.py \
  demo/telemetry_redaction_audit.py \
  demo/telemetry_cost_budget.py \
  demo/error_budget_ledger.py \
  demo/rollback_drill.py \
  demo/post_incident_review.py \
  demo/incident_response_drill.py \
  demo/dependency_contract_audit.py \
  demo/synthetic_probe_audit.py \
  demo/model_release_safety_audit.py \
  demo/shadow_traffic_replay_audit.py \
  demo/load_shedding_policy_audit.py \
  demo/accelerator_quota_fairness_audit.py \
  demo/regional_failover_audit.py \
  demo/release_waiver_governance.py \
  demo/disaster_recovery_drill.py \
  demo/evidence_provenance.py \
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
python3 -m json.tool config/supply-chain-policy.json >/dev/null
python3 -m json.tool config/k8s-hardening-policy.json >/dev/null
python3 -m json.tool config/namespace-resource-policy.json >/dev/null
python3 -m json.tool config/availability-topology-policy.json >/dev/null
python3 -m json.tool config/autoscaling-policy.json >/dev/null
python3 -m json.tool config/scheduling-placement-policy.json >/dev/null
python3 -m json.tool config/rollout-safety-policy.json >/dev/null
python3 -m json.tool config/network-boundary-policy.json >/dev/null
python3 -m json.tool config/collector-self-observability-policy.json >/dev/null
python3 -m json.tool config/telemetry-sampling-policy.json >/dev/null
python3 -m json.tool config/workload-identity-policy.json >/dev/null
python3 -m json.tool config/admission-policy.json >/dev/null
python3 -m json.tool config/alerting-policy.json >/dev/null
python3 -m json.tool config/dashboard-policy.json >/dev/null
python3 -m json.tool config/openslo-policy.json >/dev/null
python3 -m json.tool config/observability-drift-policy.json >/dev/null
python3 -m json.tool config/telemetry-redaction-policy.json >/dev/null
python3 -m json.tool config/telemetry-cost-policy.json >/dev/null
python3 -m json.tool config/error-budget-policy.json >/dev/null
python3 -m json.tool config/rollback-drill-policy.json >/dev/null
python3 -m json.tool config/post-incident-review-policy.json >/dev/null
python3 -m json.tool config/incident-response-policy.json >/dev/null
python3 -m json.tool config/dependency-contract-policy.json >/dev/null
python3 -m json.tool config/synthetic-probe-policy.json >/dev/null
python3 -m json.tool config/model-release-policy.json >/dev/null
python3 -m json.tool config/shadow-traffic-policy.json >/dev/null
python3 -m json.tool config/load-shedding-policy.json >/dev/null
python3 -m json.tool config/accelerator-quota-policy.json >/dev/null
python3 -m json.tool config/regional-failover-policy.json >/dev/null
python3 -m json.tool config/release-waiver-policy.json >/dev/null
python3 -m json.tool config/release-waivers.json >/dev/null
python3 -m json.tool config/disaster-recovery-policy.json >/dev/null
python3 -m json.tool config/evidence-provenance-policy.json >/dev/null
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
python3 demo/supply_chain_audit.py \
  --policy config/supply-chain-policy.json \
  --repo-root . \
  --output-dir out/supply-chain-audit-validate >/dev/null
python3 demo/k8s_hardening_audit.py \
  --policy config/k8s-hardening-policy.json \
  --repo-root . \
  --output-dir out/k8s-hardening-audit-validate >/dev/null
python3 demo/namespace_resource_audit.py \
  --policy config/namespace-resource-policy.json \
  --repo-root . \
  --output-dir out/namespace-resource-audit-validate >/dev/null
python3 demo/availability_topology_audit.py \
  --policy config/availability-topology-policy.json \
  --repo-root . \
  --output-dir out/availability-topology-audit-validate >/dev/null
python3 demo/autoscaling_policy_audit.py \
  --policy config/autoscaling-policy.json \
  --repo-root . \
  --output-dir out/autoscaling-policy-audit-validate >/dev/null
python3 demo/scheduling_placement_audit.py \
  --policy config/scheduling-placement-policy.json \
  --repo-root . \
  --output-dir out/scheduling-placement-audit-validate >/dev/null
python3 demo/rollout_safety_audit.py \
  --policy config/rollout-safety-policy.json \
  --repo-root . \
  --output-dir out/rollout-safety-audit-validate >/dev/null
python3 demo/network_boundary_audit.py \
  --policy config/network-boundary-policy.json \
  --repo-root . \
  --output-dir out/network-boundary-audit-validate >/dev/null
python3 demo/collector_self_observability_audit.py \
  --policy config/collector-self-observability-policy.json \
  --repo-root . \
  --output-dir out/collector-self-observability-audit-validate >/dev/null
python3 demo/telemetry_sampling_audit.py \
  --policy config/telemetry-sampling-policy.json \
  --repo-root . \
  --output-dir out/telemetry-sampling-audit-validate >/dev/null
python3 demo/workload_identity_audit.py \
  --policy config/workload-identity-policy.json \
  --repo-root . \
  --output-dir out/workload-identity-audit-validate >/dev/null
python3 demo/admission_policy_audit.py \
  --policy config/admission-policy.json \
  --repo-root . \
  --output-dir out/admission-policy-audit-validate >/dev/null
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
  --dashboard out/grafana-dashboard-validate/rendered-grafana-dashboard.json \
  --config-map out/grafana-dashboard-validate/grafana-dashboard-configmap.yaml >/dev/null
python3 demo/openslo_contract.py \
  --slo-config config/reliability-slo.json \
  --alert-policy config/alerting-policy.json \
  --openslo-policy config/openslo-policy.json \
  --output-dir out/openslo-contract-validate \
  --contract out/openslo-contract-validate/gke-ai-inference-slo.yaml >/dev/null
python3 demo/observability_drift_audit.py \
  --policy config/observability-drift-policy.json \
  --alerting out/alerting-rules-validate/alerting-rules.json \
  --dashboard out/grafana-dashboard-validate/grafana-dashboard.json \
  --openslo out/openslo-contract-validate/openslo-contract.json \
  --runbooks out/incident-runbooks-validate/incident-runbooks.json \
  --output-dir out/observability-drift-audit-validate >/dev/null
python3 demo/telemetry_redaction_audit.py \
  --summary out/incident-replay-validate/summary.json \
  --payload-dir out/incident-replay-payloads-validate \
  --policy config/telemetry-redaction-policy.json \
  --output-dir out/telemetry-redaction-audit-validate >/dev/null
python3 demo/telemetry_cost_budget.py \
  --summary out/incident-replay-validate/summary.json \
  --payload-dir out/incident-replay-payloads-validate \
  --policy config/telemetry-cost-policy.json \
  --output-dir out/telemetry-cost-budget-validate >/dev/null
python3 demo/error_budget_ledger.py \
  --summary out/incident-replay-validate/summary.json \
  --slo-config config/reliability-slo.json \
  --openslo-policy config/openslo-policy.json \
  --error-budget-policy config/error-budget-policy.json \
  --output-dir out/error-budget-ledger-validate >/dev/null
python3 demo/rollback_drill.py \
  --summary out/incident-replay-validate/summary.json \
  --runbooks out/incident-runbooks-validate/incident-runbooks.json \
  --deployment-policy out/deployment-policy-validate/deployment-policy.json \
  --error-budget out/error-budget-ledger-validate/error-budget-ledger.json \
  --drill-policy config/rollback-drill-policy.json \
  --output-dir out/rollback-drill-validate >/dev/null
python3 demo/post_incident_review.py \
  --summary out/incident-replay-validate/summary.json \
  --incident-correlation out/advanced-reliability-validate/incident-correlation.json \
  --rollback-drill out/rollback-drill-validate/rollback-drill.json \
  --error-budget out/error-budget-ledger-validate/error-budget-ledger.json \
  --deployment-policy out/deployment-policy-validate/deployment-policy.json \
  --policy config/post-incident-review-policy.json \
  --output-dir out/post-incident-review-validate >/dev/null
python3 demo/incident_response_drill.py \
  --policy config/incident-response-policy.json \
  --alerting out/alerting-rules-validate/alerting-rules.json \
  --runbooks out/incident-runbooks-validate/incident-runbooks.json \
  --incident-correlation out/advanced-reliability-validate/incident-correlation.json \
  --rollback-drill out/rollback-drill-validate/rollback-drill.json \
  --post-incident-review out/post-incident-review-validate/post-incident-review.json \
  --output-dir out/incident-response-drill-validate >/dev/null
python3 demo/dependency_contract_audit.py \
  --policy config/dependency-contract-policy.json \
  --summary out/incident-replay-validate/summary.json \
  --critical-path out/detailed-reliability-validate/critical-path-attribution.json \
  --runbooks out/incident-runbooks-validate/incident-runbooks.json \
  --alerting out/alerting-rules-validate/alerting-rules.json \
  --error-budget out/error-budget-ledger-validate/error-budget-ledger.json \
  --rollback-drill out/rollback-drill-validate/rollback-drill.json \
  --output-dir out/dependency-contract-audit-validate >/dev/null
python3 demo/synthetic_probe_audit.py \
  --policy config/synthetic-probe-policy.json \
  --summary out/incident-replay-validate/summary.json \
  --alerting out/alerting-rules-validate/alerting-rules.json \
  --dependency-contract out/dependency-contract-audit-validate/dependency-contract-audit.json \
  --incident-response out/incident-response-drill-validate/incident-response-drill.json \
  --rollback-drill out/rollback-drill-validate/rollback-drill.json \
  --error-budget out/error-budget-ledger-validate/error-budget-ledger.json \
  --output-dir out/synthetic-probe-audit-validate >/dev/null
python3 demo/model_release_safety_audit.py \
  --policy config/model-release-policy.json \
  --rollout-guard out/advanced-reliability-validate/rollout-guard.json \
  --trace-quality out/advanced-reliability-validate/trace-quality-audit.json \
  --token-cost out/detailed-reliability-validate/token-cost-guard.json \
  --error-budget out/error-budget-ledger-validate/error-budget-ledger.json \
  --rollback-drill out/rollback-drill-validate/rollback-drill.json \
  --synthetic-probe out/synthetic-probe-audit-validate/synthetic-probe-audit.json \
  --output-dir out/model-release-safety-audit-validate >/dev/null
python3 demo/shadow_traffic_replay_audit.py \
  --policy config/shadow-traffic-policy.json \
  --summary out/incident-replay-validate/summary.json \
  --telemetry-redaction out/telemetry-redaction-audit-validate/telemetry-redaction-audit.json \
  --rollout-guard out/advanced-reliability-validate/rollout-guard.json \
  --token-cost out/detailed-reliability-validate/token-cost-guard.json \
  --synthetic-probe out/synthetic-probe-audit-validate/synthetic-probe-audit.json \
  --model-release-safety out/model-release-safety-audit-validate/model-release-safety-audit.json \
  --output-dir out/shadow-traffic-replay-audit-validate >/dev/null
python3 demo/load_shedding_policy_audit.py \
  --policy config/load-shedding-policy.json \
  --capacity out/capacity-plan-validate/capacity-plan.json \
  --tenant-blast-radius out/detailed-reliability-validate/tenant-blast-radius.json \
  --token-cost out/detailed-reliability-validate/token-cost-guard.json \
  --error-budget out/error-budget-ledger-validate/error-budget-ledger.json \
  --synthetic-probe out/synthetic-probe-audit-validate/synthetic-probe-audit.json \
  --runbooks out/incident-runbooks-validate/incident-runbooks.json \
  --output-dir out/load-shedding-policy-audit-validate >/dev/null
python3 demo/accelerator_quota_fairness_audit.py \
  --policy config/accelerator-quota-policy.json \
  --capacity out/capacity-plan-validate/capacity-plan.json \
  --tenant-blast-radius out/detailed-reliability-validate/tenant-blast-radius.json \
  --token-cost out/detailed-reliability-validate/token-cost-guard.json \
  --load-shedding out/load-shedding-policy-audit-validate/load-shedding-policy-audit.json \
  --shadow-traffic out/shadow-traffic-replay-audit-validate/shadow-traffic-replay-audit.json \
  --model-release-safety out/model-release-safety-audit-validate/model-release-safety-audit.json \
  --output-dir out/accelerator-quota-fairness-audit-validate >/dev/null
python3 demo/disaster_recovery_drill.py \
  --repo-root . \
  --policy config/disaster-recovery-policy.json \
  --restore-dir out/disaster-recovery-restore-validate \
  --output-dir out/disaster-recovery-drill-validate >/dev/null
python3 demo/regional_failover_audit.py \
  --policy config/regional-failover-policy.json \
  --capacity out/capacity-plan-validate/capacity-plan.json \
  --error-budget out/error-budget-ledger-validate/error-budget-ledger.json \
  --rollback-drill out/rollback-drill-validate/rollback-drill.json \
  --disaster-recovery out/disaster-recovery-drill-validate/disaster-recovery-drill.json \
  --synthetic-probe out/synthetic-probe-audit-validate/synthetic-probe-audit.json \
  --load-shedding out/load-shedding-policy-audit-validate/load-shedding-policy-audit.json \
  --runbooks out/incident-runbooks-validate/incident-runbooks.json \
  --k8s-hardening out/k8s-hardening-audit-validate/k8s-hardening-audit.json \
  --output-dir out/regional-failover-audit-validate >/dev/null
python3 demo/release_waiver_governance.py \
  --policy config/release-waiver-policy.json \
  --waivers config/release-waivers.json \
  --deployment-policy out/deployment-policy-validate/deployment-policy.json \
  --error-budget out/error-budget-ledger-validate/error-budget-ledger.json \
  --rollback-drill out/rollback-drill-validate/rollback-drill.json \
  --post-incident-review out/post-incident-review-validate/post-incident-review.json \
  --output-dir out/release-waiver-governance-validate >/dev/null
./scripts/generate-evidence.sh >/dev/null
python3 demo/evidence_provenance.py \
  --policy config/evidence-provenance-policy.json \
  --repo-root . \
  --output-dir out/evidence-provenance-validate >/dev/null
python3 demo/release_readiness.py \
  --gate docs/evidence/reliability-gate.json \
  --capacity docs/evidence/capacity-plan.json \
  --runbooks docs/evidence/incident-runbooks.json \
  --advanced docs/evidence/complex-problems.json \
  --detailed docs/evidence/detailed-problems.json \
  --policy docs/evidence/deployment-policy.json \
  --policy-regression docs/evidence/policy-regression-suite.json \
  --supply-chain docs/evidence/supply-chain-audit.json \
  --k8s-hardening docs/evidence/k8s-hardening-audit.json \
  --namespace-resource docs/evidence/namespace-resource-audit.json \
  --availability-topology docs/evidence/availability-topology-audit.json \
  --autoscaling-policy docs/evidence/autoscaling-policy-audit.json \
  --scheduling-placement docs/evidence/scheduling-placement-audit.json \
  --rollout-safety docs/evidence/rollout-safety-audit.json \
  --network-boundary docs/evidence/network-boundary-audit.json \
  --collector-self-observability docs/evidence/collector-self-observability-audit.json \
  --telemetry-sampling docs/evidence/telemetry-sampling-audit.json \
  --workload-identity docs/evidence/workload-identity-audit.json \
  --admission-policy docs/evidence/admission-policy-audit.json \
  --alerting docs/evidence/alerting-rules.json \
  --dashboard docs/evidence/grafana-dashboard.json \
  --openslo docs/evidence/openslo-contract.json \
  --telemetry-redaction docs/evidence/telemetry-redaction-audit.json \
  --telemetry-cost docs/evidence/telemetry-cost-budget.json \
  --error-budget docs/evidence/error-budget-ledger.json \
  --rollback-drill docs/evidence/rollback-drill.json \
  --post-incident-review docs/evidence/post-incident-review.json \
  --incident-response-drill docs/evidence/incident-response-drill.json \
  --dependency-contract docs/evidence/dependency-contract-audit.json \
  --synthetic-probe docs/evidence/synthetic-probe-audit.json \
  --model-release-safety docs/evidence/model-release-safety-audit.json \
  --shadow-traffic-replay docs/evidence/shadow-traffic-replay-audit.json \
  --accelerator-quota docs/evidence/accelerator-quota-fairness-audit.json \
  --load-shedding-policy docs/evidence/load-shedding-policy-audit.json \
  --regional-failover docs/evidence/regional-failover-audit.json \
  --release-waiver-governance docs/evidence/release-waiver-governance.json \
  --disaster-recovery-drill docs/evidence/disaster-recovery-drill.json \
  --observability-drift docs/evidence/observability-drift-audit.json \
  --evidence-provenance docs/evidence/evidence-provenance.json \
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
python3 -m json.tool docs/evidence/supply-chain-audit.json >/dev/null
python3 -m json.tool docs/evidence/k8s-hardening-audit.json >/dev/null
python3 -m json.tool docs/evidence/namespace-resource-audit.json >/dev/null
python3 -m json.tool docs/evidence/availability-topology-audit.json >/dev/null
python3 -m json.tool docs/evidence/autoscaling-policy-audit.json >/dev/null
python3 -m json.tool docs/evidence/scheduling-placement-audit.json >/dev/null
python3 -m json.tool docs/evidence/rollout-safety-audit.json >/dev/null
python3 -m json.tool docs/evidence/network-boundary-audit.json >/dev/null
python3 -m json.tool docs/evidence/collector-self-observability-audit.json >/dev/null
python3 -m json.tool docs/evidence/telemetry-sampling-audit.json >/dev/null
python3 -m json.tool docs/evidence/workload-identity-audit.json >/dev/null
python3 -m json.tool docs/evidence/admission-policy-audit.json >/dev/null
python3 -m json.tool docs/evidence/alerting-rules.json >/dev/null
python3 -m json.tool docs/evidence/grafana-dashboard.json >/dev/null
python3 -m json.tool docs/evidence/openslo-contract.json >/dev/null
python3 -m json.tool docs/evidence/observability-drift-audit.json >/dev/null
python3 -m json.tool docs/evidence/telemetry-redaction-audit.json >/dev/null
python3 -m json.tool docs/evidence/telemetry-cost-budget.json >/dev/null
python3 -m json.tool docs/evidence/error-budget-ledger.json >/dev/null
python3 -m json.tool docs/evidence/rollback-drill.json >/dev/null
python3 -m json.tool docs/evidence/post-incident-review.json >/dev/null
python3 -m json.tool docs/evidence/incident-response-drill.json >/dev/null
python3 -m json.tool docs/evidence/dependency-contract-audit.json >/dev/null
python3 -m json.tool docs/evidence/synthetic-probe-audit.json >/dev/null
python3 -m json.tool docs/evidence/model-release-safety-audit.json >/dev/null
python3 -m json.tool docs/evidence/shadow-traffic-replay-audit.json >/dev/null
python3 -m json.tool docs/evidence/load-shedding-policy-audit.json >/dev/null
python3 -m json.tool docs/evidence/accelerator-quota-fairness-audit.json >/dev/null
python3 -m json.tool docs/evidence/regional-failover-audit.json >/dev/null
python3 -m json.tool docs/evidence/release-waiver-governance.json >/dev/null
python3 -m json.tool docs/evidence/disaster-recovery-drill.json >/dev/null
python3 -m json.tool docs/evidence/evidence-provenance.json >/dev/null
python3 -m json.tool dashboards/grafana/gke-ai-inference-reliability.json >/dev/null
python3 -m unittest discover -s tests

if [ "${CI:-}" = "true" ] && command -v git >/dev/null 2>&1; then
  git diff --exit-code -- docs/evidence k8s/gke/alerting-rules.yaml k8s/gke/grafana-dashboard-configmap.yaml dashboards/grafana/gke-ai-inference-reliability.json slos/openslo/gke-ai-inference-slo.yaml
fi

if command -v ruby >/dev/null 2>&1; then
  yaml_files="$(find .github collector k8s policies slos -type f \( -name '*.yaml' -o -name '*.yml' \) 2>/dev/null | sort)"
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
