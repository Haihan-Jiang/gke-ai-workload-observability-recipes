#!/usr/bin/env python3
"""Generate and audit an OpenSLO-style service-level objective contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo import alerting_rules, reliability_gate


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def quote(value: str) -> str:
    return json.dumps(value)


def selector(alert_policy: dict[str, Any]) -> str:
    return alerting_rules.service_selector(alert_policy)


def build_sli_queries(slo_config: dict[str, Any], alert_policy: dict[str, Any]) -> dict[str, str]:
    baseline = reliability_gate.scenario_slo(slo_config, "baseline")
    rollout = reliability_gate.scenario_slo(slo_config, "rollout_regression")
    service_selector = selector(alert_policy)
    rollout_selector = alerting_rules.service_selector(
        alert_policy,
        {"service_version": str(rollout["expected_service_version"])},
    )
    latency_threshold = alerting_rules.seconds(baseline["max_p95_ms"])
    rollout_threshold = alerting_rules.seconds(rollout["min_p95_ms"])
    total = f"sum(rate(http_server_duration_seconds_count{{{service_selector}}}[5m]))"
    error = (
        f"sum(rate(http_server_duration_seconds_count{{{service_selector},"
        "http_response_status_code=~\"5..\"}[5m]))"
    )
    latency_bad = (
        "histogram_quantile(0.95, "
        f"sum by (le) (rate(http_server_duration_seconds_bucket{{{service_selector}}}[5m]))) "
        f"> {latency_threshold}"
    )
    rollout_bad = (
        "histogram_quantile(0.95, "
        f"sum by (le) (rate(http_server_duration_seconds_bucket{{{rollout_selector}}}[5m]))) "
        f"> {rollout_threshold}"
    )
    telemetry_loss = (
        "sum(rate(otelcol_exporter_send_failed_spans_total[5m])) "
        "/ clamp_min("
        "sum(rate(otelcol_exporter_sent_spans_total[5m])) + "
        "sum(rate(otelcol_exporter_send_failed_spans_total[5m])), 1)"
    )
    return {
        "total": total,
        "error": error,
        "good": f"{total} - ({error})",
        "baseline_latency": latency_bad,
        "rollout_latency": rollout_bad,
        "telemetry_loss": telemetry_loss,
    }


def build_contract(
    slo_config: dict[str, Any],
    alert_policy: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    openslo = policy["openslo"]
    service = policy["service"]
    queries = build_sli_queries(slo_config, alert_policy)
    scenarios = list(policy["required_scenarios"])
    return {
        "apiVersion": openslo["api_version"],
        "kind": openslo["kind"],
        "metadata": {
            "name": openslo["name"],
            "displayName": openslo["display_name"],
            "labels": {
                "service": service["name"],
                "namespace": service["namespace"],
                "team": service["team"],
                "owner": service["owner"],
            },
            "annotations": {
                "description": openslo["description"],
                "profile": slo_config["profile"],
            },
        },
        "spec": {
            "service": service["name"],
            "indicator": {
                "metadata": {"name": "inference-request-quality"},
                "spec": {
                    "ratioMetric": {
                        "counter": True,
                        "good": {"metricSource": {"type": "prometheus", "query": queries["good"]}},
                        "total": {"metricSource": {"type": "prometheus", "query": queries["total"]}},
                    }
                },
            },
            "latencyGuardrails": [
                {
                    "name": "baseline-p95-latency",
                    "scenario": "baseline",
                    "metricSource": {"type": "prometheus", "query": queries["baseline_latency"]},
                },
                {
                    "name": "rollout-p95-latency",
                    "scenario": "rollout_regression",
                    "metricSource": {"type": "prometheus", "query": queries["rollout_latency"]},
                },
            ],
            "objective": {
                "displayName": openslo["objective_display"],
                "target": openslo["target"],
                "timeWindow": [{"duration": openslo["time_window"], "isRolling": True}],
                "budgetingMethod": openslo["budgeting_method"],
            },
            "scenarios": scenarios,
            "operationalLinks": {
                "alerting_rules": "docs/evidence/alerting-rules.md",
                "grafana_dashboard": "docs/evidence/grafana-dashboard.md",
                "release_readiness": "docs/evidence/release-readiness.md",
                "runbooks": "docs/evidence/incident-runbooks.md",
            },
            "telemetryQuality": {
                "lossRatioQuery": queries["telemetry_loss"],
                "evidence": "docs/evidence/collector-resilience.md",
            },
        },
    }


def render_yaml(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(render_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {render_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(render_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {render_scalar(item)}")
        return lines
    return [f"{prefix}{render_scalar(value)}"]


def render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    return quote(str(value))


def evaluate(contract: dict[str, Any], policy: dict[str, Any], contract_yaml: str) -> dict[str, Any]:
    spec = contract.get("spec", {})
    objective = spec.get("objective", {})
    indicator = spec.get("indicator", {}).get("spec", {}).get("ratioMetric", {})
    scenarios = set(spec.get("scenarios", []))
    links = spec.get("operationalLinks", {})
    latency_guardrails = spec.get("latencyGuardrails", [])
    required_scenarios = set(policy.get("required_scenarios", []))
    required_links = set(policy.get("required_links", []))
    good_query = indicator.get("good", {}).get("metricSource", {}).get("query", "")
    total_query = indicator.get("total", {}).get("metricSource", {}).get("query", "")
    checks = [
        {
            "name": "openslo_shape",
            "ok": contract.get("apiVersion") == policy["openslo"]["api_version"]
            and contract.get("kind") == policy["openslo"]["kind"]
            and bool(contract.get("metadata", {}).get("name")),
            "evidence": {"apiVersion": contract.get("apiVersion"), "kind": contract.get("kind")},
        },
        {
            "name": "objective_target",
            "ok": float(objective.get("target", 0)) >= 99.0
            and bool(objective.get("timeWindow"))
            and objective.get("budgetingMethod") == policy["openslo"]["budgeting_method"],
            "evidence": objective,
        },
        {
            "name": "prometheus_ratio_metric",
            "ok": "prometheus" in json.dumps(indicator)
            and "http_server_duration_seconds_count" in total_query
            and "http_server_duration_seconds_count" in good_query,
            "evidence": {"total_query": total_query, "good_query": good_query},
        },
        {
            "name": "latency_guardrails",
            "ok": len(latency_guardrails) >= 2
            and all(
                "http_server_duration_seconds_bucket"
                in item.get("metricSource", {}).get("query", "")
                for item in latency_guardrails
            ),
            "evidence": {"guardrails": latency_guardrails},
        },
        {
            "name": "scenario_coverage",
            "ok": scenarios >= required_scenarios,
            "evidence": {"observed": sorted(scenarios), "required": sorted(required_scenarios)},
        },
        {
            "name": "operational_links",
            "ok": set(links) >= required_links,
            "evidence": {"links": links},
        },
        {
            "name": "telemetry_quality",
            "ok": "otelcol_exporter_send_failed_spans_total" in spec.get("telemetryQuality", {}).get("lossRatioQuery", ""),
            "evidence": spec.get("telemetryQuality", {}),
        },
        {
            "name": "yaml_rendered",
            "ok": "apiVersion:" in contract_yaml and "kind:" in contract_yaml and "spec:" in contract_yaml,
            "evidence": {"bytes": len(contract_yaml.encode("utf-8"))},
        },
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "objective_target": objective.get("target"),
        "scenario_count": len(scenarios),
        "failed_count": sum(1 for item in checks if not item["ok"]),
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.joinpath("openslo-contract.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], contract: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# OpenSLO Contract Evidence",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This generated contract makes the lab's SLO machine-readable. It ties",
        "the service objective to Prometheus SLI queries, scenario coverage,",
        "telemetry-quality evidence, alerting rules, dashboards, release",
        "readiness, and runbooks.",
        "",
        "## Contract",
        "",
        f"- Name: `{contract['metadata']['name']}`",
        f"- Service: `{contract['spec']['service']}`",
        f"- Target: `{contract['spec']['objective']['target']}%`",
        f"- Time window: `{contract['spec']['objective']['timeWindow'][0]['duration']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    output_dir.joinpath("openslo-contract.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slo-config", default="config/reliability-slo.json")
    parser.add_argument("--alert-policy", default="config/alerting-policy.json")
    parser.add_argument("--openslo-policy", default="config/openslo-policy.json")
    parser.add_argument("--output-dir", default="out/openslo-contract")
    parser.add_argument("--contract", default="slos/openslo/gke-ai-inference-slo.yaml")
    args = parser.parse_args()

    slo_config = reliability_gate.load_slo_config(Path(args.slo_config))
    alert_policy = alerting_rules.load_json(Path(args.alert_policy))
    policy = load_json(Path(args.openslo_policy))
    contract = build_contract(slo_config, alert_policy, policy)
    contract_yaml = "\n".join(render_yaml(contract)) + "\n"
    report = evaluate(contract, policy, contract_yaml)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, contract, output_dir)

    contract_path = Path(args.contract)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(contract_yaml, encoding="utf-8")

    print(f"wrote {output_dir / 'openslo-contract.json'}")
    print(f"wrote {output_dir / 'openslo-contract.md'}")
    print(f"wrote {contract_path}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
