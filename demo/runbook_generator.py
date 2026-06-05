#!/usr/bin/env python3
"""Generate scenario runbooks from incident replay evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


RUNBOOKS = {
    "baseline": {
        "problem_id": "P01",
        "owner": "SRE / platform",
        "first_checks": [
            "Confirm p95 latency and error rate match the healthy control group.",
            "Verify traces include k8s namespace, service.version, cache.result, and incident.scenario.",
        ],
        "mitigation": "Use as the comparison group before changing traffic or rollout policy.",
    },
    "cache_miss_storm": {
        "problem_id": "P02",
        "owner": "Inference platform / retrieval owner",
        "first_checks": [
            "Filter traces where cache.result=miss.",
            "Compare vector-cache lookup span time against model inference span time.",
            "Check whether a rollout, embedding-version change, or cache eviction preceded the storm.",
        ],
        "mitigation": "Warm or pin the retrieval cache, reduce cache churn, and protect the model path with rate limits.",
    },
    "dependency_timeout": {
        "problem_id": "P03",
        "owner": "Feature platform / dependency owner",
        "first_checks": [
            "Inspect feature-store lookup child spans for timeout or retry patterns.",
            "Compare dependency latency against root inference latency.",
            "Check dependency saturation before scaling the inference deployment.",
        ],
        "mitigation": "Fail closed with a fallback feature set, cap retries, and page the dependency owner.",
    },
    "rollout_regression": {
        "problem_id": "P04",
        "owner": "Service owner / release engineer",
        "first_checks": [
            "Split traces by service.version.",
            "Compare v2 latency and errors against the baseline v1 group.",
            "Check deployment events, image digest, and config changes for the affected version.",
        ],
        "mitigation": "Pause rollout, shift traffic back to the stable version, and keep the failing traces for review.",
    },
    "collector_queue_pressure": {
        "problem_id": "P05",
        "owner": "Observability platform",
        "first_checks": [
            "Check collector queue depth, retry counts, and exporter backpressure.",
            "Confirm the application remains healthy while telemetry loss increases.",
            "Validate persistent queue storage and collector resource requests.",
        ],
        "mitigation": "Scale or restart collectors, protect queue storage, and reduce exporter pressure before declaring dashboards healthy.",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_runbooks(summary: list[dict[str, Any]], gate: dict[str, Any]) -> list[dict[str, Any]]:
    gate_status = {item["name"]: item["status"] for item in gate.get("gates", [])}
    result: list[dict[str, Any]] = []
    for item in summary:
        scenario = str(item["scenario"])
        template = RUNBOOKS.get(scenario)
        if not template:
            continue
        result.append(
            {
                "scenario": scenario,
                "problem_id": template["problem_id"],
                "owner": template["owner"],
                "trigger": item["triage"],
                "p95_ms": item["p95_ms"],
                "error_rate": item["error_rate"],
                "telemetry_loss_rate": item["telemetry_loss_rate"],
                "first_checks": template["first_checks"],
                "mitigation": template["mitigation"],
                "gate_status": gate_status,
            }
        )
    return result


def write_json(runbooks: list[dict[str, Any]], output_dir: Path) -> None:
    payload = {"runbooks": runbooks}
    (output_dir / "incident-runbooks.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_markdown(runbooks: list[dict[str, Any]], output_dir: Path) -> None:
    lines = [
        "# Incident Runbooks",
        "",
        "These runbooks are generated from the replay output. They keep the lab",
        "grounded in operational actions instead of stopping at dashboards.",
        "",
    ]
    for item in runbooks:
        lines.extend(
            [
                f"## {item['scenario']}",
                "",
                f"- Problem: `{item['problem_id']}`",
                f"- Owner: {item['owner']}",
                f"- Trigger: {item['trigger']}",
                f"- p95 latency: `{item['p95_ms']} ms`",
                f"- Error rate: `{item['error_rate']}`",
                f"- Telemetry loss rate: `{item['telemetry_loss_rate']}`",
                "",
                "First checks:",
            ]
        )
        for check in item["first_checks"]:
            lines.append(f"- {check}")
        lines.extend(["", f"Mitigation: {item['mitigation']}", ""])
    (output_dir / "incident-runbooks.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--gate", default="out/reliability-gate/reliability-gate.json")
    parser.add_argument("--output-dir", default="out/incident-runbooks")
    args = parser.parse_args()

    runbooks = build_runbooks(load_json(Path(args.summary)), load_json(Path(args.gate)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(runbooks, output_dir)
    write_markdown(runbooks, output_dir)
    print(f"wrote {output_dir / 'incident-runbooks.json'}")
    print(f"wrote {output_dir / 'incident-runbooks.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
