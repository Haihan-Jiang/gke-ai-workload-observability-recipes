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


def load_slo_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "scenarios" not in data:
        raise ValueError("SLO config must be an object with a scenarios field")
    return data


def check(condition: bool, message: str) -> dict[str, Any]:
    return {"ok": bool(condition), "message": message}


def scenario_slo(slo_config: dict[str, Any], scenario: str) -> dict[str, Any]:
    scenarios = slo_config.get("scenarios", {})
    if not isinstance(scenarios, dict) or scenario not in scenarios:
        raise ValueError(f"missing SLO config for scenario {scenario}")
    value = scenarios[scenario]
    if not isinstance(value, dict):
        raise ValueError(f"SLO config for scenario {scenario} must be an object")
    return value


def evaluate(summary: dict[str, dict[str, Any]], slo_config: dict[str, Any]) -> list[dict[str, Any]]:
    required = set(slo_config["scenarios"])
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
    collector = summary["collector_queue_pressure"]
    baseline_slo = scenario_slo(slo_config, "baseline")
    cache_slo = scenario_slo(slo_config, "cache_miss_storm")
    dependency_slo = scenario_slo(slo_config, "dependency_timeout")
    rollout_slo = scenario_slo(slo_config, "rollout_regression")
    collector_slo = scenario_slo(slo_config, "collector_queue_pressure")

    gates = [
        {
            "name": "healthy_baseline",
            "intent": "The control group should stay inside the inference SLO.",
            "checks": [
                check(int(baseline["errors"]) <= int(baseline_slo["max_errors"]), "baseline has no user-visible errors"),
                check(
                    int(baseline["p95_ms"]) <= int(baseline_slo["max_p95_ms"]),
                    f"baseline p95 latency is <= {baseline_slo['max_p95_ms']} ms",
                ),
                check(
                    float(baseline["cache_miss_rate"]) <= float(baseline_slo["max_cache_miss_rate"]),
                    "baseline cache miss rate is low",
                ),
                check(
                    float(baseline["telemetry_loss_rate"]) <= float(baseline_slo["max_telemetry_loss_rate"]),
                    "baseline telemetry delivery is loss-free",
                ),
            ],
        },
        {
            "name": "cache_miss_storm_detected",
            "intent": "Cache miss storms should be classified as latency incidents, not model incidents.",
            "checks": [
                check(int(cache["errors"]) <= int(cache_slo["max_errors"]), "cache miss storm has no synthetic upstream errors"),
                check(
                    float(cache["cache_miss_rate"]) >= float(cache_slo["min_cache_miss_rate"]),
                    "cache miss rate is high enough to explain latency",
                ),
                check(int(cache["p95_ms"]) >= int(cache_slo["min_p95_ms"]), "cache miss storm breaches the latency SLO"),
            ],
        },
        {
            "name": "dependency_timeout_detected",
            "intent": "Feature-store timeouts should be visible as dependency-driven errors.",
            "checks": [
                check(
                    int(dependency["errors"]) >= int(dependency_slo["min_errors"]),
                    "dependency timeout creates user-visible errors",
                ),
                check(
                    float(dependency["error_rate"]) >= float(dependency_slo["min_error_rate"]),
                    "dependency timeout error rate is material",
                ),
                check(
                    int(dependency["p95_ms"]) >= int(dependency_slo["min_p95_ms"]),
                    "dependency timeout p95 latency is clearly degraded",
                ),
            ],
        },
        {
            "name": "rollout_regression_detected",
            "intent": "A bad service version should be separable from baseline traffic.",
            "checks": [
                check(
                    str(rollout["service_version"]) == str(rollout_slo["expected_service_version"]),
                    f"rollout regression is tied to service.version={rollout_slo['expected_service_version']}",
                ),
                check(
                    int(rollout["errors"]) >= int(rollout_slo["min_errors"]),
                    "rollout regression creates user-visible errors",
                ),
                check(
                    int(rollout["p95_ms"]) >= int(rollout_slo["min_p95_ms"]),
                    "rollout regression breaches the latency SLO",
                ),
            ],
        },
        {
            "name": "collector_queue_pressure_detected",
            "intent": "Telemetry delivery loss should be detected separately from user-facing app failure.",
            "checks": [
                check(int(collector["errors"]) <= int(collector_slo["max_errors"]), "collector pressure has no app errors"),
                check(
                    float(collector["telemetry_loss_rate"]) >= float(collector_slo["min_telemetry_loss_rate"]),
                    "telemetry loss rate is high enough to trigger delivery investigation",
                ),
                check(
                    str(collector["collector_queue_pressure"]) == str(collector_slo["expected_collector_queue_pressure"]),
                    "collector queue pressure is classified as high",
                ),
                check(
                    int(collector["p95_ms"]) <= int(collector_slo["max_p95_ms"]),
                    "application latency remains inside the collector-pressure ceiling",
                ),
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
            "configurable SLO gates, Kubernetes metadata, and collector delivery proof."
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
    parser.add_argument("--slo-config", default="config/reliability-slo.json")
    parser.add_argument("--output-dir", default="out/reliability-gate")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gates = evaluate(load_summary(Path(args.summary)), load_slo_config(Path(args.slo_config)))
    write_json(gates, output_dir)
    write_markdown(gates, output_dir)
    print(f"wrote {output_dir / 'reliability-gate.json'}")
    print(f"wrote {output_dir / 'reliability-gate.md'}")
    return 0 if all(gate["status"] == "pass" for gate in gates) else 1


if __name__ == "__main__":
    raise SystemExit(main())
