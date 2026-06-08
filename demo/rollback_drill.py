#!/usr/bin/env python3
"""Generate rollback drill evidence from release and incident artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def by_key(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(item[key]): item for item in items}


def rollback_required(ledger_item: dict[str, Any]) -> bool:
    return str(ledger_item.get("release_action")) == "block_release_or_rollback"


def manual_review_required(ledger_item: dict[str, Any]) -> bool:
    return str(ledger_item.get("release_action")) == "require_sre_review_before_rollout"


def build_timeline(step_policy: dict[str, Any]) -> list[dict[str, Any]]:
    ack = int(step_policy["ack_minutes"])
    mitigated = ack + int(step_policy["mitigate_minutes"])
    verified = mitigated + int(step_policy["verify_minutes"])
    return [
        {
            "minute": 0,
            "phase": "detect",
            "action": "alert fires or release gate blocks promotion from generated evidence",
        },
        {
            "minute": ack,
            "phase": "acknowledge",
            "action": "incident commander assigns scenario owner and freezes rollout expansion",
        },
        {
            "minute": mitigated,
            "phase": "mitigate",
            "action": step_policy["primary_action"],
        },
        {
            "minute": verified,
            "phase": "verify",
            "action": "re-run evidence generation and confirm SLO budget, alerts, dashboard, and runbook status",
        },
    ]


def build_drills(
    *,
    summary: list[dict[str, Any]],
    runbooks: dict[str, Any],
    deployment_policy: dict[str, Any],
    error_budget: dict[str, Any],
    drill_policy: dict[str, Any],
) -> dict[str, Any]:
    summary_by_name = by_key(summary, "scenario")
    runbook_by_name = by_key(runbooks.get("runbooks", []), "scenario")
    ledger_by_name = by_key(error_budget.get("ledger", []), "scenario")
    roles = drill_policy["roles"]
    drills = []
    for scenario, step_policy in drill_policy["scenario_steps"].items():
        ledger_item = ledger_by_name.get(scenario)
        summary_item = summary_by_name.get(scenario)
        runbook = runbook_by_name.get(scenario)
        owner_role = str(step_policy["owner_role"])
        timeline = build_timeline(step_policy)
        completion_minutes = max(item["minute"] for item in timeline)
        response_type = "manual_review"
        if ledger_item and rollback_required(ledger_item):
            response_type = "rollback_required"
        elif ledger_item and manual_review_required(ledger_item):
            response_type = "manual_review"
        drills.append(
            {
                "scenario": scenario,
                "response_type": response_type,
                "owner_role": owner_role,
                "owner": roles.get(owner_role, "unassigned"),
                "rto_minutes": int(drill_policy["rto_minutes"]),
                "rpo_minutes": int(drill_policy["rpo_minutes"]),
                "completion_minutes": completion_minutes,
                "within_rto": completion_minutes <= int(drill_policy["rto_minutes"]),
                "release_action": ledger_item.get("release_action") if ledger_item else "missing",
                "budget_decision": ledger_item.get("decision") if ledger_item else "missing",
                "runbook_owner": runbook.get("owner") if runbook else "missing",
                "signals": {
                    "p95_ms": summary_item.get("p95_ms") if summary_item else None,
                    "error_rate": summary_item.get("error_rate") if summary_item else None,
                    "telemetry_loss_rate": summary_item.get("telemetry_loss_rate") if summary_item else None,
                    "service_version": summary_item.get("service_version") if summary_item else None,
                },
                "timeline": timeline,
            }
        )

    configured = set(drill_policy["scenario_steps"])
    missing_summary = sorted(configured - set(summary_by_name))
    missing_runbooks = sorted(configured - set(runbook_by_name))
    missing_budget = sorted(configured - set(ledger_by_name))
    missing_owners = sorted({item["owner_role"] for item in drills if item["owner"] == "unassigned"})
    rollback_drills = [item for item in drills if item["response_type"] == "rollback_required"]
    manual_review_drills = [item for item in drills if item["response_type"] == "manual_review"]
    checks = [
        {
            "name": "scenario_coverage",
            "ok": len(drills) >= int(drill_policy["minimum_drills"])
            and not missing_summary
            and not missing_budget,
            "evidence": {
                "configured": sorted(configured),
                "missing_summary": missing_summary,
                "missing_budget": missing_budget,
            },
        },
        {
            "name": "runbook_linkage",
            "ok": not missing_runbooks,
            "evidence": {"missing_runbooks": missing_runbooks},
        },
        {
            "name": "rollback_path",
            "ok": len(rollback_drills) >= int(drill_policy["minimum_rollback_required"]),
            "evidence": {"rollback_required": [item["scenario"] for item in rollback_drills]},
        },
        {
            "name": "manual_review_path",
            "ok": len(manual_review_drills) >= 1,
            "evidence": {"manual_review": [item["scenario"] for item in manual_review_drills]},
        },
        {
            "name": "rto_coverage",
            "ok": all(item["within_rto"] for item in drills),
            "evidence": {
                "rto_minutes": drill_policy["rto_minutes"],
                "completion_minutes": {
                    item["scenario"]: item["completion_minutes"]
                    for item in drills
                },
            },
        },
        {
            "name": "owner_coverage",
            "ok": not missing_owners,
            "evidence": {"missing_owner_roles": missing_owners},
        },
        {
            "name": "release_policy_linkage",
            "ok": deployment_policy.get("decision")
            in {"block_production_promotion", "manual_review_required", "promote"}
            and error_budget.get("status") == PASS,
            "evidence": {
                "deployment_decision": deployment_policy.get("decision"),
                "error_budget_status": error_budget.get("status"),
            },
        },
    ]
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "rto_minutes": drill_policy["rto_minutes"],
        "rpo_minutes": drill_policy["rpo_minutes"],
        "deployment_decision": deployment_policy.get("decision"),
        "drill_count": len(drills),
        "rollback_required_count": len(rollback_drills),
        "manual_review_count": len(manual_review_drills),
        "failed_count": failed_count,
        "required_evidence": drill_policy.get("required_evidence", []),
        "drills": drills,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "rollback-drill.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Rollback Drill Evidence",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This report turns the release gate, error-budget ledger, and generated",
        "runbooks into an incident-response drill. It checks whether the lab has",
        "named owners, rollback/manual-review paths, and an RTO-bounded timeline",
        "for each non-healthy replay scenario.",
        "",
        "## Summary",
        "",
        f"- Deployment decision: `{report['deployment_decision']}`",
        f"- RTO: `{report['rto_minutes']} minutes`",
        f"- RPO: `{report['rpo_minutes']} minutes`",
        f"- Drills: `{report['drill_count']}`",
        f"- Rollback required: `{report['rollback_required_count']}`",
        f"- Manual review: `{report['manual_review_count']}`",
        "",
        "## Drills",
        "",
        "| Scenario | Response | Owner | Complete by | Within RTO | Release action |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in report["drills"]:
        lines.append(
            "| `{scenario}` | `{response_type}` | {owner} | {completion_minutes}m | {within_rto} | `{release_action}` |".format(
                **item
            )
        )
    lines.extend(["", "## Timeline Detail", ""])
    for item in report["drills"]:
        lines.extend([f"### {item['scenario']}", ""])
        for step in item["timeline"]:
            lines.append(f"- T+{step['minute']}m `{step['phase']}`: {step['action']}")
        lines.append("")
    lines.extend(["## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    (output_dir / "rollback-drill.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="out/incident-replay/summary.json")
    parser.add_argument("--runbooks", default="out/incident-runbooks/incident-runbooks.json")
    parser.add_argument("--deployment-policy", default="out/deployment-policy/deployment-policy.json")
    parser.add_argument("--error-budget", default="out/error-budget-ledger/error-budget-ledger.json")
    parser.add_argument("--drill-policy", default="config/rollback-drill-policy.json")
    parser.add_argument("--output-dir", default="out/rollback-drill")
    args = parser.parse_args()

    report = build_drills(
        summary=load_json(Path(args.summary)),
        runbooks=load_json(Path(args.runbooks)),
        deployment_policy=load_json(Path(args.deployment_policy)),
        error_budget=load_json(Path(args.error_budget)),
        drill_policy=load_json(Path(args.drill_policy)),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'rollback-drill.json'}")
    print(f"wrote {output_dir / 'rollback-drill.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
