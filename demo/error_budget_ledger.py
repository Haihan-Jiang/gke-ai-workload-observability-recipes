#!/usr/bin/env python3
"""Generate an auditable SLO error-budget ledger from replay output."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_summary(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, list):
        raise ValueError("summary must be a JSON list")
    return data


def target_percent(openslo_policy: dict[str, Any]) -> float:
    return float(openslo_policy["openslo"]["target"])


def allowed_bad_fraction(target: float) -> float:
    return max(0.0, round((100.0 - target) / 100.0, 6))


def required_scenarios(openslo_policy: dict[str, Any]) -> set[str]:
    return set(openslo_policy.get("required_scenarios", []))


def latency_bad_events(item: dict[str, Any], slo_config: dict[str, Any]) -> int:
    """Estimate replay requests outside the baseline latency envelope.

    The incident summary intentionally stores compact p95 evidence rather than
    every raw latency sample. The estimate is conservative and transparent:
    the farther p95 is above the baseline threshold, the larger the replay
    budget pressure.
    """

    threshold = int(slo_config["scenarios"]["baseline"]["max_p95_ms"])
    p95_ms = int(item["p95_ms"])
    if p95_ms <= threshold:
        return 0
    requests = int(item["requests"])
    pressure = min(1.0, (p95_ms - threshold) / max(1, p95_ms))
    return min(requests, math.ceil(requests * pressure))


def telemetry_bad_events(item: dict[str, Any]) -> int:
    requests = int(item["requests"])
    loss_rate = float(item.get("telemetry_loss_rate", 0.0))
    if loss_rate <= 0:
        return 0
    return min(requests, math.ceil(requests * loss_rate))


def classify(consumed_ratio: float, policy: dict[str, Any]) -> str:
    thresholds = policy["classification"]
    if consumed_ratio <= float(thresholds["healthy_max_consumed_ratio"]):
        return "within_budget"
    if consumed_ratio <= float(thresholds["review_max_consumed_ratio"]):
        return "manual_review_required"
    return "budget_exhausted"


def build_ledger(
    summary: list[dict[str, Any]],
    slo_config: dict[str, Any],
    openslo_policy: dict[str, Any],
    error_budget_policy: dict[str, Any],
) -> dict[str, Any]:
    target = target_percent(openslo_policy)
    bad_fraction = allowed_bad_fraction(target)
    actions = dict(error_budget_policy["release_actions"])
    minimum_budget_events = int(error_budget_policy["minimum_budget_events"])
    required = required_scenarios(openslo_policy)
    observed = {str(item["scenario"]) for item in summary}
    baseline_name = str(error_budget_policy["baseline_scenario"])

    ledger = []
    for item in summary:
        requests = int(item["requests"])
        allowed_events = max(minimum_budget_events, math.ceil(requests * bad_fraction))
        errors = int(item["errors"])
        latency = latency_bad_events(item, slo_config)
        telemetry = telemetry_bad_events(item)
        used_events = errors + latency + telemetry
        consumed_ratio = round(used_events / max(1, allowed_events), 2)
        decision = classify(consumed_ratio, error_budget_policy)
        ledger.append(
            {
                "scenario": item["scenario"],
                "description": item.get("description", ""),
                "requests": requests,
                "allowed_bad_events": allowed_events,
                "budget_used_events": used_events,
                "budget_remaining_events": allowed_events - used_events,
                "consumed_ratio": consumed_ratio,
                "decision": decision,
                "release_action": actions.get(decision, "unmapped"),
                "bad_event_sources": {
                    "errors": errors,
                    "latency_budget_pressure": latency,
                    "telemetry_delivery_loss": telemetry,
                },
                "signals": {
                    "p95_ms": item["p95_ms"],
                    "error_rate": item["error_rate"],
                    "telemetry_loss_rate": item.get("telemetry_loss_rate", 0.0),
                    "service_version": item.get("service_version", "unknown"),
                },
            }
        )

    by_name = {str(item["scenario"]): item for item in ledger}
    missing = sorted(required - observed)
    baseline = by_name.get(baseline_name)
    incident_rows = [item for item in ledger if str(item["scenario"]) != baseline_name]
    checks = [
        {
            "name": "objective_target",
            "ok": target >= float(error_budget_policy["minimum_target_percent"]) and bad_fraction > 0,
            "evidence": {
                "target_percent": target,
                "allowed_bad_fraction": bad_fraction,
            },
        },
        {
            "name": "scenario_coverage",
            "ok": len(summary) >= int(error_budget_policy["minimum_scenarios"]) and not missing,
            "evidence": {
                "observed": sorted(observed),
                "required": sorted(required),
                "missing": missing,
            },
        },
        {
            "name": "baseline_within_budget",
            "ok": bool(baseline)
            and baseline["decision"] == "within_budget"
            and int(baseline["budget_used_events"]) == 0,
            "evidence": baseline or {},
        },
        {
            "name": "incident_budget_pressure",
            "ok": len(incident_rows) >= 4
            and all(item["decision"] != "within_budget" for item in incident_rows),
            "evidence": {
                "non_green_scenarios": [
                    item["scenario"]
                    for item in incident_rows
                    if item["decision"] != "within_budget"
                ]
            },
        },
        {
            "name": "release_action_mapping",
            "ok": all(item["decision"] in actions and item["release_action"] != "unmapped" for item in ledger),
            "evidence": actions,
        },
        {
            "name": "math_consistency",
            "ok": all(
                int(item["budget_used_events"]) == sum(int(value) for value in item["bad_event_sources"].values())
                for item in ledger
            ),
            "evidence": {"ledger_rows": len(ledger)},
        },
    ]
    counts: dict[str, int] = {}
    for item in ledger:
        counts[str(item["decision"])] = counts.get(str(item["decision"]), 0) + 1
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "objective": {
            "target_percent": target,
            "time_window": openslo_policy["openslo"]["time_window"],
            "budgeting_method": openslo_policy["openslo"]["budgeting_method"],
            "allowed_bad_fraction": bad_fraction,
            "latency_threshold_ms": slo_config["scenarios"]["baseline"]["max_p95_ms"],
        },
        "scenario_count": len(ledger),
        "non_green_count": sum(1 for item in ledger if item["decision"] != "within_budget"),
        "decision_counts": counts,
        "failed_count": failed_count,
        "ledger": ledger,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "error-budget-ledger.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    objective = report["objective"]
    lines = [
        "# Error Budget Ledger",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This ledger turns the OpenSLO objective into a replay-level budget",
        "accounting artifact. It estimates which scenarios stay inside budget,",
        "which need manual SRE review, and which should block a rollout or",
        "trigger rollback before production promotion.",
        "",
        "## Objective",
        "",
        f"- Target: `{objective['target_percent']}%`",
        f"- Time window: `{objective['time_window']}`",
        f"- Budgeting method: `{objective['budgeting_method']}`",
        f"- Allowed bad-event fraction: `{objective['allowed_bad_fraction']}`",
        f"- Latency envelope: `p95 <= {objective['latency_threshold_ms']} ms`",
        "",
        "## Ledger",
        "",
        "| Scenario | Allowed | Used | Ratio | Decision | Release action | Sources |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for item in report["ledger"]:
        sources = item["bad_event_sources"]
        source_text = (
            f"errors={sources['errors']}, "
            f"latency={sources['latency_budget_pressure']}, "
            f"telemetry={sources['telemetry_delivery_loss']}"
        )
        lines.append(
            "| `{scenario}` | {allowed_bad_events} | {budget_used_events} | {consumed_ratio} | `{decision}` | `{release_action}` | {sources} |".format(
                sources=source_text,
                **item,
            )
        )

    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    (output_dir / "error-budget-ledger.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--slo-config", default="config/reliability-slo.json")
    parser.add_argument("--openslo-policy", default="config/openslo-policy.json")
    parser.add_argument("--error-budget-policy", default="config/error-budget-policy.json")
    parser.add_argument("--output-dir", default="out/error-budget-ledger")
    args = parser.parse_args()

    report = build_ledger(
        load_summary(Path(args.summary)),
        load_json(Path(args.slo_config)),
        load_json(Path(args.openslo_policy)),
        load_json(Path(args.error_budget_policy)),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'error-budget-ledger.json'}")
    print(f"wrote {output_dir / 'error-budget-ledger.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
