#!/usr/bin/env python3
"""Generate a Grafana dashboard and audit coverage for inference SLOs."""

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


def runbook_url(alert_policy: dict[str, Any], scenario: str) -> str:
    return f"{alert_policy['runbook_base_url']}#{scenario}"


def link(alert_policy: dict[str, Any], scenario: str) -> dict[str, Any]:
    return {
        "title": f"Runbook: {scenario}",
        "url": runbook_url(alert_policy, scenario),
        "targetBlank": True,
    }


def target(ref_id: str, expr: str, legend: str, datasource: dict[str, str]) -> dict[str, Any]:
    return {
        "refId": ref_id,
        "expr": expr,
        "legendFormat": legend,
        "datasource": datasource,
    }


def panel(
    *,
    panel_id: int,
    title: str,
    panel_type: str,
    x: int,
    y: int,
    w: int,
    h: int,
    scenarios: list[str],
    targets: list[dict[str, Any]],
    alert_policy: dict[str, Any],
    unit: str = "short",
) -> dict[str, Any]:
    return {
        "id": panel_id,
        "title": title,
        "type": panel_type,
        "description": "Scenarios: " + ", ".join(scenarios),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "datasource": targets[0]["datasource"] if targets else None,
        "fieldConfig": {
            "defaults": {"unit": unit},
            "overrides": [],
        },
        "options": {},
        "targets": targets,
        "links": [link(alert_policy, scenario) for scenario in scenarios],
    }


def scenario_coverage(panel_doc: dict[str, Any]) -> set[str]:
    description = str(panel_doc.get("description", ""))
    if "Scenarios:" not in description:
        return set()
    value = description.split("Scenarios:", 1)[1]
    return {item.strip() for item in value.split(",") if item.strip()}


def build_dashboard(
    slo_config: dict[str, Any],
    alert_policy: dict[str, Any],
    dashboard_policy: dict[str, Any],
) -> dict[str, Any]:
    datasource = dashboard_policy["datasource"]
    dashboard_cfg = dashboard_policy["dashboard"]
    baseline = reliability_gate.scenario_slo(slo_config, "baseline")
    cache = reliability_gate.scenario_slo(slo_config, "cache_miss_storm")
    dependency = reliability_gate.scenario_slo(slo_config, "dependency_timeout")
    rollout = reliability_gate.scenario_slo(slo_config, "rollout_regression")
    collector = reliability_gate.scenario_slo(slo_config, "collector_queue_pressure")
    selector = alerting_rules.service_selector(alert_policy)
    rollout_selector = alerting_rules.service_selector(
        alert_policy,
        {"service_version": str(rollout["expected_service_version"])},
    )
    panels = [
        panel(
            panel_id=1,
            title="p95 latency by service version",
            panel_type="timeseries",
            x=0,
            y=0,
            w=12,
            h=8,
            scenarios=["baseline", "rollout_regression"],
            targets=[
                target(
                    "A",
                    (
                        "histogram_quantile(0.95, "
                        f"sum by (le, service_version) (rate(http_server_duration_seconds_bucket{{{selector}}}[5m])))"
                    ),
                    "p95 {{service_version}}",
                    datasource,
                ),
                target("B", str(alerting_rules.seconds(baseline["max_p95_ms"])), "baseline threshold", datasource),
                target("C", str(alerting_rules.seconds(rollout["min_p95_ms"])), "rollout threshold", datasource),
            ],
            alert_policy=alert_policy,
            unit="s",
        ),
        panel(
            panel_id=2,
            title="error rate by response class",
            panel_type="timeseries",
            x=12,
            y=0,
            w=12,
            h=8,
            scenarios=["dependency_timeout", "rollout_regression"],
            targets=[
                target(
                    "A",
                    (
                        f"sum by (http_response_status_code) (rate(http_server_duration_seconds_count{{{selector},"
                        "http_response_status_code=~\"5..\"}[5m])) "
                        f"/ clamp_min(sum(rate(http_server_duration_seconds_count{{{selector}}}[5m])), 1)"
                    ),
                    "5xx error rate",
                    datasource,
                ),
                target("B", str(dependency["min_error_rate"]), "dependency threshold", datasource),
            ],
            alert_policy=alert_policy,
            unit="percentunit",
        ),
        panel(
            panel_id=3,
            title="cache miss ratio",
            panel_type="timeseries",
            x=0,
            y=8,
            w=8,
            h=7,
            scenarios=["cache_miss_storm"],
            targets=[
                target(
                    "A",
                    (
                        f"sum(rate(ai_inference_cache_requests_total{{{selector},cache_result=\"miss\"}}[5m])) "
                        f"/ clamp_min(sum(rate(ai_inference_cache_requests_total{{{selector}}}[5m])), 1)"
                    ),
                    "cache miss ratio",
                    datasource,
                ),
                target("B", str(cache["min_cache_miss_rate"]), "storm threshold", datasource),
            ],
            alert_policy=alert_policy,
            unit="percentunit",
        ),
        panel(
            panel_id=4,
            title="collector telemetry loss",
            panel_type="timeseries",
            x=8,
            y=8,
            w=8,
            h=7,
            scenarios=["collector_queue_pressure"],
            targets=[
                target(
                    "A",
                    (
                        "sum(rate(otelcol_exporter_send_failed_spans_total[5m])) "
                        "/ clamp_min("
                        "sum(rate(otelcol_exporter_sent_spans_total[5m])) + "
                        "sum(rate(otelcol_exporter_send_failed_spans_total[5m])), 1)"
                    ),
                    "telemetry loss ratio",
                    datasource,
                ),
                target("B", str(collector["min_telemetry_loss_rate"]), "loss threshold", datasource),
            ],
            alert_policy=alert_policy,
            unit="percentunit",
        ),
        panel(
            panel_id=5,
            title="active SLO alerts",
            panel_type="table",
            x=16,
            y=8,
            w=8,
            h=7,
            scenarios=list(dashboard_policy["required_scenarios"]),
            targets=[
                target(
                    "A",
                    (
                        "ALERTS{alertstate=\"firing\","
                        f"team=\"{alert_policy['service']['team']}\","
                        f"service=\"{alert_policy['service']['name']}\"}}"
                    ),
                    "{{alertname}} {{scenario}}",
                    datasource,
                )
            ],
            alert_policy=alert_policy,
        ),
        panel(
            panel_id=6,
            title="rollout candidate p95",
            panel_type="stat",
            x=0,
            y=15,
            w=8,
            h=5,
            scenarios=["rollout_regression"],
            targets=[
                target(
                    "A",
                    (
                        "histogram_quantile(0.95, "
                        f"sum by (le) (rate(http_server_duration_seconds_bucket{{{rollout_selector}}}[5m])))"
                    ),
                    f"candidate {rollout['expected_service_version']}",
                    datasource,
                )
            ],
            alert_policy=alert_policy,
            unit="s",
        ),
    ]
    return {
        "uid": dashboard_cfg["uid"],
        "title": dashboard_cfg["title"],
        "tags": dashboard_cfg["tags"],
        "timezone": dashboard_cfg["timezone"],
        "refresh": dashboard_cfg["refresh"],
        "schemaVersion": dashboard_cfg["schema_version"],
        "version": 1,
        "editable": True,
        "templating": {"list": []},
        "time": {"from": "now-6h", "to": "now"},
        "panels": panels,
    }


def render_config_map(dashboard: dict[str, Any], policy: dict[str, Any]) -> str:
    config_map = policy["config_map"]
    dashboard_json = json.dumps(dashboard, indent=2)
    lines = [
        "apiVersion: v1",
        "kind: ConfigMap",
        "metadata:",
        f"  name: {config_map['name']}",
        f"  namespace: {config_map['namespace']}",
        "  labels:",
    ]
    for key, value in config_map["labels"].items():
        lines.append(f"    {key}: {json.dumps(str(value))}")
    lines.extend(["data:", f"  {config_map['dashboard_key']}: |"])
    lines.extend(f"    {line}" for line in dashboard_json.splitlines())
    lines.append("")
    return "\n".join(lines)


def evaluate(dashboard: dict[str, Any], policy: dict[str, Any], config_map_manifest: str) -> dict[str, Any]:
    panels = dashboard.get("panels", [])
    required_scenarios = set(policy.get("required_scenarios", []))
    observed_scenarios = set().union(*(scenario_coverage(item) for item in panels)) if panels else set()
    required_panel_types = set(policy.get("required_panel_types", []))
    observed_panel_types = {str(item.get("type", "")) for item in panels}
    missing_datasource = [
        item.get("title")
        for item in panels
        for target_doc in item.get("targets", [])
        if target_doc.get("datasource", {}).get("uid") != policy["datasource"]["uid"]
    ]
    runbook_scenarios = {
        scenario
        for item in panels
        for scenario in scenario_coverage(item)
        if any(scenario in str(link_doc.get("url", "")) for link_doc in item.get("links", []))
    }
    config_map = policy["config_map"]
    checks = [
        {"name": "dashboard_uid", "ok": bool(dashboard.get("uid")), "evidence": {"uid": dashboard.get("uid")}},
        {"name": "panel_count", "ok": len(panels) >= 6, "evidence": {"panel_count": len(panels)}},
        {
            "name": "scenario_coverage",
            "ok": observed_scenarios >= required_scenarios,
            "evidence": {"observed": sorted(observed_scenarios), "required": sorted(required_scenarios)},
        },
        {
            "name": "panel_type_coverage",
            "ok": observed_panel_types >= required_panel_types,
            "evidence": {"observed": sorted(observed_panel_types), "required": sorted(required_panel_types)},
        },
        {
            "name": "prometheus_datasource",
            "ok": not missing_datasource,
            "evidence": {"missing_datasource_panels": sorted(set(str(item) for item in missing_datasource))},
        },
        {
            "name": "runbook_links",
            "ok": runbook_scenarios >= required_scenarios,
            "evidence": {"linked_scenarios": sorted(runbook_scenarios)},
        },
        {
            "name": "config_map_manifest",
            "ok": "kind: ConfigMap" in config_map_manifest
            and config_map["dashboard_key"] in config_map_manifest
            and "grafana_dashboard" in config_map_manifest,
            "evidence": {"config_map": config_map["name"], "dashboard_key": config_map["dashboard_key"]},
        },
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "panel_count": len(panels),
        "failed_count": sum(1 for item in checks if not item["ok"]),
        "scenarios": sorted(observed_scenarios),
        "panel_types": sorted(observed_panel_types),
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.joinpath("grafana-dashboard.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], dashboard: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Grafana Dashboard Evidence",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This generated dashboard is dashboard-as-code evidence for the lab. It",
        "ties SLO scenarios to Prometheus queries, runbook links, and alerting",
        "context so reviewers can inspect the operational surface without",
        "manually designing panels.",
        "",
        "## Panels",
        "",
        "| Panel | Type | Scenarios |",
        "| --- | --- | --- |",
    ]
    for item in dashboard.get("panels", []):
        lines.append(
            f"| `{item['title']}` | `{item['type']}` | {', '.join(sorted(scenario_coverage(item)))} |"
        )
    lines.extend(["", "## Audit Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    output_dir.joinpath("grafana-dashboard.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slo-config", default="config/reliability-slo.json")
    parser.add_argument("--alert-policy", default="config/alerting-policy.json")
    parser.add_argument("--dashboard-policy", default="config/dashboard-policy.json")
    parser.add_argument("--output-dir", default="out/grafana-dashboard")
    parser.add_argument("--dashboard", default="dashboards/grafana/gke-ai-inference-reliability.json")
    parser.add_argument("--config-map", default="k8s/gke/grafana-dashboard-configmap.yaml")
    args = parser.parse_args()

    slo_config = reliability_gate.load_slo_config(Path(args.slo_config))
    alert_policy = alerting_rules.load_json(Path(args.alert_policy))
    dashboard_policy = load_json(Path(args.dashboard_policy))
    dashboard = build_dashboard(slo_config, alert_policy, dashboard_policy)
    config_map_manifest = render_config_map(dashboard, dashboard_policy)
    report = evaluate(dashboard, dashboard_policy, config_map_manifest)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, dashboard, output_dir)

    dashboard_path = Path(args.dashboard)
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(json.dumps(dashboard, indent=2) + "\n", encoding="utf-8")

    config_map_path = Path(args.config_map)
    config_map_path.parent.mkdir(parents=True, exist_ok=True)
    config_map_path.write_text(config_map_manifest, encoding="utf-8")

    print(f"wrote {output_dir / 'grafana-dashboard.json'}")
    print(f"wrote {output_dir / 'grafana-dashboard.md'}")
    print(f"wrote {dashboard_path}")
    print(f"wrote {config_map_path}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
