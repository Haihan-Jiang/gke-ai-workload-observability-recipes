#!/usr/bin/env python3
"""Audit release exception requests against reliability evidence."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
CONDITIONALLY_APPROVED = "conditionally_approved"
DENIED = "denied_override"
INVALID = "invalid_request"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def by_scenario(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["scenario"]): item for item in items}


def check(name: str, ok: bool, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "status": PASS if ok else FAIL,
        "reason": reason,
        "evidence": evidence,
    }


def missing_required_fields(waiver: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    missing = []
    for field in policy.get("required_fields", []):
        value = waiver.get(field)
        if value is None or value == "" or value == [] or value == {}:
            missing.append(str(field))
    return missing


def duration_days(waiver: dict[str, Any]) -> float:
    created = parse_time(str(waiver["created_at"]))
    expires = parse_time(str(waiver["expires_at"]))
    return round((expires - created).total_seconds() / 86400, 2)


def waiver_active(waiver: dict[str, Any], policy: dict[str, Any]) -> bool:
    reference = parse_time(str(policy["audit_reference_time"]))
    created = parse_time(str(waiver["created_at"]))
    expires = parse_time(str(waiver["expires_at"]))
    return created <= reference < expires


def linked_evidence_ok(waiver: dict[str, Any], policy: dict[str, Any]) -> bool:
    linked = set(waiver.get("linked_evidence", []))
    return linked >= set(policy.get("required_linked_evidence", []))


def owner_approvals_ok(waiver: dict[str, Any], policy: dict[str, Any]) -> bool:
    approvers = [str(item) for item in waiver.get("approvers", [])]
    return (
        len(set(approvers)) >= int(policy["minimum_approvers"])
        and str(waiver.get("requested_by")) not in set(approvers)
    )


def budget_acknowledged(waiver: dict[str, Any], ledger_item: dict[str, Any]) -> bool:
    acknowledgement = waiver.get("budget_acknowledgement", {})
    return (
        float(acknowledgement.get("consumed_ratio", -1)) >= float(ledger_item.get("consumed_ratio", 0))
        and int(acknowledgement.get("budget_used_events", -1)) >= int(ledger_item.get("budget_used_events", 0))
    )


def scenario_linkage_ok(
    waiver: dict[str, Any],
    ledger_item: dict[str, Any],
    rollback_drills: dict[str, dict[str, Any]],
    post_incident_reviews: dict[str, dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    scenario = str(waiver.get("scenario"))
    rollback_name = str(waiver.get("rollback_drill", ""))
    review_name = str(waiver.get("post_incident_review", ""))
    release_action = str(waiver.get("release_action", ""))
    return (
        scenario in rollback_drills
        and scenario in post_incident_reviews
        and rollback_name == scenario
        and review_name == scenario
        and release_action == str(ledger_item.get("release_action")),
        {
            "scenario": scenario,
            "rollback_drill": rollback_name,
            "post_incident_review": review_name,
            "release_action": release_action,
            "ledger_release_action": ledger_item.get("release_action"),
        },
    )


def evaluate_waiver(
    waiver: dict[str, Any],
    *,
    policy: dict[str, Any],
    ledger: dict[str, dict[str, Any]],
    rollback_drills: dict[str, dict[str, Any]],
    post_incident_reviews: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    scenario = str(waiver.get("scenario", ""))
    ledger_item = ledger.get(scenario, {})
    linkage_ok, linkage_evidence = scenario_linkage_ok(
        waiver,
        ledger_item,
        rollback_drills,
        post_incident_reviews,
    ) if ledger_item else (False, {"scenario": scenario})
    field_missing = missing_required_fields(waiver, policy)
    waiver_checks = [
        check(
            "required_fields",
            not field_missing,
            "Waiver request includes the required governance fields.",
            {"missing": field_missing},
        ),
        check(
            "known_scenario",
            bool(ledger_item) and str(ledger_item.get("decision")) != "within_budget",
            "Waiver is tied to a non-green error-budget scenario.",
            {"scenario": scenario, "ledger_decision": ledger_item.get("decision")},
        ),
        check(
            "owner_approvals",
            owner_approvals_ok(waiver, policy),
            "Waiver has enough distinct approvers and no self-approval.",
            {"requested_by": waiver.get("requested_by"), "approvers": waiver.get("approvers", [])},
        ),
        check(
            "validity_window",
            bool(ledger_item)
            and waiver_active(waiver, policy)
            and duration_days(waiver) <= float(policy["max_valid_days"]),
            "Waiver is active at the audit reference time and expires inside the maximum duration.",
            {
                "created_at": waiver.get("created_at"),
                "expires_at": waiver.get("expires_at"),
                "duration_days": duration_days(waiver) if "created_at" in waiver and "expires_at" in waiver else None,
                "audit_reference_time": policy.get("audit_reference_time"),
            },
        ),
        check(
            "evidence_linkage",
            linked_evidence_ok(waiver, policy),
            "Waiver links the required release, budget, rollback, RCA, and readiness evidence.",
            {"linked_evidence": waiver.get("linked_evidence", [])},
        ),
        check(
            "scenario_linkage",
            linkage_ok,
            "Waiver scenario matches rollback drill, post-incident review, and release action evidence.",
            linkage_evidence,
        ),
        check(
            "budget_acknowledgement",
            bool(ledger_item) and budget_acknowledged(waiver, ledger_item),
            "Waiver acknowledges at least the replayed budget consumption.",
            {
                "waiver": waiver.get("budget_acknowledgement", {}),
                "ledger": {
                    "consumed_ratio": ledger_item.get("consumed_ratio"),
                    "budget_used_events": ledger_item.get("budget_used_events"),
                },
            },
        ),
    ]
    failed = [item["name"] for item in waiver_checks if item["status"] != PASS]
    ledger_decision = str(ledger_item.get("decision", "unknown"))
    if failed:
        decision = INVALID
    elif ledger_decision in set(policy.get("deny_override_decisions", [])):
        decision = DENIED
    elif ledger_decision in set(policy.get("manual_review_decisions", [])) and int(waiver.get("max_traffic_percent", 101)) <= int(policy["max_manual_review_traffic_percent"]):
        decision = CONDITIONALLY_APPROVED
    else:
        decision = INVALID
    return {
        "id": waiver.get("id"),
        "scenario": scenario,
        "ledger_decision": ledger_decision,
        "release_action": ledger_item.get("release_action"),
        "decision": decision,
        "failed_checks": failed,
        "checks": waiver_checks,
    }


def mutate_waiver(base: dict[str, Any], mutation: str) -> dict[str, Any]:
    waiver = copy.deepcopy(base)
    if mutation == "expired":
        waiver["expires_at"] = "2026-06-01T11:00:00Z"
    elif mutation == "missing_approver":
        waiver["approvers"] = ["sre_lead"]
    elif mutation == "missing_evidence":
        waiver["linked_evidence"] = ["docs/evidence/deployment-policy.json"]
    elif mutation == "missing_rollback_link":
        waiver["rollback_drill"] = "wrong_scenario"
    elif mutation == "missing_review_link":
        waiver["post_incident_review"] = "wrong_scenario"
    elif mutation == "excessive_duration":
        waiver["expires_at"] = "2026-07-15T16:00:00Z"
    elif mutation == "understated_budget":
        waiver["budget_acknowledgement"] = {"consumed_ratio": 0.5, "budget_used_events": 1}
    elif mutation == "unknown_scenario":
        waiver["scenario"] = "unknown_scenario"
        waiver["rollback_drill"] = "unknown_scenario"
        waiver["post_incident_review"] = "unknown_scenario"
    else:
        raise ValueError(f"unknown mutation: {mutation}")
    waiver["id"] = f"{base['id']}-{mutation}"
    return waiver


def build_report(
    *,
    policy: dict[str, Any],
    waivers: dict[str, Any],
    deployment_policy: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    post_incident_review: dict[str, Any],
) -> dict[str, Any]:
    ledger = by_scenario(error_budget.get("ledger", []))
    rollback_drills = by_scenario(rollback_drill.get("drills", []))
    post_incident_reviews = by_scenario(post_incident_review.get("reviews", []))
    waiver_items = list(waivers.get("waivers", []))
    decisions = [
        evaluate_waiver(
            waiver,
            policy=policy,
            ledger=ledger,
            rollback_drills=rollback_drills,
            post_incident_reviews=post_incident_reviews,
        )
        for waiver in waiver_items
    ]
    base_for_fixtures = waiver_items[0]
    fixture_decisions = [
        {
            "fixture": mutation,
            **evaluate_waiver(
                mutate_waiver(base_for_fixtures, mutation),
                policy=policy,
                ledger=ledger,
                rollback_drills=rollback_drills,
                post_incident_reviews=post_incident_reviews,
            ),
        }
        for mutation in policy.get("fixture_mutations", [])
    ]
    conditional = [item for item in decisions if item["decision"] == CONDITIONALLY_APPROVED]
    denied = [item for item in decisions if item["decision"] == DENIED]
    invalid = [item for item in decisions if item["decision"] == INVALID]
    unsafe_approved = [
        item
        for item in decisions
        if item["ledger_decision"] in set(policy.get("deny_override_decisions", []))
        and item["decision"] == CONDITIONALLY_APPROVED
    ]
    failed_fixtures = [item for item in fixture_decisions if item["decision"] != INVALID]
    checks = [
        check(
            "waiver_coverage",
            len(decisions) >= int(policy["minimum_waivers"]),
            "Waiver register covers the non-green replay scenarios.",
            {"waiver_count": len(decisions)},
        ),
        check(
            "conditional_approval_path",
            len(conditional) >= int(policy["minimum_conditional_approvals"]),
            "Manual-review scenarios have limited conditional approvals.",
            {"conditional_approvals": [item["scenario"] for item in conditional]},
        ),
        check(
            "deny_override_path",
            len(denied) >= int(policy["minimum_denied_overrides"]),
            "Budget-exhausted scenarios deny production-promotion overrides.",
            {"denied_overrides": [item["scenario"] for item in denied]},
        ),
        check(
            "no_invalid_waivers",
            not invalid,
            "Configured waiver requests satisfy metadata, linkage, expiry, and budget acknowledgement checks.",
            {"invalid": [item["id"] for item in invalid]},
        ),
        check(
            "no_unsafe_approvals",
            not unsafe_approved,
            "Budget-exhausted scenarios are never conditionally approved for production promotion.",
            {"unsafe_approved": [item["id"] for item in unsafe_approved]},
        ),
        check(
            "negative_fixture_coverage",
            len(fixture_decisions) >= len(policy.get("fixture_mutations", [])) and not failed_fixtures,
            "Negative fixtures become invalid waiver requests.",
            {"failed_fixtures": [item["fixture"] for item in failed_fixtures]},
        ),
        check(
            "release_policy_linkage",
            deployment_policy.get("human_approval_required") is True
            and deployment_policy.get("decision") in {"block_production_promotion", "manual_review_required"},
            "Waiver governance only activates when release evidence requires human approval.",
            {
                "deployment_decision": deployment_policy.get("decision"),
                "human_approval_required": deployment_policy.get("human_approval_required"),
            },
        ),
    ]
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "deployment_decision": deployment_policy.get("decision"),
        "waiver_count": len(decisions),
        "conditional_approval_count": len(conditional),
        "denied_override_count": len(denied),
        "invalid_waiver_count": len(invalid),
        "unsafe_approved_count": len(unsafe_approved),
        "fixture_count": len(fixture_decisions),
        "failed_count": failed_count,
        "decisions": decisions,
        "fixture_decisions": fixture_decisions,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "release-waiver-governance.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Release Waiver Governance",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks release exception requests against generated",
        "deployment, error-budget, rollback, and post-incident evidence. It",
        "allows only bounded manual-review exceptions and denies",
        "production-promotion overrides for budget-exhausted scenarios.",
        "",
        "## Summary",
        "",
        f"- Deployment decision: `{report['deployment_decision']}`",
        f"- Waivers: `{report['waiver_count']}`",
        f"- Conditional approvals: `{report['conditional_approval_count']}`",
        f"- Denied overrides: `{report['denied_override_count']}`",
        f"- Invalid waivers: `{report['invalid_waiver_count']}`",
        f"- Unsafe approvals: `{report['unsafe_approved_count']}`",
        "",
        "## Waiver Decisions",
        "",
        "| Waiver | Scenario | Ledger decision | Governance decision | Failed checks |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["decisions"]:
        failed = ", ".join(item["failed_checks"]) or "-"
        lines.append(
            f"| `{item['id']}` | `{item['scenario']}` | `{item['ledger_decision']}` | `{item['decision']}` | {failed} |"
        )
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Decision | Failed checks |", "| --- | --- | --- |"])
    for item in report["fixture_decisions"]:
        failed = ", ".join(item["failed_checks"]) or "-"
        lines.append(f"| `{item['fixture']}` | `{item['decision']}` | {failed} |")
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {item['status'].upper()} |")
    lines.append("")
    (output_dir / "release-waiver-governance.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/release-waiver-policy.json")
    parser.add_argument("--waivers", default="config/release-waivers.json")
    parser.add_argument("--deployment-policy", default="docs/evidence/deployment-policy.json")
    parser.add_argument("--error-budget", default="docs/evidence/error-budget-ledger.json")
    parser.add_argument("--rollback-drill", default="docs/evidence/rollback-drill.json")
    parser.add_argument("--post-incident-review", default="docs/evidence/post-incident-review.json")
    parser.add_argument("--output-dir", default="out/release-waiver-governance")
    args = parser.parse_args()

    report = build_report(
        policy=load_json(Path(args.policy)),
        waivers=load_json(Path(args.waivers)),
        deployment_policy=load_json(Path(args.deployment_policy)),
        error_budget=load_json(Path(args.error_budget)),
        rollback_drill=load_json(Path(args.rollback_drill)),
        post_incident_review=load_json(Path(args.post_incident_review)),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'release-waiver-governance.json'}")
    print(f"wrote {output_dir / 'release-waiver-governance.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
