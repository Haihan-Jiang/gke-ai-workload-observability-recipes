#!/usr/bin/env python3
"""Generate detailed reliability evidence from replay summaries and OTLP payloads."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from demo.advanced_reliability import iter_payloads, otlp_attrs
except ModuleNotFoundError:
    from advanced_reliability import iter_payloads, otlp_attrs


DETAILED_PROBLEMS = [
    {
        "id": "C06",
        "name": "Critical-path span attribution",
        "risk": "Root latency is not actionable unless the dominant child span is identified.",
        "artifact": "critical-path-attribution.md",
    },
    {
        "id": "C07",
        "name": "Tail-sampling evidence coverage",
        "risk": "Incident traces can be sampled away even when aggregate metrics show a problem.",
        "artifact": "evidence-coverage.md",
    },
    {
        "id": "C08",
        "name": "Autoscaler lag and cold-start recovery",
        "risk": "A capacity plan can look adequate while scale-up latency still misses the incident window.",
        "artifact": "hpa-lag-analysis.md",
    },
    {
        "id": "C09",
        "name": "Tenant blast-radius detection",
        "risk": "A premium tenant can be impacted while aggregate service health looks only moderately degraded.",
        "artifact": "tenant-blast-radius.md",
    },
    {
        "id": "C10",
        "name": "Token and GPU cost guardrail",
        "risk": "Long prompts and expensive model variants can create reliability and cost regressions together.",
        "artifact": "token-cost-guard.md",
    },
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def summary_by_name(summary: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["scenario"]): item for item in summary}


def build_critical_path(payload_dir: Path, detailed_config: dict[str, Any]) -> dict[str, Any]:
    config = detailed_config["critical_path"]
    tracked = set(config["tracked_child_spans"])
    scenario_totals: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

    for payload in iter_payloads(payload_dir):
        for resource_span in payload.get("resourceSpans", []):
            resource_attrs = otlp_attrs(resource_span.get("resource", {}).get("attributes", []))
            scenario = str(resource_attrs.get("incident.scenario", payload["_source_path"].replace(".otlp.json", "")))
            for scope_span in resource_span.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    name = str(span.get("name"))
                    if name not in tracked:
                        continue
                    duration_ms = (
                        int(span["endTimeUnixNano"]) - int(span["startTimeUnixNano"])
                    ) // 1_000_000
                    scenario_totals[scenario][name].append(duration_ms)

    scenarios = []
    for scenario, spans in sorted(scenario_totals.items()):
        averages = {
            name: round(sum(values) / len(values), 2)
            for name, values in spans.items()
        }
        total = sum(averages.values())
        dominant_span = max(averages, key=averages.get)
        dominance_ratio = round(averages[dominant_span] / max(1, total), 3)
        scenarios.append(
            {
                "scenario": scenario,
                "average_child_span_ms": averages,
                "dominant_span": dominant_span,
                "dominance_ratio": dominance_ratio,
                "actionable": dominance_ratio >= float(config["dominance_ratio_threshold"]),
            }
        )
    return {"problem_id": "C06", "scenarios": scenarios}


def build_evidence_coverage(
    summary: list[dict[str, Any]],
    payload_dir: Path,
    detailed_config: dict[str, Any],
) -> dict[str, Any]:
    config = detailed_config["evidence_coverage"]
    root_counts: dict[str, int] = defaultdict(int)
    tail_reasons: dict[str, set[str]] = defaultdict(set)
    summary_map = summary_by_name(summary)

    for payload in iter_payloads(payload_dir):
        for resource_span in payload.get("resourceSpans", []):
            resource_attrs = otlp_attrs(resource_span.get("resource", {}).get("attributes", []))
            scenario = str(resource_attrs.get("incident.scenario", payload["_source_path"].replace(".otlp.json", "")))
            for scope_span in resource_span.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    if span.get("name") != "POST /v1/infer":
                        continue
                    root_counts[scenario] += 1
                    attrs = otlp_attrs(span.get("attributes", []))
                    status = span.get("status", {}).get("code")
                    if status == "STATUS_CODE_ERROR" or int(attrs.get("http.status_code", 200)) >= 500:
                        tail_reasons[scenario].add("error")
                    if int(attrs.get("ai.inference.latency_ms", 0)) >= int(config["high_latency_ms"]):
                        tail_reasons[scenario].add("high_latency")
                    if float(attrs.get("telemetry.loss_rate", 0.0)) >= float(config["telemetry_loss_threshold"]):
                        tail_reasons[scenario].add("telemetry_loss")

    scenarios = []
    for scenario, item in sorted(summary_map.items()):
        reasons = sorted(tail_reasons.get(scenario, set()))
        expected = []
        if float(item["error_rate"]) > 0:
            expected.append("error")
        if int(item["p95_ms"]) >= int(config["high_latency_ms"]):
            expected.append("high_latency")
        if float(item["telemetry_loss_rate"]) >= float(config["telemetry_loss_threshold"]):
            expected.append("telemetry_loss")
        count_ok = root_counts[scenario] >= int(config["min_root_spans_per_scenario"])
        reasons_ok = set(expected).issubset(reasons)
        scenarios.append(
            {
                "scenario": scenario,
                "root_spans": root_counts[scenario],
                "expected_tail_reasons": expected,
                "observed_tail_reasons": reasons,
                "coverage_ok": count_ok and reasons_ok,
            }
        )
    return {
        "problem_id": "C07",
        "status": "pass" if all(item["coverage_ok"] for item in scenarios) else "fail",
        "scenarios": scenarios,
    }


def build_hpa_lag(summary: list[dict[str, Any]], detailed_config: dict[str, Any]) -> dict[str, Any]:
    config = detailed_config["hpa_lag"]
    rows = []
    for item in summary:
        p95_ms = max(1, int(item["p95_ms"]))
        per_replica_rps = (int(config["concurrency_per_replica"]) * 1000) / p95_ms
        required_replicas = max(1, math.ceil(float(config["target_rps"]) / per_replica_rps))
        missing_replicas = max(0, required_replicas - int(config["current_replicas"]))
        scale_minutes = math.ceil(missing_replicas / max(1, int(config["max_scale_up_replicas_per_minute"])))
        recovery_seconds = scale_minutes * 60 + (int(config["cold_start_seconds"]) if missing_replicas else 0)
        scalable = float(item["error_rate"]) <= float(config["non_scalable_error_rate"])
        rows.append(
            {
                "scenario": item["scenario"],
                "required_replicas": required_replicas,
                "missing_replicas": missing_replicas,
                "estimated_recovery_seconds": recovery_seconds,
                "scalable": scalable,
                "decision": (
                    "steady_state"
                    if missing_replicas == 0
                    else "scale"
                    if scalable and recovery_seconds <= int(config["max_recovery_seconds"])
                    else "fix_dependency_or_rollout"
                    if not scalable
                    else "pre_scale_or_raise_hpa_budget"
                ),
            }
        )
    return {"problem_id": "C08", "scenarios": rows}


def build_tenant_blast_radius(summary: list[dict[str, Any]], detailed_config: dict[str, Any]) -> dict[str, Any]:
    config = detailed_config["tenant_blast_radius"]["tiers"]
    rows = []
    for item in summary:
        tier = str(item["tenant_tier"])
        tier_slo = config[tier]
        violations = []
        if int(item["p95_ms"]) > int(tier_slo["max_p95_ms"]):
            violations.append(f"p95 {item['p95_ms']}ms exceeds {tier_slo['max_p95_ms']}ms")
        if float(item["error_rate"]) > float(tier_slo["max_error_rate"]):
            violations.append(f"error rate {item['error_rate']} exceeds {tier_slo['max_error_rate']}")
        if float(item["telemetry_loss_rate"]) > float(tier_slo["max_telemetry_loss_rate"]):
            violations.append(
                f"telemetry loss {item['telemetry_loss_rate']} exceeds {tier_slo['max_telemetry_loss_rate']}"
            )
        rows.append(
            {
                "scenario": item["scenario"],
                "tenant_tier": tier,
                "violations": violations,
                "blast_radius": "tenant_slo_breach" if violations else "contained",
            }
        )
    return {
        "problem_id": "C09",
        "breached_scenarios": [item["scenario"] for item in rows if item["violations"]],
        "scenarios": rows,
    }


def build_token_cost_guard(summary: list[dict[str, Any]], detailed_config: dict[str, Any]) -> dict[str, Any]:
    config = detailed_config["token_cost_guard"]
    rows = []
    for item in summary:
        total_tokens = int(item["input_tokens"]) + int(item["output_tokens"])
        cost_per_request = (
            int(item["input_tokens"]) / 1000 * float(config["input_token_cost_per_1k"])
            + int(item["output_tokens"]) / 1000 * float(config["output_token_cost_per_1k"])
        )
        cost_per_1k = round(cost_per_request * 1000, 4)
        violations = []
        if total_tokens > int(config["max_total_tokens_per_request"]):
            violations.append(f"tokens {total_tokens} exceed {config['max_total_tokens_per_request']}")
        if int(item["gpu_ms"]) > int(config["max_gpu_ms_per_request"]):
            violations.append(f"gpu_ms {item['gpu_ms']} exceeds {config['max_gpu_ms_per_request']}")
        if cost_per_1k > float(config["max_cost_per_1k_requests"]):
            violations.append(f"cost_per_1k {cost_per_1k} exceeds {config['max_cost_per_1k_requests']}")
        rows.append(
            {
                "scenario": item["scenario"],
                "model_variant": item["model_variant"],
                "total_tokens": total_tokens,
                "gpu_ms": item["gpu_ms"],
                "estimated_cost_per_1k_requests": cost_per_1k,
                "violations": violations,
                "decision": "block_or_review" if violations else "allow",
            }
        )
    return {"problem_id": "C10", "scenarios": rows}


def write_report(name: str, report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{name}.md").write_text(render_markdown(name, report), encoding="utf-8")


def render_markdown(name: str, report: dict[str, Any]) -> str:
    title = {
        "critical-path-attribution": "Critical Path Attribution",
        "evidence-coverage": "Evidence Coverage",
        "hpa-lag-analysis": "HPA Lag Analysis",
        "tenant-blast-radius": "Tenant Blast Radius",
        "token-cost-guard": "Token Cost Guard",
        "detailed-problems": "Detailed Problem Coverage",
    }[name]
    lines = ["# " + title, ""]
    if name == "critical-path-attribution":
        lines.extend(["| Scenario | Dominant span | Dominance | Actionable |", "| --- | --- | ---: | --- |"])
        for item in report["scenarios"]:
            lines.append(
                f"| `{item['scenario']}` | `{item['dominant_span']}` | {item['dominance_ratio']} | {item['actionable']} |"
            )
    elif name == "evidence-coverage":
        lines.extend(["| Scenario | Root spans | Expected reasons | Observed reasons | Status |", "| --- | ---: | --- | --- | --- |"])
        for item in report["scenarios"]:
            lines.append(
                f"| `{item['scenario']}` | {item['root_spans']} | {', '.join(item['expected_tail_reasons']) or 'none'} | {', '.join(item['observed_tail_reasons']) or 'none'} | {'PASS' if item['coverage_ok'] else 'FAIL'} |"
            )
    elif name == "hpa-lag-analysis":
        lines.extend(["| Scenario | Required replicas | Missing | Recovery sec | Decision |", "| --- | ---: | ---: | ---: | --- |"])
        for item in report["scenarios"]:
            lines.append(
                f"| `{item['scenario']}` | {item['required_replicas']} | {item['missing_replicas']} | {item['estimated_recovery_seconds']} | `{item['decision']}` |"
            )
    elif name == "tenant-blast-radius":
        lines.extend(["| Scenario | Tenant tier | Blast radius | Violations |", "| --- | --- | --- | --- |"])
        for item in report["scenarios"]:
            lines.append(
                f"| `{item['scenario']}` | `{item['tenant_tier']}` | `{item['blast_radius']}` | {'; '.join(item['violations']) or 'none'} |"
            )
    elif name == "token-cost-guard":
        lines.extend(["| Scenario | Model variant | Tokens | GPU ms | Cost / 1k req | Decision |", "| --- | --- | ---: | ---: | ---: | --- |"])
        for item in report["scenarios"]:
            lines.append(
                f"| `{item['scenario']}` | `{item['model_variant']}` | {item['total_tokens']} | {item['gpu_ms']} | {item['estimated_cost_per_1k_requests']} | `{item['decision']}` |"
            )
    elif name == "detailed-problems":
        lines.extend(["| ID | Problem | Artifact |", "| --- | --- | --- |"])
        for item in report["problems"]:
            lines.append(f"| {item['id']} | {item['name']} | [{item['artifact']}]({item['artifact']}) |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--payload-dir", default="out/incident-replay-payloads")
    parser.add_argument("--detailed-config", default="config/detailed-reliability.json")
    parser.add_argument("--output-dir", default="out/detailed-reliability")
    args = parser.parse_args()

    summary = load_json(Path(args.summary))
    detailed_config = load_json(Path(args.detailed_config))
    payload_dir = Path(args.payload_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reports = {
        "critical-path-attribution": build_critical_path(payload_dir, detailed_config),
        "evidence-coverage": build_evidence_coverage(summary, payload_dir, detailed_config),
        "hpa-lag-analysis": build_hpa_lag(summary, detailed_config),
        "tenant-blast-radius": build_tenant_blast_radius(summary, detailed_config),
        "token-cost-guard": build_token_cost_guard(summary, detailed_config),
        "detailed-problems": {"problems": DETAILED_PROBLEMS},
    }
    for name, report in reports.items():
        write_report(name, report, output_dir)
    print(f"wrote detailed reliability evidence to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
