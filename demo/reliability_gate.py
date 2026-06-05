#!/usr/bin/env python3
"""Evaluate replay output against inference reliability expectations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_summary(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("summary must be a JSON list")
    result: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict) or "scenario" not in item:
            raise ValueError("summary items must be objects with a scenario field")
        result[str(item["scenario"])] = item
    return result


def check(condition: bool, message: str) -> dict[str, Any]:
    return {"ok": bool(condition), "message": message}


def evaluate(summary: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    required = {"baseline", "cache_miss_storm", "dependency_timeout", "rollout_regression"}
    missing = sorted(required - set(summary))
    if missing:
        return [
            {
                "name": "required_scenarios",
                "status": "fail",
                "checks": [check(False, f"missing scenarios: {', '.join(missing)}")],
            }
        ]

    baseline = summary["baseline"]
    cache = summary["cache_miss_storm"]
    dependency = summary["dependency_timeout"]
    rollout = summary["rollout_regression"]

    gates = [
        {
            "name": "healthy_baseline",
            "intent": "The control group should stay inside the inference SLO.",
            "checks": [
                check(int(baseline["errors"]) == 0, "baseline has no user-visible errors"),
                check(int(baseline["p95_ms"]) <= 100, "baseline p95 latency is <= 100 ms"),
                check(float(baseline["cache_miss_rate"]) <= 0.10, "baseline cache miss rate is low"),
            ],
        },
        {
            "name": "cache_miss_storm_detected",
            "intent": "Cache miss storms should be classified as latency incidents, not model incidents.",
            "checks": [
                check(int(cache["errors"]) == 0, "cache miss storm has no synthetic upstream errors"),
                check(float(cache["cache_miss_rate"]) >= 0.75, "cache miss rate is high enough to explain latency"),
                check(int(cache["p95_ms"]) >= 150, "cache miss storm breaches the latency SLO"),
            ],
        },
        {
            "name": "dependency_timeout_detected",
            "intent": "Feature-store timeouts should be visible as dependency-driven errors.",
            "checks": [
                check(int(dependency["errors"]) >= 1, "dependency timeout creates user-visible errors"),
                check(float(dependency["error_rate"]) >= 0.30, "dependency timeout error rate is material"),
                check(int(dependency["p95_ms"]) >= 500, "dependency timeout p95 latency is clearly degraded"),
            ],
        },
        {
            "name": "rollout_regression_detected",
            "intent": "A bad service version should be separable from baseline traffic.",
            "checks": [
                check(str(rollout["service_version"]) == "v2", "rollout regression is tied to service.version=v2"),
                check(int(rollout["errors"]) >= 1, "rollout regression creates user-visible errors"),
                check(int(rollout["p95_ms"]) >= 300, "rollout regression breaches the latency SLO"),
            ],
        },
    ]
    for gate in gates:
        gate["status"] = "pass" if all(item["ok"] for item in gate["checks"]) else "fail"
    return gates


def write_json(gates: list[dict[str, Any]], output_dir: Path) -> None:
    payload = {
        "status": "pass" if all(gate["status"] == "pass" for gate in gates) else "fail",
        "gates": gates,
        "resume_claim": (
            "Runnable GKE AI inference reliability lab with incident replay, "
            "SLO-style reliability gates, Kubernetes metadata, and collector delivery proof."
        ),
    }
    (output_dir / "reliability-gate.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(gates: list[dict[str, Any]], output_dir: Path) -> None:
    status = "PASS" if all(gate["status"] == "pass" for gate in gates) else "FAIL"
    lines = [
        "# Reliability Gate Evidence",
        "",
        f"Overall status: **{status}**",
        "",
        "This gate turns the replay into an SRE-style reliability check. The lab",
        "does not merely generate traces; it verifies that healthy traffic stays",
        "inside the control SLO and that failure scenarios are classified by the",
        "signal a production team would need during incident triage.",
        "",
        "| Gate | Status | Intent |",
        "| --- | --- | --- |",
    ]
    for gate in gates:
        lines.append(f"| `{gate['name']}` | {gate['status']} | {gate['intent']} |")

    lines.extend(["", "## Checks", ""])
    for gate in gates:
        lines.append(f"### {gate['name']}")
        lines.append("")
        for item in gate["checks"]:
            marker = "PASS" if item["ok"] else "FAIL"
            lines.append(f"- {marker}: {item['message']}")
        lines.append("")

    lines.extend(
        [
            "## Resume-Safe Claim",
            "",
            "> Built a runnable GKE AI inference reliability lab with OpenTelemetry",
            "> traces, Kubernetes metadata, durable collector queues, incident replay,",
            "> and SLO-style reliability gates for SRE debugging workflows.",
            "",
        ]
    )
    (output_dir / "reliability-gate.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--output-dir", default="out/reliability-gate")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gates = evaluate(load_summary(Path(args.summary)))
    write_json(gates, output_dir)
    write_markdown(gates, output_dir)
    print(f"wrote {output_dir / 'reliability-gate.json'}")
    print(f"wrote {output_dir / 'reliability-gate.md'}")
    return 0 if all(gate["status"] == "pass" for gate in gates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
