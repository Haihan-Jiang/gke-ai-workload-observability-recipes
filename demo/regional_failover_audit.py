#!/usr/bin/env python3
"""Audit regional failover readiness for AI inference reliability controls."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
PROTECTIVE_ACTIONS = {
    "protect_telemetry",
    "rate_limit_retrieval",
    "rollback_canary",
    "shed_best_effort",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def by_scenario(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item["scenario"]): item
        for item in items
        if item.get("scenario")
    }


def by_name(items: list[dict[str, Any]], field: str = "name") -> dict[str, dict[str, Any]]:
    return {
        str(item[field]): item
        for item in items
        if item.get(field)
    }


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def load_shedding_by_scenario(load_shedding: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return by_scenario(load_shedding.get("actions", []))


def probe_by_scenario(synthetic_probe: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return by_scenario(synthetic_probe.get("probes", []))


def k8s_control_status(k8s_hardening: dict[str, Any]) -> dict[str, str]:
    return {
        str(item["name"]): str(item.get("status", ""))
        for item in k8s_hardening.get("checks", [])
        if item.get("name")
    }


def int_or_default(value: Any, default: int) -> int:
    if value is None:
        return default
    return int(value)


def build_events(
    *,
    policy: dict[str, Any],
    capacity: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    disaster_recovery: dict[str, Any],
    synthetic_probe: dict[str, Any],
    load_shedding: dict[str, Any],
    runbooks: dict[str, Any],
    k8s_hardening: dict[str, Any],
) -> list[dict[str, Any]]:
    capacity_by_name = by_scenario(capacity.get("scenarios", []))
    ledger_by_name = by_scenario(error_budget.get("ledger", []))
    rollback_by_name = by_scenario(rollback_drill.get("drills", []))
    probe_by_name = probe_by_scenario(synthetic_probe)
    load_shedding_by_name = load_shedding_by_scenario(load_shedding)
    runbook_by_name = by_scenario(runbooks.get("runbooks", []))
    control_status = k8s_control_status(k8s_hardening)
    events = []
    for event in policy.get("events", []):
        scenario = str(event["scenario"])
        capacity_item = capacity_by_name.get(scenario, {})
        ledger_item = ledger_by_name.get(scenario, {})
        rollback_item = rollback_by_name.get(scenario, {})
        probe_item = probe_by_name.get(scenario, {})
        shed_item = load_shedding_by_name.get(scenario, {})
        runbook = runbook_by_name.get(scenario, {})
        required_controls = list(policy.get("required_k8s_controls", [])) if event.get("requires_k8s_controls") else []
        events.append(
            {
                "name": event["name"],
                "scenario": scenario,
                "event_type": event.get("event_type"),
                "owner": event.get("owner"),
                "runbook_owner": runbook.get("owner"),
                "standby_region": event.get("standby_region"),
                "standby_replicas": event.get("standby_replicas"),
                "required_controls": required_controls,
                "control_status": {
                    control: control_status.get(control)
                    for control in required_controls
                },
                "capacity": {
                    "required_replicas": capacity_item.get("required_replicas"),
                    "max_replicas_budget": capacity.get("max_replicas_budget"),
                    "warnings": capacity_item.get("warnings", []),
                    "target_rps": capacity_item.get("target_rps"),
                },
                "budget_decision": ledger_item.get("decision"),
                "release_action": ledger_item.get("release_action"),
                "rollback": {
                    "response_type": rollback_item.get("response_type"),
                    "within_rto": rollback_item.get("within_rto"),
                    "completion_minutes": rollback_item.get("completion_minutes"),
                },
                "probe": {
                    "name": probe_item.get("name"),
                    "signal_ok": probe_item.get("signal_ok"),
                    "release_action": probe_item.get("release_action"),
                },
                "load_shedding": {
                    "traffic_action": shed_item.get("traffic_action"),
                    "release_action": shed_item.get("release_action"),
                    "protected_tiers": shed_item.get("protected_tiers", []),
                    "shed_tiers": shed_item.get("shed_tiers", []),
                },
                "disaster_recovery": {
                    "status": disaster_recovery.get("status"),
                    "estimated_restore_minutes": disaster_recovery.get("estimated_restore_minutes"),
                    "rto_minutes": disaster_recovery.get("rto_minutes"),
                    "rpo_minutes": disaster_recovery.get("rpo_minutes"),
                    "estimated_data_loss_minutes": disaster_recovery.get("estimated_data_loss_minutes"),
                    "generated_artifact_count": disaster_recovery.get("generated_artifact_count"),
                },
                "expected": {
                    "budget_decision": event.get("expected_budget_decision"),
                    "release_action": event.get("expected_release_action"),
                    "load_shedding_action": event.get("expected_load_shedding_action"),
                    "probe": event.get("expected_probe"),
                    "requires_dr": bool(event.get("requires_dr")),
                    "requires_rollback": bool(event.get("requires_rollback")),
                    "requires_k8s_controls": bool(event.get("requires_k8s_controls")),
                },
            }
        )
    return events


def evaluate_events(events: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    event_names = {item["name"] for item in events}
    event_scenarios = {item["scenario"] for item in events}
    missing_names = [
        item["name"]
        for item in policy.get("events", [])
        if item.get("name") not in event_names
    ]
    standby_regions = {str(item["standby_region"]) for item in events if item.get("standby_region")}
    dr_gaps = []
    for item in events:
        if not item["expected"]["requires_dr"]:
            continue
        dr = item["disaster_recovery"]
        if (
            dr.get("status") != "pass"
            or int_or_default(dr.get("estimated_restore_minutes"), 999999) > int_or_default(dr.get("rto_minutes"), 0)
            or int_or_default(dr.get("estimated_data_loss_minutes"), 999999) > int_or_default(dr.get("rpo_minutes"), 0)
            or int_or_default(dr.get("generated_artifact_count"), 0) < 4
        ):
            dr_gaps.append({"event": item["name"], "disaster_recovery": dr})
    capacity_gaps = []
    for item in events:
        capacity = item["capacity"]
        required = int(capacity.get("required_replicas") or 0)
        standby = int(item.get("standby_replicas") or 0)
        warnings = capacity.get("warnings", [])
        traffic_action = item["load_shedding"].get("traffic_action")
        release_action = item.get("release_action")
        if required and standby < min(required, int(capacity.get("max_replicas_budget") or required)):
            capacity_gaps.append(
                {
                    "event": item["name"],
                    "required_replicas": required,
                    "standby_replicas": standby,
                }
            )
        if warnings and (
            traffic_action not in PROTECTIVE_ACTIONS
            or release_action == "eligible_for_release"
        ):
            capacity_gaps.append(
                {
                    "event": item["name"],
                    "warnings": warnings,
                    "traffic_action": traffic_action,
                    "release_action": release_action,
                }
            )
    linkage_gaps = []
    for item in events:
        expected = item["expected"]
        if item.get("owner") != item.get("runbook_owner"):
            linkage_gaps.append(
                {
                    "event": item["name"],
                    "reason": "owner_runbook_mismatch",
                    "owner": item.get("owner"),
                    "runbook_owner": item.get("runbook_owner"),
                }
            )
        if item.get("budget_decision") != expected.get("budget_decision"):
            linkage_gaps.append(
                {
                    "event": item["name"],
                    "reason": "budget_decision_mismatch",
                    "expected": expected.get("budget_decision"),
                    "observed": item.get("budget_decision"),
                }
            )
        if item.get("release_action") != expected.get("release_action"):
            linkage_gaps.append(
                {
                    "event": item["name"],
                    "reason": "release_action_mismatch",
                    "expected": expected.get("release_action"),
                    "observed": item.get("release_action"),
                }
            )
        if item["load_shedding"].get("traffic_action") != expected.get("load_shedding_action"):
            linkage_gaps.append(
                {
                    "event": item["name"],
                    "reason": "load_shedding_action_mismatch",
                    "expected": expected.get("load_shedding_action"),
                    "observed": item["load_shedding"].get("traffic_action"),
                }
            )
        if item["probe"].get("name") != expected.get("probe") or item["probe"].get("signal_ok") is not True:
            linkage_gaps.append(
                {
                    "event": item["name"],
                    "reason": "probe_mismatch",
                    "expected": expected.get("probe"),
                    "observed": item["probe"],
                }
            )
        if item["probe"].get("release_action") != item.get("release_action"):
            linkage_gaps.append(
                {
                    "event": item["name"],
                    "reason": "probe_release_action_mismatch",
                    "probe_release_action": item["probe"].get("release_action"),
                    "release_action": item.get("release_action"),
                }
            )
    rollback_gaps = []
    k8s_gaps = []
    for item in events:
        if item["expected"]["requires_rollback"]:
            rollback = item["rollback"]
            if rollback.get("response_type") != "rollback_required" or rollback.get("within_rto") is not True:
                rollback_gaps.append({"event": item["name"], "rollback": rollback})
        if item["expected"]["requires_k8s_controls"]:
            failed_controls = [
                control
                for control, status in item["control_status"].items()
                if status != "pass"
            ]
            if failed_controls:
                k8s_gaps.append({"event": item["name"], "failed_controls": failed_controls})
    checks = [
        check(
            "failover_inventory",
            len(events) >= int(policy.get("minimum_event_count", 0))
            and not missing_names
            and len(event_scenarios) >= 5
            and len(standby_regions) >= int(policy.get("minimum_standby_region_count", 0)),
            {
                "event_count": len(events),
                "scenarios": sorted(event_scenarios),
                "standby_regions": sorted(standby_regions),
                "missing_names": missing_names,
            },
        ),
        check("dr_recovery_contract", not dr_gaps, {"gaps": dr_gaps}),
        check("capacity_failover_guard", not capacity_gaps, {"gaps": capacity_gaps}),
        check("traffic_safety_linkage", not linkage_gaps, {"gaps": linkage_gaps}),
        check(
            "rollback_observability_contract",
            not rollback_gaps and not k8s_gaps,
            {"rollback_gaps": rollback_gaps, "k8s_gaps": k8s_gaps},
        ),
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "checks": checks,
        "failed_count": sum(1 for item in checks if not item["ok"]),
        "standby_region_count": len(standby_regions),
    }


def mutate_fixture(
    *,
    policy: dict[str, Any],
    disaster_recovery: dict[str, Any],
    k8s_hardening: dict[str, Any],
    fixture: dict[str, Any],
) -> dict[str, Any]:
    mutated = {
        "policy": copy.deepcopy(policy),
        "disaster_recovery": copy.deepcopy(disaster_recovery),
        "k8s_hardening": copy.deepcopy(k8s_hardening),
    }
    events = by_name(mutated["policy"].get("events", []))
    mutation = fixture["mutation"]
    if mutation == "remove_event":
        mutated["policy"]["events"] = [
            item
            for item in mutated["policy"].get("events", [])
            if item.get("name") != fixture["event"]
        ]
    elif mutation == "set_dr_restore_minutes":
        mutated["disaster_recovery"]["estimated_restore_minutes"] = int(fixture["minutes"])
    elif mutation == "set_standby_replicas":
        events[str(fixture["event"])]["standby_replicas"] = int(fixture["standby_replicas"])
    elif mutation == "set_expected_release_action":
        events[str(fixture["event"])]["expected_release_action"] = str(fixture["expected_release_action"])
    elif mutation == "fail_k8s_control":
        control = str(fixture["control"])
        for item in mutated["k8s_hardening"].get("checks", []):
            if item.get("name") == control:
                item["status"] = "fail"
                break
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    *,
    policy: dict[str, Any],
    capacity: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    disaster_recovery: dict[str, Any],
    synthetic_probe: dict[str, Any],
    load_shedding: dict[str, Any],
    runbooks: dict[str, Any],
    k8s_hardening: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = mutate_fixture(
            policy=policy,
            disaster_recovery=disaster_recovery,
            k8s_hardening=k8s_hardening,
            fixture=fixture,
        )
        events = build_events(
            policy=mutated["policy"],
            capacity=capacity,
            error_budget=error_budget,
            rollback_drill=rollback_drill,
            disaster_recovery=mutated["disaster_recovery"],
            synthetic_probe=synthetic_probe,
            load_shedding=load_shedding,
            runbooks=runbooks,
            k8s_hardening=mutated["k8s_hardening"],
        )
        report = evaluate_events(events, mutated["policy"])
        expected_failed_check = fixture["expected_failed_check"]
        failed_checks = [item["name"] for item in report["checks"] if not item["ok"]]
        results.append(
            {
                "name": fixture["name"],
                "mutation": fixture["mutation"],
                "expected_failed_check": expected_failed_check,
                "failed_checks": failed_checks,
                "detected": expected_failed_check in failed_checks,
            }
        )
    return results


def build_report(
    *,
    policy: dict[str, Any],
    capacity: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    disaster_recovery: dict[str, Any],
    synthetic_probe: dict[str, Any],
    load_shedding: dict[str, Any],
    runbooks: dict[str, Any],
    k8s_hardening: dict[str, Any],
) -> dict[str, Any]:
    events = build_events(
        policy=policy,
        capacity=capacity,
        error_budget=error_budget,
        rollback_drill=rollback_drill,
        disaster_recovery=disaster_recovery,
        synthetic_probe=synthetic_probe,
        load_shedding=load_shedding,
        runbooks=runbooks,
        k8s_hardening=k8s_hardening,
    )
    event_report = evaluate_events(events, policy)
    fixture_results = evaluate_fixtures(
        policy=policy,
        capacity=capacity,
        error_budget=error_budget,
        rollback_drill=rollback_drill,
        disaster_recovery=disaster_recovery,
        synthetic_probe=synthetic_probe,
        load_shedding=load_shedding,
        runbooks=runbooks,
        k8s_hardening=k8s_hardening,
    )
    undetected = [item for item in fixture_results if not item["detected"]]
    checks = event_report["checks"] + [
        check(
            "negative_fixture_coverage",
            not undetected
            and len(fixture_results) >= int(policy.get("minimum_detected_fixtures", 0)),
            {
                "fixture_count": len(fixture_results),
                "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
                "undetected": [item["name"] for item in undetected],
            },
        )
    ]
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "event_count": len(events),
        "standby_region_count": event_report["standby_region_count"],
        "fixture_count": len(fixture_results),
        "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
        "failed_count": failed_count,
        "events": events,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "regional-failover-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Regional Failover Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks whether regional or zonal failover decisions are",
        "connected to disaster recovery, capacity risk, synthetic probes,",
        "load-shedding actions, runbook ownership, rollback evidence, and",
        "Kubernetes control-plane hardening.",
        "",
        "## Summary",
        "",
        f"- Events: `{report['event_count']}`",
        f"- Standby regions: `{report['standby_region_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Events",
        "",
        "| Event | Scenario | Standby region | Standby replicas | Release action |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for item in report["events"]:
        lines.append(
            "| `{name}` | `{scenario}` | `{standby_region}` | {standby_replicas} | `{release_action}` |".format(
                name=item["name"],
                scenario=item["scenario"],
                standby_region=item["standby_region"],
                standby_replicas=item["standby_replicas"],
                release_action=item["release_action"],
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Detected |", "| --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(f"| `{item['name']}` | {'yes' if item['detected'] else 'no'} |")
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "regional-failover-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/regional-failover-policy.json")
    parser.add_argument("--capacity", default="docs/evidence/capacity-plan.json")
    parser.add_argument("--error-budget", default="docs/evidence/error-budget-ledger.json")
    parser.add_argument("--rollback-drill", default="docs/evidence/rollback-drill.json")
    parser.add_argument("--disaster-recovery", default="docs/evidence/disaster-recovery-drill.json")
    parser.add_argument("--synthetic-probe", default="docs/evidence/synthetic-probe-audit.json")
    parser.add_argument("--load-shedding", default="docs/evidence/load-shedding-policy-audit.json")
    parser.add_argument("--runbooks", default="docs/evidence/incident-runbooks.json")
    parser.add_argument("--k8s-hardening", default="docs/evidence/k8s-hardening-audit.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(
        policy=load_json(Path(args.policy)),
        capacity=load_json(Path(args.capacity)),
        error_budget=load_json(Path(args.error_budget)),
        rollback_drill=load_json(Path(args.rollback_drill)),
        disaster_recovery=load_json(Path(args.disaster_recovery)),
        synthetic_probe=load_json(Path(args.synthetic_probe)),
        load_shedding=load_json(Path(args.load_shedding)),
        runbooks=load_json(Path(args.runbooks)),
        k8s_hardening=load_json(Path(args.k8s_hardening)),
    )
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'regional-failover-audit.json'}")
    print(f"wrote {output_dir / 'regional-failover-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
