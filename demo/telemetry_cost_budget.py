#!/usr/bin/env python3
"""Estimate trace volume, sampling, and retention budget for replayed payloads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
GIB = 1024**3
SECONDS_PER_DAY = 86_400


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def span_count(payload: dict[str, Any]) -> int:
    return sum(
        len(scope_span.get("spans", []))
        for resource_span in payload.get("resourceSpans", [])
        for scope_span in resource_span.get("scopeSpans", [])
    )


def payload_metrics(summary: list[dict[str, Any]], payload_dir: Path) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for item in summary:
        scenario = str(item["scenario"])
        path = payload_dir / f"{scenario}.otlp.json"
        requests = int(item["requests"])
        payload = load_json(path)
        bytes_total = path.stat().st_size
        spans = span_count(payload)
        metrics.append(
            {
                "scenario": scenario,
                "requests": requests,
                "payload_bytes": bytes_total,
                "span_count": spans,
                "bytes_per_request": round(bytes_total / requests, 2),
                "spans_per_request": round(spans / requests, 2),
            }
        )
    return metrics


def weighted_bytes_per_request(metrics: list[dict[str, Any]], policy: dict[str, Any]) -> float:
    traffic_mix = policy.get("traffic_mix", {})
    sampling_rates = policy.get("sampling_rates", {})
    return sum(
        float(item["bytes_per_request"])
        * float(traffic_mix.get(item["scenario"], 0.0))
        * float(sampling_rates.get(item["scenario"], 0.0))
        for item in metrics
    )


def build_report(
    *,
    summary: list[dict[str, Any]],
    payload_dir: Path,
    policy: dict[str, Any],
) -> dict[str, Any]:
    metrics = payload_metrics(summary, payload_dir)
    scenarios = {item["scenario"] for item in metrics}
    traffic_mix = {str(k): float(v) for k, v in policy.get("traffic_mix", {}).items()}
    sampling_rates = {str(k): float(v) for k, v in policy.get("sampling_rates", {}).items()}
    weighted_bytes = weighted_bytes_per_request(metrics, policy)
    production_qps = float(policy["production_qps"])
    daily_ingest_gib = weighted_bytes * production_qps * SECONDS_PER_DAY / GIB
    retained_gib = daily_ingest_gib * int(policy["retention_days"])
    critical_scenarios = set(policy.get("critical_scenarios", []))
    traffic_mix_total = round(sum(traffic_mix.values()), 6)
    missing_mix = sorted(scenarios - set(traffic_mix))
    missing_sampling = sorted(scenarios - set(sampling_rates))
    incident_sample_gaps = sorted(
        scenario
        for scenario in scenarios
        if scenario != "baseline"
        and sampling_rates.get(scenario, 0.0) < float(policy["min_incident_sample_rate"])
    )
    critical_sample_gaps = sorted(
        scenario
        for scenario in critical_scenarios
        if sampling_rates.get(scenario, 0.0) < float(policy["min_critical_sample_rate"])
    )
    checks = [
        {
            "name": "payload_coverage",
            "ok": not missing_mix and not missing_sampling and len(metrics) >= 5,
            "evidence": {
                "scenarios": sorted(scenarios),
                "missing_traffic_mix": missing_mix,
                "missing_sampling_rates": missing_sampling,
            },
        },
        {
            "name": "span_budget",
            "ok": all(float(item["spans_per_request"]) <= float(policy["max_spans_per_request"]) for item in metrics),
            "evidence": {
                "max_allowed": policy["max_spans_per_request"],
                "max_observed": max(item["spans_per_request"] for item in metrics),
            },
        },
        {
            "name": "payload_size_budget",
            "ok": all(float(item["bytes_per_request"]) <= float(policy["max_payload_bytes_per_request"]) for item in metrics),
            "evidence": {
                "max_allowed": policy["max_payload_bytes_per_request"],
                "max_observed": max(item["bytes_per_request"] for item in metrics),
            },
        },
        {
            "name": "sampling_policy",
            "ok": traffic_mix_total == 1.0
            and sampling_rates.get("baseline", 1.0) <= float(policy["max_baseline_sample_rate"])
            and not incident_sample_gaps,
            "evidence": {
                "traffic_mix_total": traffic_mix_total,
                "baseline_sample_rate": sampling_rates.get("baseline"),
                "incident_sample_gaps": incident_sample_gaps,
            },
        },
        {
            "name": "critical_scenario_sampling",
            "ok": not critical_sample_gaps,
            "evidence": {
                "critical_scenarios": sorted(critical_scenarios),
                "critical_sample_gaps": critical_sample_gaps,
            },
        },
        {
            "name": "daily_ingest_budget",
            "ok": daily_ingest_gib <= float(policy["max_daily_ingest_gib"]),
            "evidence": {
                "daily_ingest_gib": round(daily_ingest_gib, 2),
                "max_daily_ingest_gib": policy["max_daily_ingest_gib"],
            },
        },
        {
            "name": "retention_budget",
            "ok": retained_gib <= float(policy["max_retained_gib"]),
            "evidence": {
                "retention_days": policy["retention_days"],
                "retained_gib": round(retained_gib, 2),
                "max_retained_gib": policy["max_retained_gib"],
            },
        },
    ]
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "scenario_count": len(metrics),
        "production_qps": production_qps,
        "weighted_bytes_per_request": round(weighted_bytes, 2),
        "daily_ingest_gib": round(daily_ingest_gib, 2),
        "retained_gib": round(retained_gib, 2),
        "failed_count": failed_count,
        "scenarios": metrics,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "telemetry-cost-budget.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Telemetry Cost Budget",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This budget estimates trace ingest and retention from the generated",
        "OTLP payloads. It keeps incident traces useful while checking that",
        "sampling, span volume, payload size, and retention assumptions stay",
        "inside a production-style telemetry budget.",
        "",
        "## Summary",
        "",
        f"- Production QPS: `{report['production_qps']}`",
        f"- Weighted bytes per request after sampling: `{report['weighted_bytes_per_request']}`",
        f"- Daily ingest: `{report['daily_ingest_gib']}` GiB",
        f"- Retained storage: `{report['retained_gib']}` GiB",
        "",
        "## Scenario Cost Inputs",
        "",
        "| Scenario | Requests | Spans/request | Bytes/request |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item in report["scenarios"]:
        lines.append(
            f"| `{item['scenario']}` | {item['requests']} | {item['spans_per_request']} | {item['bytes_per_request']} |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    (output_dir / "telemetry-cost-budget.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--payload-dir", default="out/incident-replay-payloads")
    parser.add_argument("--policy", default="config/telemetry-cost-policy.json")
    parser.add_argument("--output-dir", default="out/telemetry-cost-budget")
    args = parser.parse_args()

    report = build_report(
        summary=load_json(Path(args.summary)),
        payload_dir=Path(args.payload_dir),
        policy=load_json(Path(args.policy)),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'telemetry-cost-budget.json'}")
    print(f"wrote {output_dir / 'telemetry-cost-budget.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
