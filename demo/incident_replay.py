#!/usr/bin/env python3
"""Replay AI inference incidents as OTLP/HTTP traces and write a report.

The script intentionally uses only the Python standard library so the lab can
run on a clean laptop without a package install.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import uuid
from pathlib import Path
from typing import Any
from urllib import request


def hex_id(byte_count: int) -> str:
    return uuid.uuid4().hex[: byte_count * 2]


def attribute(key: str, value: str | int | float | bool) -> dict[str, object]:
    if isinstance(value, bool):
        encoded: dict[str, object] = {"boolValue": value}
    elif isinstance(value, int):
        encoded = {"intValue": value}
    elif isinstance(value, float):
        encoded = {"doubleValue": value}
    else:
        encoded = {"stringValue": value}
    return {"key": key, "value": encoded}


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "baseline",
        "description": "Healthy inference path with cache hits and stable model latency.",
        "requests": 8,
        "latencies_ms": [42, 45, 43, 48, 46, 44, 47, 45],
        "cache": "hit",
        "dependency_ms": 8,
        "status_code": 200,
        "error_rate": 0.0,
        "service_version": "v1",
        "triage": "Healthy control group; use as the comparison baseline.",
    },
    {
        "name": "cache_miss_storm",
        "description": "Vector cache misses push model latency above the SLO.",
        "requests": 7,
        "latencies_ms": [155, 188, 206, 240, 229, 196, 251],
        "cache": "miss",
        "dependency_ms": 64,
        "status_code": 200,
        "error_rate": 0.0,
        "service_version": "v1",
        "triage": "Look for cache.result=miss and longer vector-cache spans before tuning the model path.",
    },
    {
        "name": "dependency_timeout",
        "description": "Feature-store timeouts create elevated latency and user-visible errors.",
        "requests": 6,
        "latencies_ms": [520, 880, 1210, 960, 1320, 1140],
        "cache": "hit",
        "dependency_ms": 730,
        "status_code": 503,
        "error_rate": 0.5,
        "service_version": "v1",
        "triage": "Trace child spans isolate feature-store lookup as the dominant latency source.",
    },
    {
        "name": "rollout_regression",
        "description": "A new service version increases latency and error rate during rollout.",
        "requests": 7,
        "latencies_ms": [180, 210, 340, 410, 390, 455, 370],
        "cache": "mixed",
        "dependency_ms": 90,
        "status_code": 500,
        "error_rate": 0.28,
        "service_version": "v2",
        "triage": "Compare service.version=v2 traces against baseline before rolling forward.",
    },
]


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((pct / 100) * (len(ordered) - 1)))
    return ordered[index]


def span(
    *,
    trace_id: str,
    span_id: str,
    name: str,
    start_ns: int,
    duration_ms: int,
    parent_span_id: str | None = None,
    status_code: str = "STATUS_CODE_UNSET",
    attrs: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": name,
        "kind": 1,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(start_ns + duration_ms * 1_000_000),
        "attributes": attrs or [],
    }
    if parent_span_id:
        result["parentSpanId"] = parent_span_id
    if status_code != "STATUS_CODE_UNSET":
        result["status"] = {"code": status_code}
    return result


def build_scenario_payload(scenario: dict[str, Any], base_ns: int) -> dict[str, object]:
    spans: list[dict[str, object]] = []
    latencies = list(scenario["latencies_ms"])
    error_count = round(float(scenario["error_rate"]) * int(scenario["requests"]))
    for index, latency_ms in enumerate(latencies):
        trace_id = hex_id(16)
        root_span_id = hex_id(8)
        cache_span_id = hex_id(8)
        dependency_span_id = hex_id(8)
        model_span_id = hex_id(8)
        request_start = base_ns + index * 200_000_000
        is_error = index >= len(latencies) - error_count
        status_code = int(scenario["status_code"]) if is_error else 200
        cache_result = scenario["cache"]
        if cache_result == "mixed":
            cache_result = "miss" if index % 2 else "hit"

        root_attrs = [
            attribute("http.route", "/v1/infer"),
            attribute("http.status_code", status_code),
            attribute("ai.model", "demo-recommender"),
            attribute("ai.inference.latency_ms", int(latency_ms)),
            attribute("cache.result", str(cache_result)),
            attribute("incident.scenario", str(scenario["name"])),
            attribute("service.version", str(scenario["service_version"])),
            attribute("sre.signal", "latency"),
        ]
        if is_error:
            root_attrs.extend(
                [
                    attribute("error.type", "upstream_dependency"),
                    attribute("sre.signal", "error"),
                ]
            )

        spans.append(
            span(
                trace_id=trace_id,
                span_id=root_span_id,
                name="POST /v1/infer",
                start_ns=request_start,
                duration_ms=int(latency_ms),
                status_code="STATUS_CODE_ERROR" if is_error else "STATUS_CODE_UNSET",
                attrs=root_attrs,
            )
        )
        spans.append(
            span(
                trace_id=trace_id,
                span_id=cache_span_id,
                parent_span_id=root_span_id,
                name="vector-cache lookup",
                start_ns=request_start + 3_000_000,
                duration_ms=18 if cache_result == "miss" else 6,
                attrs=[
                    attribute("cache.result", str(cache_result)),
                    attribute("incident.scenario", str(scenario["name"])),
                    attribute("sre.signal", "dependency"),
                ],
            )
        )
        spans.append(
            span(
                trace_id=trace_id,
                span_id=dependency_span_id,
                parent_span_id=root_span_id,
                name="feature-store lookup",
                start_ns=request_start + 18_000_000,
                duration_ms=int(scenario["dependency_ms"]),
                status_code="STATUS_CODE_ERROR" if is_error else "STATUS_CODE_UNSET",
                attrs=[
                    attribute("peer.service", "feature-store"),
                    attribute("incident.scenario", str(scenario["name"])),
                    attribute("sre.signal", "dependency"),
                ],
            )
        )
        spans.append(
            span(
                trace_id=trace_id,
                span_id=model_span_id,
                parent_span_id=root_span_id,
                name="model inference",
                start_ns=request_start + 34_000_000,
                duration_ms=max(20, int(latency_ms) - int(scenario["dependency_ms"]) - 20),
                attrs=[
                    attribute("ai.model", "demo-recommender"),
                    attribute("incident.scenario", str(scenario["name"])),
                    attribute("sre.signal", "model"),
                ],
            )
        )

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        attribute("service.name", "toy-ai-inference-api"),
                        attribute("deployment.environment", "incident-replay"),
                        attribute("cloud.provider", "gcp"),
                        attribute("k8s.cluster.name", "local-reference"),
                        attribute("k8s.namespace.name", "ai-observability-demo"),
                        attribute("service.version", str(scenario["service_version"])),
                        attribute("incident.scenario", str(scenario["name"])),
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "gke-ai-observability-lab"},
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def post_payload(endpoint: str, payload: dict[str, object]) -> int:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        response.read()
        return int(response.status)


def summarize_scenario(scenario: dict[str, Any]) -> dict[str, object]:
    latencies = list(scenario["latencies_ms"])
    request_count = int(scenario["requests"])
    error_count = round(float(scenario["error_rate"]) * request_count)
    cache = str(scenario["cache"])
    miss_count = request_count if cache == "miss" else 0
    if cache == "mixed":
        miss_count = request_count // 2
    return {
        "scenario": scenario["name"],
        "description": scenario["description"],
        "requests": request_count,
        "errors": error_count,
        "error_rate": round(error_count / request_count, 2),
        "p50_ms": int(statistics.median(latencies)),
        "p95_ms": percentile(latencies, 95),
        "cache_miss_rate": round(miss_count / request_count, 2),
        "service_version": scenario["service_version"],
        "triage": scenario["triage"],
    }


def write_report(output_dir: Path, summaries: list[dict[str, object]], endpoint: str, sent: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Incident Replay Report",
        "",
        "This report is generated by `demo/incident_replay.py`.",
        "",
        f"- OTLP endpoint: `{endpoint}`",
        f"- Sent to collector: `{str(sent).lower()}`",
        "",
        "| Scenario | Requests | Errors | p50 ms | p95 ms | Cache miss rate | Triage signal |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in summaries:
        lines.append(
            "| {scenario} | {requests} | {errors} | {p50_ms} | {p95_ms} | {cache_miss_rate} | {triage} |".format(
                **item
            )
        )
    lines.extend(
        [
            "",
            "## What This Proves",
            "",
            "- The lab can replay healthy and unhealthy AI inference paths.",
            "- Each trace carries scenario, service version, latency, cache, and dependency context.",
            "- The generated report gives a reviewer an incident narrative instead of only raw config.",
            "",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("OTLP_HTTP_ENDPOINT", "http://127.0.0.1:4318/v1/traces"),
    )
    parser.add_argument("--output-dir", default="out/incident-replay")
    parser.add_argument("--no-send", action="store_true", help="generate the report without sending OTLP")
    args = parser.parse_args()

    base_ns = time.time_ns()
    summaries = [summarize_scenario(scenario) for scenario in SCENARIOS]
    sent = not args.no_send
    if sent:
        for offset, scenario in enumerate(SCENARIOS):
            status = post_payload(args.endpoint, build_scenario_payload(scenario, base_ns + offset * 2_000_000_000))
            print(f"sent scenario={scenario['name']} status={status}")

    output_dir = Path(args.output_dir)
    write_report(output_dir, summaries, args.endpoint, sent)
    print(f"wrote {output_dir / 'report.md'}")
    print(f"wrote {output_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
