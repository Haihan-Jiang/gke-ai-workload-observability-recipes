#!/usr/bin/env python3
"""Audit incident replay summary and OTLP payload contracts."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "replay-source-contract-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def otlp_value(value: dict[str, Any]) -> Any:
    if "stringValue" in value:
        return value["stringValue"]
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "boolValue" in value:
        return bool(value["boolValue"])
    return None


def attribute(key: str, value: str | int | float | bool) -> dict[str, Any]:
    if isinstance(value, bool):
        encoded: dict[str, Any] = {"boolValue": value}
    elif isinstance(value, int):
        encoded = {"intValue": value}
    elif isinstance(value, float):
        encoded = {"doubleValue": value}
    else:
        encoded = {"stringValue": value}
    return {"key": key, "value": encoded}


def attr_values(attributes: list[dict[str, Any]]) -> dict[str, list[Any]]:
    values: dict[str, list[Any]] = {}
    for item in attributes:
        key = str(item.get("key", ""))
        values.setdefault(key, []).append(otlp_value(dict(item.get("value", {}))))
    return values


def first_attr(attributes: list[dict[str, Any]], key: str) -> Any:
    values = attr_values(attributes).get(key, [])
    return values[0] if values else None


def spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for resource_span in payload.get("resourceSpans", []):
        for scope_span in resource_span.get("scopeSpans", []):
            result.extend(scope_span.get("spans", []))
    return result


def root_spans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [span for span in spans(payload) if not span.get("parentSpanId")]


def resource_attrs(payload: dict[str, Any]) -> dict[str, list[Any]]:
    values: dict[str, list[Any]] = {}
    for resource_span in payload.get("resourceSpans", []):
        for key, observed in attr_values(resource_span.get("resource", {}).get("attributes", [])).items():
            values.setdefault(key, []).extend(observed)
    return values


def load_payloads(payload_dir: Path, expected_scenarios: list[str]) -> dict[str, dict[str, Any] | None]:
    payloads: dict[str, dict[str, Any] | None] = {}
    for scenario in expected_scenarios:
        path = payload_dir / f"{scenario}.otlp.json"
        payloads[scenario] = load_json(path) if path.exists() else None
    return payloads


def summary_by_scenario(summary: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("scenario", "")): item for item in summary}


def evaluate(summary: list[dict[str, Any]], payloads: dict[str, dict[str, Any] | None], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected = [str(item) for item in policy.get("expected_scenarios", [])]
    summary_names = [str(item.get("scenario", "")) for item in summary]
    summary_map = summary_by_scenario(summary)
    duplicates = sorted({name for name in summary_names if summary_names.count(name) > 1})
    missing_summary = sorted(set(expected) - set(summary_names))
    unexpected_summary = sorted(set(summary_names) - set(expected))
    present_payloads = {name: payload for name, payload in payloads.items() if payload is not None}
    missing_payloads = sorted(set(expected) - set(present_payloads))

    required_fields = [str(field) for field in policy.get("required_summary_fields", [])]
    summary_gaps = []
    metric_gaps = []
    total_requests = 0
    for scenario in expected:
        item = summary_map.get(scenario)
        if item is None:
            continue
        missing_fields = [field for field in required_fields if field not in item]
        if missing_fields:
            summary_gaps.append({"scenario": scenario, "missing_fields": missing_fields})
        requests = int(item.get("requests", 0))
        errors = int(item.get("errors", 0))
        p50 = int(item.get("p50_ms", 0))
        p95 = int(item.get("p95_ms", 0))
        total_requests += requests
        expected_error_rate = round(errors / requests, 2) if requests else None
        if requests <= 0 or errors < 0 or errors > requests or p50 <= 0 or p95 < p50:
            metric_gaps.append({"scenario": scenario, "reason": "invalid_latency_or_error_metrics"})
        if expected_error_rate is None or float(item.get("error_rate", -1.0)) != expected_error_rate:
            metric_gaps.append({"scenario": scenario, "reason": "error_rate_mismatch"})

    required_root_attrs = set(str(item) for item in policy.get("required_root_attributes", []))
    required_child_spans = set(str(item) for item in policy.get("required_child_spans", []))
    forbidden_attrs = set(str(item) for item in policy.get("forbidden_attribute_keys", []))
    root_span_count = 0
    total_span_count = 0
    attribute_keys: set[str] = set()
    root_attr_gaps = []
    trace_shape_gaps = []
    consistency_gaps = []
    forbidden_gaps = []

    for scenario in expected:
        payload = present_payloads.get(scenario)
        summary_item = summary_map.get(scenario, {})
        if payload is None:
            continue
        payload_spans = spans(payload)
        payload_roots = root_spans(payload)
        root_span_count += len(payload_roots)
        total_span_count += len(payload_spans)
        child_names = {str(span.get("name", "")) for span in payload_spans if span.get("parentSpanId")}
        if not required_child_spans <= child_names:
            trace_shape_gaps.append(
                {
                    "scenario": scenario,
                    "missing_child_spans": sorted(required_child_spans - child_names),
                }
            )
        if len(payload_roots) != int(summary_item.get("requests", -1)):
            trace_shape_gaps.append(
                {
                    "scenario": scenario,
                    "root_span_count": len(payload_roots),
                    "summary_requests": summary_item.get("requests"),
                }
            )
        resource_values = resource_attrs(payload)
        if scenario not in set(str(value) for value in resource_values.get("incident.scenario", [])):
            consistency_gaps.append({"scenario": scenario, "reason": "resource_scenario_mismatch"})
        for span_item in payload_spans:
            span_attrs = attr_values(span_item.get("attributes", []))
            attribute_keys.update(span_attrs)
            forbidden = sorted(forbidden_attrs & set(span_attrs))
            if forbidden:
                forbidden_gaps.append(
                    {
                        "scenario": scenario,
                        "span": span_item.get("name"),
                        "forbidden_attributes": forbidden,
                    }
                )
        for root in payload_roots:
            root_attrs = attr_values(root.get("attributes", []))
            missing = sorted(required_root_attrs - set(root_attrs))
            if missing:
                root_attr_gaps.append(
                    {"scenario": scenario, "span": root.get("spanId"), "missing_attributes": missing}
                )
            if str(first_attr(root.get("attributes", []), "incident.scenario")) != scenario:
                consistency_gaps.append({"scenario": scenario, "reason": "root_scenario_mismatch"})
            if str(first_attr(root.get("attributes", []), "service.version")) != str(summary_item.get("service_version")):
                consistency_gaps.append({"scenario": scenario, "reason": "service_version_mismatch"})
            if str(first_attr(root.get("attributes", []), "ai.model.variant")) != str(summary_item.get("model_variant")):
                consistency_gaps.append({"scenario": scenario, "reason": "model_variant_mismatch"})

    trait_gaps = []
    for scenario, traits in dict(policy.get("expected_traits", {})).items():
        item = summary_map.get(str(scenario), {})
        if not item:
            continue
        if "service_version" in traits and item.get("service_version") != traits["service_version"]:
            trait_gaps.append({"scenario": scenario, "reason": "service_version"})
        if "tenant_tier" in traits and item.get("tenant_tier") != traits["tenant_tier"]:
            trait_gaps.append({"scenario": scenario, "reason": "tenant_tier"})
        if "request_priority" in traits and item.get("request_priority") != traits["request_priority"]:
            trait_gaps.append({"scenario": scenario, "reason": "request_priority"})
        if float(item.get("error_rate", 0.0)) < float(traits.get("min_error_rate", 0.0)):
            trait_gaps.append({"scenario": scenario, "reason": "min_error_rate"})
        if float(item.get("error_rate", 0.0)) > float(traits.get("max_error_rate", 1.0)):
            trait_gaps.append({"scenario": scenario, "reason": "max_error_rate"})
        if float(item.get("cache_miss_rate", 0.0)) < float(traits.get("min_cache_miss_rate", 0.0)):
            trait_gaps.append({"scenario": scenario, "reason": "min_cache_miss_rate"})
        if float(item.get("cache_miss_rate", 0.0)) > float(traits.get("max_cache_miss_rate", 1.0)):
            trait_gaps.append({"scenario": scenario, "reason": "max_cache_miss_rate"})
        if float(item.get("telemetry_loss_rate", 0.0)) < float(traits.get("min_telemetry_loss_rate", 0.0)):
            trait_gaps.append({"scenario": scenario, "reason": "min_telemetry_loss_rate"})
        if "collector_queue_pressure" in traits and item.get("collector_queue_pressure") != traits["collector_queue_pressure"]:
            trait_gaps.append({"scenario": scenario, "reason": "collector_queue_pressure"})
        if traits.get("required_error_status"):
            payload = present_payloads.get(str(scenario))
            has_error = any(span.get("status", {}).get("code") == "STATUS_CODE_ERROR" for span in spans(payload or {}))
            if not has_error:
                trait_gaps.append({"scenario": scenario, "reason": "missing_error_status"})

    checks = [
        check(
            "scenario_inventory",
            not duplicates
            and not missing_summary
            and not unexpected_summary
            and len(summary_names) >= int(policy.get("minimum_scenario_count", 0)),
            {
                "observed": sorted(summary_names),
                "expected": sorted(expected),
                "duplicates": duplicates,
                "missing": missing_summary,
                "unexpected": unexpected_summary,
            },
        ),
        check(
            "summary_contract",
            not summary_gaps and not metric_gaps,
            {"summary_gaps": summary_gaps, "metric_gaps": metric_gaps},
        ),
        check(
            "payload_inventory",
            not missing_payloads
            and len(present_payloads) >= int(policy.get("minimum_payload_count", 0)),
            {
                "payload_count": len(present_payloads),
                "missing_payloads": missing_payloads,
            },
        ),
        check(
            "trace_shape_contract",
            not trace_shape_gaps
            and root_span_count >= int(policy.get("minimum_root_span_count", 0))
            and total_span_count >= int(policy.get("minimum_total_span_count", 0)),
            {
                "root_span_count": root_span_count,
                "total_span_count": total_span_count,
                "trace_shape_gaps": trace_shape_gaps,
            },
        ),
        check(
            "attribute_contract",
            not root_attr_gaps
            and len(attribute_keys) >= int(policy.get("minimum_attribute_key_count", 0)),
            {
                "attribute_key_count": len(attribute_keys),
                "root_attribute_gaps": root_attr_gaps,
            },
        ),
        check(
            "scenario_consistency",
            not consistency_gaps,
            {"consistency_gaps": consistency_gaps},
        ),
        check(
            "incident_signal_contract",
            not trait_gaps,
            {"trait_gaps": trait_gaps},
        ),
        check(
            "payload_privacy_boundary",
            not forbidden_gaps,
            {"forbidden_attribute_gaps": forbidden_gaps},
        ),
    ]
    metrics = {
        "scenario_count": len(summary_names),
        "payload_count": len(present_payloads),
        "root_span_count": root_span_count,
        "total_span_count": total_span_count,
        "summary_field_count": len(required_fields),
        "attribute_key_count": len(attribute_keys),
        "total_request_count": total_requests,
    }
    return checks, metrics


def apply_fixture(summary: list[dict[str, Any]], payloads: dict[str, dict[str, Any] | None], fixture: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any] | None]]:
    mutated_summary = copy.deepcopy(summary)
    mutated_payloads = copy.deepcopy(payloads)
    mutation = str(fixture.get("mutation", ""))
    scenario = str(fixture.get("scenario", ""))
    if mutation == "remove_summary_scenario":
        mutated_summary = [item for item in mutated_summary if item.get("scenario") != scenario]
    elif mutation == "remove_summary_field":
        for item in mutated_summary:
            if item.get("scenario") == scenario:
                item.pop(str(fixture.get("field", "")), None)
    elif mutation == "remove_payload":
        mutated_payloads[scenario] = None
    elif mutation == "remove_root_attribute":
        remove_root_attribute(mutated_payloads, scenario, str(fixture.get("attribute", "")))
    elif mutation == "remove_child_span":
        remove_child_span(mutated_payloads, scenario, str(fixture.get("span", "")))
    elif mutation == "set_root_attribute":
        set_root_attribute(mutated_payloads, scenario, str(fixture.get("attribute", "")), str(fixture.get("value", "")))
    elif mutation == "append_forbidden_attribute":
        append_root_attribute(mutated_payloads, scenario, str(fixture.get("attribute", "")), str(fixture.get("value", "")))
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated_summary, mutated_payloads


def remove_root_attribute(payloads: dict[str, dict[str, Any] | None], scenario: str, key: str) -> None:
    payload = payloads.get(scenario)
    if not payload:
        return
    roots = root_spans(payload)
    if roots:
        roots[0]["attributes"] = [item for item in roots[0].get("attributes", []) if item.get("key") != key]


def remove_child_span(payloads: dict[str, dict[str, Any] | None], scenario: str, name: str) -> None:
    payload = payloads.get(scenario)
    if not payload:
        return
    for resource_span in payload.get("resourceSpans", []):
        for scope_span in resource_span.get("scopeSpans", []):
            scope_span["spans"] = [span for span in scope_span.get("spans", []) if span.get("name") != name]


def set_root_attribute(payloads: dict[str, dict[str, Any] | None], scenario: str, key: str, value: str) -> None:
    payload = payloads.get(scenario)
    if not payload:
        return
    for root in root_spans(payload):
        for item in root.get("attributes", []):
            if item.get("key") == key:
                item["value"] = {"stringValue": value}


def append_root_attribute(payloads: dict[str, dict[str, Any] | None], scenario: str, key: str, value: str) -> None:
    payload = payloads.get(scenario)
    if not payload:
        return
    roots = root_spans(payload)
    if roots:
        roots[0].setdefault("attributes", []).append(attribute(key, value))


def evaluate_fixtures(summary: list[dict[str, Any]], payloads: dict[str, dict[str, Any] | None], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_summary, mutated_payloads = apply_fixture(summary, payloads, fixture)
        checks, _ = evaluate(mutated_summary, mutated_payloads, policy)
        failed_checks = [item["name"] for item in checks if not item["ok"]]
        expected = str(fixture.get("expected_failed_check"))
        results.append(
            {
                "name": fixture.get("name"),
                "mutation": fixture.get("mutation"),
                "expected_failed_check": expected,
                "failed_checks": failed_checks,
                "detected": expected in failed_checks,
            }
        )
    return results


def build_report(summary: list[dict[str, Any]], payloads: dict[str, dict[str, Any] | None], policy: dict[str, Any]) -> dict[str, Any]:
    checks, metrics = evaluate(summary, payloads, policy)
    fixtures = evaluate_fixtures(summary, payloads, policy)
    detected_fixture_count = sum(1 for item in fixtures if item["detected"])
    checks.append(
        check(
            "negative_fixture_coverage",
            detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
            {
                "detected_fixture_count": detected_fixture_count,
                "minimum_detected_fixtures": policy.get("minimum_detected_fixtures"),
                "fixtures": fixtures,
            },
        )
    )
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "check_count": len(checks),
        "failed_count": failed_count,
        "detected_fixture_count": detected_fixture_count,
        "checks": checks,
        "fixture_results": fixtures,
        **metrics,
    }


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Replay Source Contract Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit validates the generated incident replay summary and OTLP",
        "payloads before downstream reliability, telemetry, and release gates",
        "consume them.",
        "",
        "## Summary",
        "",
        f"- Scenarios: `{report['scenario_count']}`",
        f"- Payloads: `{report['payload_count']}`",
        f"- Root spans: `{report['root_span_count']}`",
        f"- Total spans: `{report['total_span_count']}`",
        f"- Attribute keys: `{report['attribute_key_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Detected |", "| --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(f"| `{item['name']}` | {'yes' if item['detected'] else 'no'} |")
    lines.append("")
    (output_dir / "replay-source-contract-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/replay-source-contract-policy.json")
    parser.add_argument("--summary", default="out/evidence-source/summary.json")
    parser.add_argument("--payload-dir", default="out/evidence-source/payloads")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    policy = load_json(Path(args.policy))
    summary = load_json(Path(args.summary))
    payloads = load_payloads(Path(args.payload_dir), [str(item) for item in policy.get("expected_scenarios", [])])
    report = build_report(summary, payloads, policy)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'replay-source-contract-audit.json'}")
    print(f"wrote {output_dir / 'replay-source-contract-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
