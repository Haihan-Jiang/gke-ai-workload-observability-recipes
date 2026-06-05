#!/usr/bin/env python3
"""Generate advanced reliability evidence from replay output and OTLP payloads."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


COMPLEX_PROBLEMS = [
    {
        "id": "C01",
        "name": "Multi-window SLO burn rate",
        "risk": "A single incident can consume error budget faster than aggregate monthly dashboards show.",
        "artifact": "burn-rate-analysis.md",
    },
    {
        "id": "C02",
        "name": "Automated canary rollback decision",
        "risk": "A bad model or service version can look acceptable in aggregate traffic until the rollout expands.",
        "artifact": "rollout-guard.md",
    },
    {
        "id": "C03",
        "name": "Trace completeness and cardinality audit",
        "risk": "Telemetry can exist but still be unusable because key attributes are missing or too high-cardinality.",
        "artifact": "trace-quality-audit.md",
    },
    {
        "id": "C04",
        "name": "Collector outage and queue resilience",
        "risk": "Collector/exporter backpressure can silently drop traces during the exact window an incident needs evidence.",
        "artifact": "collector-resilience.md",
    },
    {
        "id": "C05",
        "name": "Incident correlation and deduplication",
        "risk": "Latency, dependency, rollout, and telemetry symptoms create separate alerts for one operator-facing incident.",
        "artifact": "incident-correlation.md",
    },
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def summary_by_name(summary: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["scenario"]): item for item in summary}


def estimate_bad_rate(item: dict[str, Any], slo_config: dict[str, Any], advanced_config: dict[str, Any]) -> float:
    baseline_slo = slo_config["scenarios"]["baseline"]
    burn_config = advanced_config["burn_rate"]
    latency_breach = 1.0 if int(item["p95_ms"]) > int(baseline_slo["max_p95_ms"]) else 0.0
    return min(
        1.0,
        float(item["error_rate"])
        + latency_breach * float(burn_config["latency_breach_weight"])
        + float(item["telemetry_loss_rate"]) * float(burn_config["telemetry_loss_weight"]),
    )


def build_burn_rate(
    summary: list[dict[str, Any]],
    slo_config: dict[str, Any],
    advanced_config: dict[str, Any],
) -> dict[str, Any]:
    by_name = summary_by_name(summary)
    burn_config = advanced_config["burn_rate"]
    error_budget = float(burn_config["error_budget_percent"]) / 100
    windows = []
    for window in burn_config["windows"]:
        bad_events = 0.0
        contributions = []
        total_requests = int(window["total_requests"])
        for scenario_name, share in window["scenario_mix"].items():
            item = by_name[scenario_name]
            requests = total_requests * float(share)
            bad_rate = estimate_bad_rate(item, slo_config, advanced_config)
            scenario_bad_events = requests * bad_rate
            bad_events += scenario_bad_events
            contributions.append(
                {
                    "scenario": scenario_name,
                    "traffic_share": share,
                    "estimated_bad_rate": round(bad_rate, 4),
                    "estimated_bad_events": round(scenario_bad_events, 2),
                }
            )
        observed_bad_rate = bad_events / total_requests
        burn_rate = observed_bad_rate / error_budget
        if burn_rate >= float(burn_config["page_threshold"]):
            action = "page"
        elif burn_rate >= float(burn_config["ticket_threshold"]):
            action = "ticket"
        else:
            action = "observe"
        windows.append(
            {
                "window": window["name"],
                "total_requests": total_requests,
                "estimated_bad_events": round(bad_events, 2),
                "observed_bad_rate": round(observed_bad_rate, 4),
                "burn_rate": round(burn_rate, 2),
                "action": action,
                "contributions": contributions,
            }
        )
    return {
        "problem_id": "C01",
        "status": "generated",
        "error_budget_percent": burn_config["error_budget_percent"],
        "windows": windows,
    }


def build_rollout_guard(summary: list[dict[str, Any]], advanced_config: dict[str, Any]) -> dict[str, Any]:
    by_name = summary_by_name(summary)
    config = advanced_config["rollout_guard"]
    baseline = by_name[config["baseline"]]
    candidate = by_name[config["candidate"]]
    p95_ratio = round(int(candidate["p95_ms"]) / max(1, int(baseline["p95_ms"])), 2)
    error_rate_delta = round(float(candidate["error_rate"]) - float(baseline["error_rate"]), 4)
    cache_miss_delta = round(float(candidate["cache_miss_rate"]) - float(baseline["cache_miss_rate"]), 4)
    telemetry_loss_delta = round(float(candidate["telemetry_loss_rate"]) - float(baseline["telemetry_loss_rate"]), 4)
    violations = []
    if p95_ratio > float(config["max_p95_ratio"]):
        violations.append(f"p95 ratio {p95_ratio} exceeds {config['max_p95_ratio']}")
    if error_rate_delta > float(config["max_error_rate_delta"]):
        violations.append(f"error delta {error_rate_delta} exceeds {config['max_error_rate_delta']}")
    if cache_miss_delta > float(config["max_cache_miss_delta"]):
        violations.append(f"cache miss delta {cache_miss_delta} exceeds {config['max_cache_miss_delta']}")
    if telemetry_loss_delta > float(config["max_telemetry_loss_delta"]):
        violations.append(f"telemetry loss delta {telemetry_loss_delta} exceeds {config['max_telemetry_loss_delta']}")
    return {
        "problem_id": "C02",
        "baseline": baseline["scenario"],
        "candidate": candidate["scenario"],
        "candidate_version": candidate["service_version"],
        "p95_ratio": p95_ratio,
        "error_rate_delta": error_rate_delta,
        "cache_miss_delta": cache_miss_delta,
        "telemetry_loss_delta": telemetry_loss_delta,
        "violations": violations,
        "decision": "rollback" if violations else "promote",
    }


def otlp_attrs(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    decoded = {}
    for attr in attributes:
        value = attr.get("value", {})
        if "stringValue" in value:
            decoded[attr["key"]] = value["stringValue"]
        elif "intValue" in value:
            decoded[attr["key"]] = value["intValue"]
        elif "doubleValue" in value:
            decoded[attr["key"]] = value["doubleValue"]
        elif "boolValue" in value:
            decoded[attr["key"]] = value["boolValue"]
    return decoded


def iter_payloads(payload_dir: Path) -> list[dict[str, Any]]:
    payloads = []
    for path in sorted(payload_dir.glob("*.otlp.json")):
        payload = load_json(path)
        payload["_source_path"] = path.name
        payloads.append(payload)
    return payloads


def build_trace_quality(payload_dir: Path, advanced_config: dict[str, Any]) -> dict[str, Any]:
    config = advanced_config["trace_quality"]
    payloads = iter_payloads(payload_dir)
    resource_missing: dict[str, list[str]] = {}
    root_missing: dict[str, list[str]] = {}
    child_span_missing: dict[str, list[str]] = {}
    cardinality: dict[str, set[str]] = {name: set() for name in config["max_cardinality"]}
    trace_count = 0

    for payload in payloads:
        source = payload["_source_path"]
        for resource_span in payload.get("resourceSpans", []):
            resource_attrs = otlp_attrs(resource_span.get("resource", {}).get("attributes", []))
            missing = sorted(set(config["required_resource_attributes"]) - set(resource_attrs))
            if missing:
                resource_missing[source] = missing
            for scope_span in resource_span.get("scopeSpans", []):
                spans = scope_span.get("spans", [])
                names = {span.get("name") for span in spans}
                missing_child = sorted(set(config["required_child_spans"]) - names)
                if missing_child:
                    child_span_missing[source] = missing_child
                for span in spans:
                    trace_count += 1
                    attrs = otlp_attrs(span.get("attributes", []))
                    for key in cardinality:
                        if key in attrs:
                            cardinality[key].add(str(attrs[key]))
                    if span.get("name") == "POST /v1/infer":
                        missing_root = sorted(set(config["required_root_span_attributes"]) - set(attrs))
                        if missing_root:
                            root_missing.setdefault(source, missing_root)

    cardinality_report = {
        key: {
            "count": len(values),
            "limit": int(config["max_cardinality"][key]),
            "values": sorted(values),
            "ok": len(values) <= int(config["max_cardinality"][key]),
        }
        for key, values in cardinality.items()
    }
    ok = not resource_missing and not root_missing and not child_span_missing and all(
        item["ok"] for item in cardinality_report.values()
    )
    return {
        "problem_id": "C03",
        "status": "pass" if ok else "fail",
        "payloads": len(payloads),
        "spans": trace_count,
        "resource_missing": resource_missing,
        "root_missing": root_missing,
        "child_span_missing": child_span_missing,
        "cardinality": cardinality_report,
    }


def build_collector_resilience(advanced_config: dict[str, Any]) -> dict[str, Any]:
    config = advanced_config["collector_resilience"]
    outage_seconds = int(config["exporter_outage_minutes"]) * 60
    ingress_spans = int(config["ingress_rps"]) * int(config["spans_per_request"]) * outage_seconds
    queue_capacity = int(config["queue_capacity_spans"])
    needed_mib = (
        ingress_spans
        * int(config["avg_span_bytes"])
        * float(config["headroom_factor"])
        / (1024 * 1024)
    )
    storage_mib = float(config["persistent_storage_mib"])
    lost_spans = max(0, ingress_spans - queue_capacity)
    risk = "ok"
    if lost_spans > 0 or needed_mib > storage_mib:
        risk = "data_loss"
    return {
        "problem_id": "C04",
        "ingress_spans_during_outage": ingress_spans,
        "queue_capacity_spans": queue_capacity,
        "queue_utilization": round(ingress_spans / max(1, queue_capacity), 3),
        "required_storage_mib": math.ceil(needed_mib),
        "configured_storage_mib": storage_mib,
        "estimated_lost_spans": lost_spans,
        "risk": risk,
        "recommendation": (
            "queue and storage are sufficient for the modeled outage"
            if risk == "ok"
            else "increase queue capacity or persistent queue storage before production use"
        ),
    }


def build_incident_correlation(
    summary: list[dict[str, Any]],
    slo_config: dict[str, Any],
    advanced_config: dict[str, Any],
) -> dict[str, Any]:
    baseline_slo = slo_config["scenarios"]["baseline"]
    incidents = []
    for item in summary:
        symptoms = []
        if int(item["p95_ms"]) > int(baseline_slo["max_p95_ms"]):
            symptoms.append("latency")
        if float(item["error_rate"]) > 0:
            symptoms.append("errors")
        if float(item["cache_miss_rate"]) > float(baseline_slo["max_cache_miss_rate"]):
            symptoms.append("cache_miss")
        if float(item["telemetry_loss_rate"]) > 0:
            symptoms.append("telemetry_loss")
        if str(item["service_version"]) != "v1":
            symptoms.append("new_version")
        if not symptoms:
            continue
        if "telemetry_loss" in symptoms and "errors" not in symptoms:
            root_cause = "telemetry_delivery"
        elif "new_version" in symptoms and "errors" in symptoms:
            root_cause = "rollout_regression"
        elif "errors" in symptoms:
            root_cause = "dependency_timeout"
        elif "cache_miss" in symptoms:
            root_cause = "cache_miss_storm"
        else:
            root_cause = "capacity_pressure"
        incidents.append(
            {
                "scenario": item["scenario"],
                "root_cause": root_cause,
                "dedupe_key": f"{root_cause}:{item['service_version']}",
                "symptoms": symptoms,
                "owner_hint": owner_for_root_cause(root_cause),
            }
        )
    return {
        "problem_id": "C05",
        "dedupe_window_minutes": advanced_config["incident_correlation"]["dedupe_window_minutes"],
        "incident_count": len(incidents),
        "unique_dedupe_keys": sorted({item["dedupe_key"] for item in incidents}),
        "incidents": incidents,
    }


def owner_for_root_cause(root_cause: str) -> str:
    return {
        "telemetry_delivery": "observability platform",
        "rollout_regression": "service owner / release engineer",
        "dependency_timeout": "feature platform / dependency owner",
        "cache_miss_storm": "inference retrieval owner",
        "capacity_pressure": "SRE / platform",
    }.get(root_cause, "SRE / platform")


def write_report(name: str, report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{name}.md").write_text(render_markdown(name, report), encoding="utf-8")


def render_markdown(name: str, report: dict[str, Any]) -> str:
    title = {
        "burn-rate-analysis": "Burn Rate Analysis",
        "rollout-guard": "Rollout Guard",
        "trace-quality-audit": "Trace Quality Audit",
        "collector-resilience": "Collector Resilience",
        "incident-correlation": "Incident Correlation",
        "complex-problems": "Complex Problem Coverage",
    }[name]
    lines = ["# " + title, ""]
    if name == "burn-rate-analysis":
        lines.extend(["| Window | Bad events | Bad rate | Burn rate | Action |", "| --- | ---: | ---: | ---: | --- |"])
        for item in report["windows"]:
            lines.append(
                f"| {item['window']} | {item['estimated_bad_events']} | {item['observed_bad_rate']} | {item['burn_rate']} | {item['action']} |"
            )
    elif name == "rollout-guard":
        lines.extend(
            [
                f"- Baseline: `{report['baseline']}`",
                f"- Candidate: `{report['candidate']}` / `{report['candidate_version']}`",
                f"- p95 ratio: `{report['p95_ratio']}`",
                f"- error rate delta: `{report['error_rate_delta']}`",
                f"- decision: **{report['decision'].upper()}**",
                "",
                "Violations:",
            ]
        )
        lines.extend([f"- {item}" for item in report["violations"]] or ["- none"])
    elif name == "trace-quality-audit":
        lines.extend(
            [
                f"- Status: **{str(report['status']).upper()}**",
                f"- Payloads audited: `{report['payloads']}`",
                f"- Spans audited: `{report['spans']}`",
                "",
                "| Attribute | Cardinality | Limit | Status |",
                "| --- | ---: | ---: | --- |",
            ]
        )
        for key, value in report["cardinality"].items():
            lines.append(f"| `{key}` | {value['count']} | {value['limit']} | {'PASS' if value['ok'] else 'FAIL'} |")
    elif name == "collector-resilience":
        lines.extend(
            [
                f"- Risk: **{str(report['risk']).upper()}**",
                f"- Ingress spans during outage: `{report['ingress_spans_during_outage']}`",
                f"- Queue capacity: `{report['queue_capacity_spans']}`",
                f"- Queue utilization: `{report['queue_utilization']}`",
                f"- Required storage MiB: `{report['required_storage_mib']}`",
                f"- Configured storage MiB: `{report['configured_storage_mib']}`",
                f"- Estimated lost spans: `{report['estimated_lost_spans']}`",
                f"- Recommendation: {report['recommendation']}",
            ]
        )
    elif name == "incident-correlation":
        lines.extend(["| Scenario | Root cause | Dedupe key | Owner | Symptoms |", "| --- | --- | --- | --- | --- |"])
        for item in report["incidents"]:
            lines.append(
                f"| `{item['scenario']}` | `{item['root_cause']}` | `{item['dedupe_key']}` | {item['owner_hint']} | {', '.join(item['symptoms'])} |"
            )
    elif name == "complex-problems":
        lines.extend(["| ID | Problem | Artifact |", "| --- | --- | --- |"])
        for item in report["problems"]:
            lines.append(f"| {item['id']} | {item['name']} | [{item['artifact']}]({item['artifact']}) |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--payload-dir", default="out/incident-replay-payloads")
    parser.add_argument("--slo-config", default="config/reliability-slo.json")
    parser.add_argument("--advanced-config", default="config/advanced-reliability.json")
    parser.add_argument("--output-dir", default="out/advanced-reliability")
    args = parser.parse_args()

    summary = load_json(Path(args.summary))
    slo_config = load_json(Path(args.slo_config))
    advanced_config = load_json(Path(args.advanced_config))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reports = {
        "burn-rate-analysis": build_burn_rate(summary, slo_config, advanced_config),
        "rollout-guard": build_rollout_guard(summary, advanced_config),
        "trace-quality-audit": build_trace_quality(Path(args.payload_dir), advanced_config),
        "collector-resilience": build_collector_resilience(advanced_config),
        "incident-correlation": build_incident_correlation(summary, slo_config, advanced_config),
        "complex-problems": {"problems": COMPLEX_PROBLEMS},
    }
    for name, report in reports.items():
        write_report(name, report, output_dir)
    print(f"wrote advanced reliability evidence to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
