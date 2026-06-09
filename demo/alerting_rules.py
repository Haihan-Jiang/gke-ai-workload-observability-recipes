#!/usr/bin/env python3
"""Generate SLO alerting rules and audit their operational metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo import reliability_gate


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def seconds(milliseconds: int | float) -> float:
    return round(float(milliseconds) / 1000.0, 3)


def service_selector(policy: dict[str, Any], extra: dict[str, str] | None = None) -> str:
    service = policy["service"]
    labels = {
        "service_name": service["name"],
        "k8s_namespace_name": service["namespace"],
    }
    if extra:
        labels.update(extra)
    return ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))


def annotation(policy: dict[str, Any], scenario: str, summary: str, description: str) -> dict[str, str]:
    return {
        "summary": summary,
        "description": description,
        "runbook_url": f"{policy['runbook_base_url']}#{scenario}",
        "dashboard_hint": policy["dashboard_hint"],
    }


def alert(
    *,
    name: str,
    scenario: str,
    severity: str,
    duration: str,
    expression: str,
    policy: dict[str, Any],
    summary: str,
    description: str,
) -> dict[str, Any]:
    service = policy["service"]
    return {
        "alert": name,
        "expr": expression,
        "for": duration,
        "labels": {
            "severity": severity,
            "team": service["team"],
            "service": service["name"],
            "scenario": scenario,
        },
        "annotations": annotation(policy, scenario, summary, description),
    }


def build_alerts(slo_config: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    scenarios = slo_config["scenarios"]
    baseline = reliability_gate.scenario_slo(slo_config, "baseline")
    cache = reliability_gate.scenario_slo(slo_config, "cache_miss_storm")
    dependency = reliability_gate.scenario_slo(slo_config, "dependency_timeout")
    rollout = reliability_gate.scenario_slo(slo_config, "rollout_regression")
    collector = reliability_gate.scenario_slo(slo_config, "collector_queue_pressure")
    selector = service_selector(policy)
    rollout_selector = service_selector(policy, {"service_version": str(rollout["expected_service_version"])})
    alerts = [
        alert(
            name="GKEAIInferenceBaselineLatencySLOViolation",
            scenario="baseline",
            severity="page",
            duration="5m",
            expression=(
                "histogram_quantile(0.95, "
                f"sum by (le) (rate(http_server_duration_seconds_bucket{{{selector}}}[5m]))) "
                f"> {seconds(baseline['max_p95_ms'])}"
            ),
            policy=policy,
            summary="Baseline inference latency exceeded the control SLO.",
            description=(
                "Healthy baseline traffic should remain inside the configured p95 latency SLO. "
                "Treat this as a service-wide reliability page before comparing failure scenarios."
            ),
        ),
        alert(
            name="GKEAIInferenceCacheMissStorm",
            scenario="cache_miss_storm",
            severity="ticket",
            duration="10m",
            expression=(
                f"sum(rate(ai_inference_cache_requests_total{{{selector},cache_result=\"miss\"}}[5m])) "
                f"/ clamp_min(sum(rate(ai_inference_cache_requests_total{{{selector}}}[5m])), 1) "
                f"> {cache['min_cache_miss_rate']}"
            ),
            policy=policy,
            summary="Inference cache miss ratio crossed the storm threshold.",
            description=(
                "High cache misses explain latency without blaming model inference. "
                "Use the cache miss runbook before scaling the serving deployment."
            ),
        ),
        alert(
            name="GKEAIInferenceDependencyErrorBudgetBurn",
            scenario="dependency_timeout",
            severity="page",
            duration="5m",
            expression=(
                f"sum(rate(http_server_duration_seconds_count{{{selector},http_response_status_code=~\"5..\"}}[5m])) "
                f"/ clamp_min(sum(rate(http_server_duration_seconds_count{{{selector}}}[5m])), 1) "
                f"> {dependency['min_error_rate']}"
            ),
            policy=policy,
            summary="Dependency-driven inference errors are burning budget.",
            description=(
                "Feature-store or dependency failures are creating material user-visible errors. "
                "Page the dependency owner instead of treating this as a pure autoscaling issue."
            ),
        ),
        alert(
            name="GKEAIInferenceRolloutVersionRegression",
            scenario="rollout_regression",
            severity="page",
            duration="5m",
            expression=(
                "histogram_quantile(0.95, "
                f"sum by (le) (rate(http_server_duration_seconds_bucket{{{rollout_selector}}}[5m]))) "
                f"> {seconds(rollout['min_p95_ms'])}"
            ),
            policy=policy,
            summary="Candidate service version is breaching latency SLO.",
            description=(
                "A version-specific latency regression should pause or rollback the rollout before more traffic shifts."
            ),
        ),
        alert(
            name="GKEAICollectorTelemetryLoss",
            scenario="collector_queue_pressure",
            severity="page",
            duration="5m",
            expression=(
                "sum(rate(otelcol_exporter_send_failed_spans_total[5m])) "
                "/ clamp_min("
                "sum(rate(otelcol_exporter_sent_spans_total[5m])) + "
                "sum(rate(otelcol_exporter_send_failed_spans_total[5m])), 1) "
                f"> {collector['min_telemetry_loss_rate']}"
            ),
            policy=policy,
            summary="Collector telemetry delivery loss crossed the release evidence threshold.",
            description=(
                "Application traffic can look healthy while telemetry is missing. "
                "Protect queue storage and exporter delivery before trusting dashboards."
            ),
        ),
    ]
    if set(scenarios) - {item["labels"]["scenario"] for item in alerts}:
        raise ValueError("alert coverage does not match configured SLO scenarios")
    return alerts


def yaml_quote(value: str) -> str:
    return json.dumps(value)


def render_prometheus_rule(alerts: list[dict[str, Any]], policy: dict[str, Any]) -> str:
    rule_config = policy["prometheus_rule"]
    lines = [
        "apiVersion: monitoring.coreos.com/v1",
        "kind: PrometheusRule",
        "metadata:",
        f"  name: {rule_config['name']}",
        f"  namespace: {rule_config['namespace']}",
        "  labels:",
        "    app.kubernetes.io/name: gke-ai-inference-alerts",
        "    app.kubernetes.io/part-of: gke-ai-inference-reliability-lab",
        "spec:",
        "  groups:",
        f"    - name: {rule_config['group']}",
        "      rules:",
    ]
    for item in alerts:
        lines.extend(
            [
                f"        - alert: {item['alert']}",
                "          expr: |",
            ]
        )
        lines.extend([f"            {line}" for line in item["expr"].splitlines()])
        lines.extend(
            [
                f"          for: {item['for']}",
                "          labels:",
            ]
        )
        for key, value in item["labels"].items():
            lines.append(f"            {key}: {yaml_quote(str(value))}")
        lines.append("          annotations:")
        for key, value in item["annotations"].items():
            lines.append(f"            {key}: {yaml_quote(str(value))}")
    lines.append("")
    return "\n".join(lines)


def evaluate(alerts: list[dict[str, Any]], policy: dict[str, Any], manifest: str) -> dict[str, Any]:
    required_labels = set(policy.get("required_labels", []))
    required_annotations = set(policy.get("required_annotations", []))
    checks = []
    names = [item["alert"] for item in alerts]
    scenarios = [item["labels"].get("scenario") for item in alerts]
    checks.append(
        {
            "name": "alert_count",
            "ok": len(alerts) >= 5,
            "evidence": {"alert_count": len(alerts)},
        }
    )
    checks.append(
        {
            "name": "unique_alert_names",
            "ok": len(names) == len(set(names)),
            "evidence": {"names": names},
        }
    )
    checks.append(
        {
            "name": "scenario_coverage",
            "ok": set(scenarios) >= set(policy.get("scenario_coverage", scenarios)),
            "evidence": {"scenarios": sorted(set(str(item) for item in scenarios))},
        }
    )
    missing_labels = {
        item["alert"]: sorted(required_labels - set(item.get("labels", {})))
        for item in alerts
        if required_labels - set(item.get("labels", {}))
    }
    checks.append(
        {
            "name": "required_labels",
            "ok": not missing_labels,
            "evidence": {"missing": missing_labels},
        }
    )
    missing_annotations = {
        item["alert"]: sorted(required_annotations - set(item.get("annotations", {})))
        for item in alerts
        if required_annotations - set(item.get("annotations", {}))
    }
    checks.append(
        {
            "name": "required_annotations",
            "ok": not missing_annotations,
            "evidence": {"missing": missing_annotations},
        }
    )
    checks.append(
        {
            "name": "page_alerts_present",
            "ok": sum(1 for item in alerts if item["labels"].get("severity") == "page") >= 3,
            "evidence": {
                "page_alerts": [
                    item["alert"]
                    for item in alerts
                    if item["labels"].get("severity") == "page"
                ]
            },
        }
    )
    checks.append(
        {
            "name": "prometheus_rule_manifest",
            "ok": "kind: PrometheusRule" in manifest and "apiVersion: monitoring.coreos.com/v1" in manifest,
            "evidence": {"kind": "PrometheusRule"},
        }
    )
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "rule_count": len(alerts),
        "failed_count": sum(1 for item in checks if not item["ok"]),
        "checks": checks,
        "alerts": alerts,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "alerting-rules.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# SLO Alerting Rules",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "These generated alert rules connect replay evidence to operations. The",
        "rules preserve scenario ownership, severity, runbook links, and dashboard",
        "hints so a release gate can become a page or ticket with enough context",
        "for first response.",
        "",
        "## Alerts",
        "",
        "| Alert | Scenario | Severity | For |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["alerts"]:
        labels = item["labels"]
        lines.append(
            f"| `{item['alert']}` | `{labels['scenario']}` | `{labels['severity']}` | `{item['for']}` |"
        )
    lines.extend(["", "## Audit Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    output_dir.joinpath("alerting-rules.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slo-config", default="config/reliability-slo.json")
    parser.add_argument("--policy", default="config/alerting-policy.json")
    parser.add_argument("--output-dir", default="out/alerting-rules")
    parser.add_argument("--manifest", default="k8s/gke/alerting-rules.yaml")
    args = parser.parse_args()

    slo_config = reliability_gate.load_slo_config(Path(args.slo_config))
    policy = load_json(Path(args.policy))
    alerts = build_alerts(slo_config, policy)
    manifest = render_prometheus_rule(alerts, policy)
    report = evaluate(alerts, policy, manifest)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest, encoding="utf-8")
    print(f"wrote {output_dir / 'alerting-rules.json'}")
    print(f"wrote {output_dir / 'alerting-rules.md'}")
    print(f"wrote {manifest_path}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
