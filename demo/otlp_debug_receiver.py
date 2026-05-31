#!/usr/bin/env python3
"""A tiny OTLP/HTTP debug receiver for machines without Docker."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


def value_to_text(value: dict[str, Any]) -> str:
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in value:
            return str(value[key])
    return json.dumps(value, sort_keys=True)


def attrs_to_dict(attrs: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in attrs:
        key = str(item.get("key") or "")
        value = item.get("value") if isinstance(item.get("value"), dict) else {}
        if key:
            result[key] = value_to_text(value)
    return result


def summarize(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for resource_span in payload.get("resourceSpans", []):
        resource = resource_span.get("resource") or {}
        resource_attrs = attrs_to_dict(resource.get("attributes") or [])
        service = resource_attrs.get("service.name", "unknown-service")
        scenario = resource_attrs.get("incident.scenario", "-")
        for scope_span in resource_span.get("scopeSpans", []):
            for span in scope_span.get("spans", []):
                span_attrs = attrs_to_dict(span.get("attributes") or [])
                latency = span_attrs.get("ai.inference.latency_ms", "-")
                cache = span_attrs.get("cache.result", "-")
                lines.append(
                    "span="
                    + str(span.get("name") or "unnamed")
                    + " service="
                    + service
                    + " scenario="
                    + span_attrs.get("incident.scenario", scenario)
                    + " signal="
                    + span_attrs.get("sre.signal", "-")
                    + " latency_ms="
                    + latency
                    + " cache="
                    + cache
                )
    return lines


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length") or "0")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return

        print("received OTLP trace request:", flush=True)
        for line in summarize(payload):
            print("  " + line, flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4318)
    args = parser.parse_args()
    server = HTTPServer((args.host, args.port), Handler)
    print(f"OTLP debug receiver listening on http://{args.host}:{args.port}/v1/traces", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
