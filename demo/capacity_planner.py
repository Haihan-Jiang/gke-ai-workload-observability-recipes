#!/usr/bin/env python3
"""Estimate inference serving capacity from replay evidence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


BOTTLENECKS = {
    "baseline": "normal inference path",
    "cache_miss_storm": "vector cache and retrieval path",
    "dependency_timeout": "feature-store dependency",
    "rollout_regression": "service rollout and version skew",
    "collector_queue_pressure": "telemetry collector delivery path",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def estimate_replicas(item: dict[str, Any], capacity: dict[str, Any]) -> dict[str, Any]:
    p95_ms = max(1, int(item["p95_ms"]))
    target_rps = float(capacity["target_rps"])
    concurrency = int(capacity["concurrency_per_replica"])
    headroom = float(capacity["headroom_factor"])
    per_replica_rps = round((concurrency * 1000) / p95_ms, 2)
    replicas = max(1, math.ceil((target_rps * headroom) / per_replica_rps))
    warnings: list[str] = []
    if float(item["error_rate"]) > 0:
        warnings.append("do not scale traffic until user-visible errors are isolated")
    if float(item["telemetry_loss_rate"]) > 0:
        warnings.append("fix collector delivery before trusting production dashboards")
    if replicas > int(capacity["max_replicas_budget"]):
        warnings.append("required replicas exceed the demo budget; treat as a dependency or design issue")
    return {
        "scenario": item["scenario"],
        "bottleneck": BOTTLENECKS.get(str(item["scenario"]), "unknown"),
        "p95_ms": p95_ms,
        "error_rate": item["error_rate"],
        "telemetry_loss_rate": item["telemetry_loss_rate"],
        "estimated_rps_per_replica": per_replica_rps,
        "target_rps": target_rps,
        "headroom_factor": headroom,
        "required_replicas": replicas,
        "warnings": warnings,
    }


def write_json(plan: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "capacity-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")


def write_markdown(plan: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Capacity Plan Evidence",
        "",
        "This report converts replayed p95 latency into a rough serving-capacity",
        "check. It is not a cloud cost estimate; it is a deterministic local",
        "sanity check for whether a scenario is a scaling problem or a reliability",
        "problem that must be fixed before adding replicas.",
        "",
        f"- Target RPS: `{plan['target_rps']}`",
        f"- Concurrency per replica: `{plan['concurrency_per_replica']}`",
        f"- Headroom factor: `{plan['headroom_factor']}`",
        f"- Replica budget: `{plan['max_replicas_budget']}`",
        "",
        "| Scenario | Bottleneck | p95 ms | Est. RPS / replica | Required replicas | Warnings |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for item in plan["scenarios"]:
        warnings = "; ".join(item["warnings"]) if item["warnings"] else "none"
        row = dict(item)
        row["warnings"] = warnings
        lines.append(
            "| {scenario} | {bottleneck} | {p95_ms} | {estimated_rps_per_replica} | {required_replicas} | {warnings} |".format(
                **row,
            )
        )

    lines.extend(
        [
            "",
            "## How To Use This",
            "",
            "- If only latency is high and there are no errors, test cache and scaling changes.",
            "- If error rate is high, treat the scenario as an incident before scaling traffic.",
            "- If telemetry loss is high, fix collector/exporter delivery before trusting dashboards.",
            "",
        ]
    )
    (output_dir / "capacity-plan.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--slo-config", default="config/reliability-slo.json")
    parser.add_argument("--output-dir", default="out/capacity-plan")
    args = parser.parse_args()

    summary = load_json(Path(args.summary))
    slo_config = load_json(Path(args.slo_config))
    capacity = slo_config["capacity"]
    scenarios = [estimate_replicas(item, capacity) for item in summary]
    plan = {
        "profile": slo_config["profile"],
        "target_rps": capacity["target_rps"],
        "concurrency_per_replica": capacity["concurrency_per_replica"],
        "headroom_factor": capacity["headroom_factor"],
        "max_replicas_budget": capacity["max_replicas_budget"],
        "scenarios": scenarios,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(plan, output_dir)
    write_markdown(plan, output_dir)
    print(f"wrote {output_dir / 'capacity-plan.json'}")
    print(f"wrote {output_dir / 'capacity-plan.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
