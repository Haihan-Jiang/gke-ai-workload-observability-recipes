#!/usr/bin/env python3
"""Generate post-incident review packets from replayed reliability evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def by_scenario(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["scenario"]): item for item in items}


def severity_for(response_type: str, policy: dict[str, Any]) -> str:
    return str(policy["severity_by_response"].get(response_type, "SEV-3"))


def impact(summary_item: dict[str, Any], ledger_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "requests": summary_item["requests"],
        "p95_ms": summary_item["p95_ms"],
        "error_rate": summary_item["error_rate"],
        "telemetry_loss_rate": summary_item.get("telemetry_loss_rate", 0.0),
        "budget_used_events": ledger_item["budget_used_events"],
        "budget_remaining_events": ledger_item["budget_remaining_events"],
        "release_action": ledger_item["release_action"],
    }


def build_action_items(scenario: str, owner: str, policy: dict[str, Any]) -> list[dict[str, Any]]:
    templates = policy["corrective_actions"].get(scenario, [])
    return [
        {
            "id": f"{scenario}-A{index + 1}",
            "owner": owner,
            "due_days": 7 if index == 0 else 14,
            "action": action,
        }
        for index, action in enumerate(templates)
    ]


def build_reviews(
    *,
    summary: list[dict[str, Any]],
    incident_correlation: dict[str, Any],
    rollback_drill: dict[str, Any],
    error_budget: dict[str, Any],
    deployment_policy: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    summary_by_name = by_scenario(summary)
    correlation_by_name = by_scenario(incident_correlation.get("incidents", []))
    drill_by_name = by_scenario(rollback_drill.get("drills", []))
    ledger_by_name = by_scenario(error_budget.get("ledger", []))
    reviews = []
    for scenario, drill in drill_by_name.items():
        summary_item = summary_by_name.get(scenario, {})
        correlation = correlation_by_name.get(scenario, {})
        ledger_item = ledger_by_name.get(scenario, {})
        owner = policy["owners"].get(scenario, drill.get("owner", "unassigned"))
        reviews.append(
            {
                "scenario": scenario,
                "severity": severity_for(str(drill.get("response_type")), policy),
                "owner": owner,
                "status": "review_ready",
                "impact": impact(summary_item, ledger_item),
                "root_cause": {
                    "category": correlation.get("root_cause", "unknown"),
                    "dedupe_key": correlation.get("dedupe_key", "unknown"),
                    "symptoms": correlation.get("symptoms", []),
                },
                "timeline": drill.get("timeline", []),
                "corrective_actions": build_action_items(scenario, owner, policy),
                "preventive_controls": policy.get("preventive_controls", []),
            }
        )

    checks = evaluate(reviews, deployment_policy, error_budget, rollback_drill, policy)
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "review_count": len(reviews),
        "action_item_count": sum(len(item["corrective_actions"]) for item in reviews),
        "preventive_control_count": len(policy.get("preventive_controls", [])),
        "deployment_decision": deployment_policy.get("decision"),
        "failed_count": failed_count,
        "reviews": reviews,
        "checks": checks,
    }


def evaluate(
    reviews: list[dict[str, Any]],
    deployment_policy: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    required_sections = set(policy.get("required_sections", []))
    review_scenarios = {item["scenario"] for item in reviews}
    rollback_scenarios = {
        item["scenario"]
        for item in rollback_drill.get("drills", [])
        if item.get("response_type") == "rollback_required"
    }
    budget_review_scenarios = {
        item["scenario"]
        for item in error_budget.get("ledger", [])
        if item.get("decision") != "within_budget"
    }
    action_items = [
        action
        for review in reviews
        for action in review.get("corrective_actions", [])
    ]
    return [
        {
            "name": "review_coverage",
            "ok": len(reviews) >= int(policy["minimum_reviews"])
            and review_scenarios >= rollback_scenarios
            and review_scenarios >= budget_review_scenarios,
            "evidence": {
                "reviews": sorted(review_scenarios),
                "rollback_scenarios": sorted(rollback_scenarios),
                "budget_review_scenarios": sorted(budget_review_scenarios),
            },
        },
        {
            "name": "required_sections",
            "ok": all(required_sections <= set(review) for review in reviews),
            "evidence": {"required": sorted(required_sections)},
        },
        {
            "name": "action_item_coverage",
            "ok": len(action_items) >= int(policy["minimum_action_items"])
            and all(item.get("owner") and item.get("due_days") for item in action_items),
            "evidence": {"action_items": len(action_items)},
        },
        {
            "name": "preventive_control_coverage",
            "ok": len(policy.get("preventive_controls", [])) >= int(policy["minimum_preventive_controls"]),
            "evidence": {"preventive_controls": policy.get("preventive_controls", [])},
        },
        {
            "name": "release_evidence_linkage",
            "ok": deployment_policy.get("decision") in {"block_production_promotion", "manual_review_required", "promote"}
            and error_budget.get("status") == PASS
            and rollback_drill.get("status") == PASS,
            "evidence": {
                "deployment_decision": deployment_policy.get("decision"),
                "error_budget_status": error_budget.get("status"),
                "rollback_drill_status": rollback_drill.get("status"),
            },
        },
        {
            "name": "severity_assignment",
            "ok": all(item.get("severity") in {"SEV-1", "SEV-2", "SEV-3"} for item in reviews),
            "evidence": {
                "severities": {
                    item["scenario"]: item.get("severity")
                    for item in reviews
                }
            },
        },
    ]


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "post-incident-review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Post-Incident Review Packet",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This packet turns replayed reliability incidents into review-ready RCA",
        "records. It ties customer-impact signals, root-cause grouping, rollback",
        "timelines, corrective actions, and preventive controls back to the",
        "generated release evidence.",
        "",
        "## Summary",
        "",
        f"- Deployment decision: `{report['deployment_decision']}`",
        f"- Reviews: `{report['review_count']}`",
        f"- Corrective actions: `{report['action_item_count']}`",
        f"- Preventive controls: `{report['preventive_control_count']}`",
        "",
        "## Reviews",
        "",
    ]
    for review in report["reviews"]:
        impact_data = review["impact"]
        root = review["root_cause"]
        lines.extend(
            [
                f"### {review['scenario']}",
                "",
                f"- Severity: `{review['severity']}`",
                f"- Owner: {review['owner']}",
                f"- Root cause: `{root['category']}`",
                f"- Dedupe key: `{root['dedupe_key']}`",
                f"- Budget used events: `{impact_data['budget_used_events']}`",
                f"- Release action: `{impact_data['release_action']}`",
                "",
                "Corrective actions:",
            ]
        )
        for action in review["corrective_actions"]:
            lines.append(f"- `{action['id']}` {action['action']} Owner: {action['owner']}; due: {action['due_days']}d")
        lines.extend(["", "Timeline:"])
        for step in review["timeline"]:
            lines.append(f"- T+{step['minute']}m `{step['phase']}`: {step['action']}")
        lines.append("")
    lines.extend(["## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    (output_dir / "post-incident-review.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--incident-correlation", default="out/advanced-reliability/incident-correlation.json")
    parser.add_argument("--rollback-drill", default="out/rollback-drill/rollback-drill.json")
    parser.add_argument("--error-budget", default="out/error-budget-ledger/error-budget-ledger.json")
    parser.add_argument("--deployment-policy", default="out/deployment-policy/deployment-policy.json")
    parser.add_argument("--policy", default="config/post-incident-review-policy.json")
    parser.add_argument("--output-dir", default="out/post-incident-review")
    args = parser.parse_args()

    report = build_reviews(
        summary=load_json(Path(args.summary)),
        incident_correlation=load_json(Path(args.incident_correlation)),
        rollback_drill=load_json(Path(args.rollback_drill)),
        error_budget=load_json(Path(args.error_budget)),
        deployment_policy=load_json(Path(args.deployment_policy)),
        policy=load_json(Path(args.policy)),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'post-incident-review.json'}")
    print(f"wrote {output_dir / 'post-incident-review.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
