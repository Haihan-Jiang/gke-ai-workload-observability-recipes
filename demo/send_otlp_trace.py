#!/usr/bin/env python3
"""Send a small OTLP/HTTP trace without third-party dependencies."""

from __future__ import annotations

import json
import os
import time
import uuid
from urllib import request


def hex_id(byte_count: int) -> str:
    return uuid.uuid4().hex[: byte_count * 2]


def attr(key: str, value: str) -> dict[str, object]:
    return {"key": key, "value": {"stringValue": value}}


def build_payload() -> dict[str, object]:
    now = time.time_ns()
    trace_id = hex_id(16)
    root_span = hex_id(8)
    child_span = hex_id(8)
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        attr("service.name", "toy-ai-inference-api"),
                        attr("deployment.environment", "local-demo"),
                        attr("cloud.provider", "gcp"),
                        attr("k8s.cluster.name", "local-reference"),
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "gke-ai-observability-demo"},
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": root_span,
                                "name": "POST /v1/infer",
                                "kind": 2,
                                "startTimeUnixNano": str(now),
                                "endTimeUnixNano": str(now + 25_000_000),
                                "attributes": [
                                    attr("ai.model", "demo-recommender"),
                                    attr("http.route", "/v1/infer"),
                                    attr("sre.signal", "latency"),
                                ],
                            },
                            {
                                "traceId": trace_id,
                                "spanId": child_span,
                                "parentSpanId": root_span,
                                "name": "vector-cache lookup",
                                "kind": 1,
                                "startTimeUnixNano": str(now + 2_000_000),
                                "endTimeUnixNano": str(now + 9_000_000),
                                "attributes": [
                                    attr("cache.result", "hit"),
                                    attr("sre.signal", "dependency"),
                                ],
                            },
                        ],
                    }
                ],
            }
        ]
    }


def main() -> int:
    endpoint = os.environ.get("OTLP_HTTP_ENDPOINT", "http://127.0.0.1:4318/v1/traces")
    data = json.dumps(build_payload()).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
    print(f"sent trace to {endpoint}; status={response.status}; body={body!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

