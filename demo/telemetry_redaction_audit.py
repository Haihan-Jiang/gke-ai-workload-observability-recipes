#!/usr/bin/env python3
"""Audit OTLP payloads for AI telemetry redaction and metadata safety."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PASS = "pass"
FAIL = "fail"
OTEL_VALUE_KEYS = ("stringValue", "intValue", "doubleValue", "boolValue")


@dataclass(frozen=True)
class AttributeObservation:
    payload: str
    scenario: str
    location: str
    key: str
    value: str | int | float | bool | None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def otel_value(attribute: dict[str, Any]) -> str | int | float | bool | None:
    value = attribute.get("value", {})
    if not isinstance(value, dict):
        return None
    for key in OTEL_VALUE_KEYS:
        if key in value:
            return value[key]
    return None


def attributes_to_map(attributes: Iterable[dict[str, Any]]) -> dict[str, str | int | float | bool | None]:
    return {str(item.get("key", "")): otel_value(item) for item in attributes}


def scenario_from_payload(payload: dict[str, Any], fallback: str) -> str:
    for resource_span in payload.get("resourceSpans", []):
        resource_attrs = attributes_to_map(resource_span.get("resource", {}).get("attributes", []))
        value = resource_attrs.get("incident.scenario")
        if value:
            return str(value)
    return fallback


def iter_attributes(payload: dict[str, Any], payload_name: str) -> list[AttributeObservation]:
    scenario = scenario_from_payload(payload, Path(payload_name).stem.replace(".otlp", ""))
    observations: list[AttributeObservation] = []
    for resource_index, resource_span in enumerate(payload.get("resourceSpans", [])):
        resource_attrs = resource_span.get("resource", {}).get("attributes", [])
        for attribute in resource_attrs:
            observations.append(
                AttributeObservation(
                    payload=payload_name,
                    scenario=scenario,
                    location=f"resource[{resource_index}]",
                    key=str(attribute.get("key", "")),
                    value=otel_value(attribute),
                )
            )
        for scope_index, scope_span in enumerate(resource_span.get("scopeSpans", [])):
            for span_index, span in enumerate(scope_span.get("spans", [])):
                span_name = str(span.get("name", "span"))
                for attribute in span.get("attributes", []):
                    observations.append(
                        AttributeObservation(
                            payload=payload_name,
                            scenario=scenario,
                            location=f"scope[{scope_index}].span[{span_index}] {span_name}",
                            key=str(attribute.get("key", "")),
                            value=otel_value(attribute),
                        )
                    )
    return observations


def load_payload_observations(payload_dir: Path) -> tuple[list[str], list[AttributeObservation]]:
    payload_files = sorted(payload_dir.glob("*.otlp.json"))
    observations: list[AttributeObservation] = []
    for path in payload_files:
        observations.extend(iter_attributes(load_json(path), path.name))
    return [path.name for path in payload_files], observations


def compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def hashed_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def violation(
    *,
    observation: AttributeObservation,
    reason: str,
    pattern: str | None = None,
) -> dict[str, Any]:
    result = {
        "payload": observation.payload,
        "scenario": observation.scenario,
        "location": observation.location,
        "key": observation.key,
        "reason": reason,
    }
    if pattern:
        result["pattern"] = pattern
    if isinstance(observation.value, str):
        result["value_sha256"] = hashed_value(observation.value)
        result["value_length"] = len(observation.value)
    return result


def scenario_keys(observations: list[AttributeObservation], location_prefix: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for observation in observations:
        if observation.location.startswith(location_prefix):
            result.setdefault(observation.scenario, set()).add(observation.key)
    return result


def missing_required(
    observed_by_scenario: dict[str, set[str]],
    scenarios: set[str],
    required: set[str],
) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for scenario in sorted(scenarios):
        absent = sorted(required - observed_by_scenario.get(scenario, set()))
        if absent:
            missing[scenario] = absent
    return missing


def build_report(
    *,
    summary: list[dict[str, Any]],
    payload_dir: Path,
    policy: dict[str, Any],
) -> dict[str, Any]:
    payload_files, observations = load_payload_observations(payload_dir)
    expected_scenarios = {str(item["scenario"]) for item in summary}
    expected_scenarios.update(str(item) for item in policy.get("required_scenarios", []))
    observed_scenarios = {item.scenario for item in observations}
    resource_keys = scenario_keys(observations, "resource")
    span_keys = scenario_keys(observations, "scope")
    required_resource = set(policy.get("required_resource_attributes", []))
    required_span = set(policy.get("required_span_attributes", []))
    approved_ai_metadata = set(policy.get("approved_ai_metadata_attributes", []))

    forbidden_key_patterns = compile_patterns(policy.get("forbidden_attribute_key_patterns", []))
    forbidden_value_patterns = compile_patterns(policy.get("forbidden_attribute_value_patterns", []))
    max_string_length = int(policy.get("max_string_value_length", 0))

    key_violations = [
        violation(observation=observation, reason="forbidden_attribute_key", pattern=pattern.pattern)
        for observation in observations
        for pattern in forbidden_key_patterns
        if pattern.search(observation.key)
    ]
    value_violations = [
        violation(observation=observation, reason="forbidden_attribute_value", pattern=pattern.pattern)
        for observation in observations
        if isinstance(observation.value, str)
        for pattern in forbidden_value_patterns
        if pattern.search(observation.value)
    ]
    length_violations = [
        violation(observation=observation, reason="string_value_too_long")
        for observation in observations
        if isinstance(observation.value, str) and len(observation.value) > max_string_length
    ]
    ai_attribute_keys = {item.key for item in observations if item.key.startswith("ai.")}
    unapproved_ai_attributes = sorted(ai_attribute_keys - approved_ai_metadata)
    resource_missing = missing_required(resource_keys, expected_scenarios, required_resource)
    span_missing = missing_required(span_keys, expected_scenarios, required_span)
    string_lengths = [
        len(item.value)
        for item in observations
        if isinstance(item.value, str)
    ]
    redaction_violations = key_violations + value_violations + length_violations
    checks = [
        {
            "name": "payload_coverage",
            "ok": len(payload_files) >= int(policy["minimum_payloads"]) and observed_scenarios >= expected_scenarios,
            "evidence": {
                "payloads": payload_files,
                "expected_scenarios": sorted(expected_scenarios),
                "observed_scenarios": sorted(observed_scenarios),
            },
        },
        {
            "name": "resource_context",
            "ok": not resource_missing,
            "evidence": {"missing": resource_missing},
        },
        {
            "name": "span_context",
            "ok": not span_missing,
            "evidence": {"missing": span_missing},
        },
        {
            "name": "approved_ai_metadata",
            "ok": not unapproved_ai_attributes and approved_ai_metadata <= ai_attribute_keys,
            "evidence": {
                "observed_ai_attributes": sorted(ai_attribute_keys),
                "unapproved_ai_attributes": unapproved_ai_attributes,
            },
        },
        {
            "name": "forbidden_attribute_keys",
            "ok": not key_violations,
            "evidence": {"violations": key_violations},
        },
        {
            "name": "forbidden_attribute_values",
            "ok": not value_violations,
            "evidence": {"violations": value_violations},
        },
        {
            "name": "string_value_budget",
            "ok": not length_violations,
            "evidence": {
                "max_allowed": max_string_length,
                "max_observed": max(string_lengths) if string_lengths else 0,
                "violations": length_violations,
            },
        },
    ]
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "payload_count": len(payload_files),
        "attribute_count": len(observations),
        "scenario_count": len(observed_scenarios),
        "redaction_violation_count": len(redaction_violations) + len(unapproved_ai_attributes),
        "failed_count": failed_count,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "telemetry-redaction-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Telemetry Redaction Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks the generated OTLP trace payloads before treating",
        "them as production-style evidence. It allows operational AI metadata",
        "such as token counts, model variant, latency, queue wait, and GPU time,",
        "while blocking prompt text, completion text, request/response bodies,",
        "secrets, direct identifiers, and oversized string attributes.",
        "",
        "## Summary",
        "",
        f"- Payloads: `{report['payload_count']}`",
        f"- Scenarios: `{report['scenario_count']}`",
        f"- Attributes inspected: `{report['attribute_count']}`",
        f"- Redaction violations: `{report['redaction_violation_count']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    (output_dir / "telemetry-redaction-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--payload-dir", default="out/incident-replay-payloads")
    parser.add_argument("--policy", default="config/telemetry-redaction-policy.json")
    parser.add_argument("--output-dir", default="out/telemetry-redaction-audit")
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
    print(f"wrote {output_dir / 'telemetry-redaction-audit.json'}")
    print(f"wrote {output_dir / 'telemetry-redaction-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
