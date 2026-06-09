#!/usr/bin/env python3
"""Audit graceful degradation and load-shedding policy for inference incidents."""

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


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def actions_by_scenario(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return by_scenario(policy.get("actions", []))


def synthetic_probe_by_scenario(synthetic_probe: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return by_scenario(synthetic_probe.get("probes", []))


def build_actions(
    *,
    capacity: dict[str, Any],
    tenant_blast_radius: dict[str, Any],
    token_cost: dict[str, Any],
    error_budget: dict[str, Any],
    synthetic_probe: dict[str, Any],
    runbooks: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    capacity_by_name = by_scenario(capacity.get("scenarios", []))
    tenant_by_name = by_scenario(tenant_blast_radius.get("scenarios", []))
    cost_by_name = by_scenario(token_cost.get("scenarios", []))
    ledger_by_name = by_scenario(error_budget.get("ledger", []))
    probe_by_name = synthetic_probe_by_scenario(synthetic_probe)
    runbook_by_name = by_scenario(runbooks.get("runbooks", []))
    actions = []
    for action in policy.get("actions", []):
        scenario = str(action["scenario"])
        capacity_item = capacity_by_name.get(scenario, {})
        tenant_item = tenant_by_name.get(scenario, {})
        cost_item = cost_by_name.get(scenario, {})
        ledger_item = ledger_by_name.get(scenario, {})
        probe_item = probe_by_name.get(scenario, {})
        runbook = runbook_by_name.get(scenario, {})
        actions.append(
            {
                "name": action["name"],
                "scenario": scenario,
                "traffic_action": action.get("traffic_action"),
                "owner": action.get("owner"),
                "runbook_owner": runbook.get("owner"),
                "protected_tiers": list(action.get("protected_tiers", [])),
                "shed_tiers": list(action.get("shed_tiers", [])),
                "fallback": action.get("fallback"),
                "capacity": {
                    "required_replicas": capacity_item.get("required_replicas"),
                    "max_replicas_budget": capacity.get("max_replicas_budget"),
                    "warnings": capacity_item.get("warnings", []),
                    "bottleneck": capacity_item.get("bottleneck"),
                },
                "tenant": {
                    "tier": tenant_item.get("tenant_tier"),
                    "blast_radius": tenant_item.get("blast_radius"),
                    "violations": tenant_item.get("violations", []),
                },
                "cost": {
                    "decision": cost_item.get("decision"),
                    "violations": cost_item.get("violations", []),
                    "model_variant": cost_item.get("model_variant"),
                },
                "budget_decision": ledger_item.get("decision"),
                "release_action": ledger_item.get("release_action"),
                "probe": {
                    "name": probe_item.get("name"),
                    "signal_ok": probe_item.get("signal_ok"),
                    "release_action": probe_item.get("release_action"),
                    "response_rollback_type": probe_item.get("response_rollback_type"),
                    "rollback_drill_type": probe_item.get("rollback_drill_type"),
                },
                "expected": {
                    "budget_decision": action.get("expected_budget_decision"),
                    "release_action": action.get("expected_release_action"),
                    "cost_decision": action.get("expected_cost_decision"),
                    "requires_preflight_probe": bool(action.get("requires_preflight_probe")),
                    "requires_cost_review": bool(action.get("requires_cost_review")),
                },
            }
        )
    return actions


def evaluate_actions(actions: list[dict[str, Any]], policy: dict[str, Any], capacity: dict[str, Any]) -> dict[str, Any]:
    action_scenarios = {item["scenario"] for item in actions}
    capacity_scenarios = {
        str(item["scenario"])
        for item in capacity.get("scenarios", [])
        if item.get("scenario")
    }
    missing_actions = sorted(capacity_scenarios - action_scenarios)
    protective_count = sum(1 for item in actions if item.get("traffic_action") in PROTECTIVE_ACTIONS)
    capacity_gaps = []
    for item in actions:
        capacity_item = item["capacity"]
        required = int(capacity_item.get("required_replicas") or 0)
        max_budget = int(capacity_item.get("max_replicas_budget") or 0)
        warnings = capacity_item.get("warnings", [])
        scale_risky = required > max_budget or bool(warnings)
        if scale_risky and item.get("traffic_action") not in PROTECTIVE_ACTIONS:
            capacity_gaps.append(
                {
                    "scenario": item["scenario"],
                    "required_replicas": required,
                    "max_replicas_budget": max_budget,
                    "warnings": warnings,
                    "traffic_action": item.get("traffic_action"),
                }
            )
        if scale_risky and not item.get("fallback"):
            capacity_gaps.append({"scenario": item["scenario"], "reason": "missing_fallback"})
    tenant_gaps = []
    for item in actions:
        tenant = item["tenant"]
        tier = tenant.get("tier")
        violations = tenant.get("violations") or []
        shed_tiers = set(item.get("shed_tiers", []))
        protected_tiers = set(item.get("protected_tiers", []))
        if tier and violations:
            if tier in shed_tiers:
                tenant_gaps.append(
                    {
                        "scenario": item["scenario"],
                        "tier": tier,
                        "reason": "violating_tier_is_shed",
                    }
                )
            if tier not in protected_tiers:
                tenant_gaps.append(
                    {
                        "scenario": item["scenario"],
                        "tier": tier,
                        "reason": "violating_tier_not_protected",
                    }
                )
        if item["scenario"] != "baseline" and "best_effort" not in shed_tiers:
            tenant_gaps.append(
                {
                    "scenario": item["scenario"],
                    "reason": "best_effort_not_shed_first",
                }
            )
    cost_gaps = []
    for item in actions:
        expected = item["expected"]
        cost = item["cost"]
        if cost.get("decision") != expected.get("cost_decision"):
            cost_gaps.append(
                {
                    "scenario": item["scenario"],
                    "expected_cost_decision": expected.get("cost_decision"),
                    "observed_cost_decision": cost.get("decision"),
                }
            )
        if cost.get("decision") == "block_or_review":
            if not expected.get("requires_cost_review"):
                cost_gaps.append({"scenario": item["scenario"], "reason": "missing_required_cost_review"})
            if "fallback" not in str(item.get("fallback", "")).lower():
                cost_gaps.append({"scenario": item["scenario"], "reason": "missing_cost_fallback"})
    linkage_gaps = []
    for item in actions:
        expected = item["expected"]
        if item.get("owner") != item.get("runbook_owner"):
            linkage_gaps.append(
                {
                    "scenario": item["scenario"],
                    "reason": "owner_runbook_mismatch",
                    "owner": item.get("owner"),
                    "runbook_owner": item.get("runbook_owner"),
                }
            )
        if item.get("budget_decision") != expected.get("budget_decision"):
            linkage_gaps.append(
                {
                    "scenario": item["scenario"],
                    "reason": "budget_decision_mismatch",
                    "expected": expected.get("budget_decision"),
                    "observed": item.get("budget_decision"),
                }
            )
        if item.get("release_action") != expected.get("release_action"):
            linkage_gaps.append(
                {
                    "scenario": item["scenario"],
                    "reason": "release_action_mismatch",
                    "expected": expected.get("release_action"),
                    "observed": item.get("release_action"),
                }
            )
        if expected.get("requires_preflight_probe"):
            probe = item["probe"]
            if not probe.get("name") or probe.get("signal_ok") is not True:
                linkage_gaps.append({"scenario": item["scenario"], "reason": "missing_preflight_probe"})
            if probe.get("release_action") != item.get("release_action"):
                linkage_gaps.append(
                    {
                        "scenario": item["scenario"],
                        "reason": "probe_release_action_mismatch",
                        "probe_release_action": probe.get("release_action"),
                        "release_action": item.get("release_action"),
                    }
                )
    checks = [
        check(
            "action_inventory",
            len(actions) >= int(policy.get("minimum_action_count", 0)) and not missing_actions,
            {
                "action_count": len(actions),
                "missing_actions": missing_actions,
            },
        ),
        check(
            "capacity_guardrail",
            not capacity_gaps and protective_count >= int(policy.get("minimum_protective_action_count", 0)),
            {
                "protective_action_count": protective_count,
                "gaps": capacity_gaps,
            },
        ),
        check("tenant_priority_contract", not tenant_gaps, {"gaps": tenant_gaps}),
        check("cost_guardrail_linkage", not cost_gaps, {"gaps": cost_gaps}),
        check("release_probe_runbook_linkage", not linkage_gaps, {"gaps": linkage_gaps}),
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "checks": checks,
        "protective_action_count": protective_count,
        "failed_count": sum(1 for item in checks if not item["ok"]),
    }


def mutate_fixture(policy: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(policy)
    actions = actions_by_scenario(mutated)
    scenario = str(fixture["scenario"])
    mutation = fixture["mutation"]
    if mutation == "remove_action":
        mutated["actions"] = [
            item
            for item in mutated.get("actions", [])
            if item.get("scenario") != scenario
        ]
    elif mutation == "set_traffic_action":
        actions[scenario]["traffic_action"] = str(fixture["traffic_action"])
    elif mutation == "add_shed_tier":
        shed_tiers = actions[scenario].setdefault("shed_tiers", [])
        if fixture["tier"] not in shed_tiers:
            shed_tiers.append(str(fixture["tier"]))
    elif mutation == "set_requires_cost_review":
        actions[scenario]["requires_cost_review"] = bool(fixture["requires_cost_review"])
    elif mutation == "set_expected_release_action":
        actions[scenario]["expected_release_action"] = str(fixture["expected_release_action"])
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    *,
    capacity: dict[str, Any],
    tenant_blast_radius: dict[str, Any],
    token_cost: dict[str, Any],
    error_budget: dict[str, Any],
    synthetic_probe: dict[str, Any],
    runbooks: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_policy = mutate_fixture(policy, fixture)
        actions = build_actions(
            capacity=capacity,
            tenant_blast_radius=tenant_blast_radius,
            token_cost=token_cost,
            error_budget=error_budget,
            synthetic_probe=synthetic_probe,
            runbooks=runbooks,
            policy=mutated_policy,
        )
        report = evaluate_actions(actions, mutated_policy, capacity)
        expected_failed_check = fixture["expected_failed_check"]
        failed_checks = [item["name"] for item in report["checks"] if not item["ok"]]
        results.append(
            {
                "name": fixture["name"],
                "mutation": fixture["mutation"],
                "scenario": fixture["scenario"],
                "expected_failed_check": expected_failed_check,
                "failed_checks": failed_checks,
                "detected": expected_failed_check in failed_checks,
            }
        )
    return results


def build_report(
    *,
    capacity: dict[str, Any],
    tenant_blast_radius: dict[str, Any],
    token_cost: dict[str, Any],
    error_budget: dict[str, Any],
    synthetic_probe: dict[str, Any],
    runbooks: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    actions = build_actions(
        capacity=capacity,
        tenant_blast_radius=tenant_blast_radius,
        token_cost=token_cost,
        error_budget=error_budget,
        synthetic_probe=synthetic_probe,
        runbooks=runbooks,
        policy=policy,
    )
    action_report = evaluate_actions(actions, policy, capacity)
    fixture_results = evaluate_fixtures(
        capacity=capacity,
        tenant_blast_radius=tenant_blast_radius,
        token_cost=token_cost,
        error_budget=error_budget,
        synthetic_probe=synthetic_probe,
        runbooks=runbooks,
        policy=policy,
    )
    undetected = [item for item in fixture_results if not item["detected"]]
    checks = action_report["checks"] + [
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
        "action_count": len(actions),
        "protective_action_count": action_report["protective_action_count"],
        "fixture_count": len(fixture_results),
        "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
        "failed_count": failed_count,
        "actions": actions,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "load-shedding-policy-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Load Shedding Policy Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that overload and incident paths have explicit",
        "graceful-degradation decisions before release promotion. The policy",
        "links capacity warnings, tenant blast radius, token/GPU cost review,",
        "error-budget release actions, preflight probes, and runbook ownership.",
        "",
        "## Summary",
        "",
        f"- Actions: `{report['action_count']}`",
        f"- Protective actions: `{report['protective_action_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Actions",
        "",
        "| Action | Scenario | Traffic action | Protected tiers | Shed tiers | Release action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["actions"]:
        lines.append(
            "| `{name}` | `{scenario}` | `{traffic_action}` | `{protected}` | `{shed}` | `{release_action}` |".format(
                name=item["name"],
                scenario=item["scenario"],
                traffic_action=item["traffic_action"],
                protected=", ".join(item["protected_tiers"]) or "none",
                shed=", ".join(item["shed_tiers"]) or "none",
                release_action=item["release_action"],
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Scenario | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item['scenario']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "load-shedding-policy-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/load-shedding-policy.json")
    parser.add_argument("--capacity", default="docs/evidence/capacity-plan.json")
    parser.add_argument("--tenant-blast-radius", default="docs/evidence/tenant-blast-radius.json")
    parser.add_argument("--token-cost", default="docs/evidence/token-cost-guard.json")
    parser.add_argument("--error-budget", default="docs/evidence/error-budget-ledger.json")
    parser.add_argument("--synthetic-probe", default="docs/evidence/synthetic-probe-audit.json")
    parser.add_argument("--runbooks", default="docs/evidence/incident-runbooks.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(
        capacity=load_json(Path(args.capacity)),
        tenant_blast_radius=load_json(Path(args.tenant_blast_radius)),
        token_cost=load_json(Path(args.token_cost)),
        error_budget=load_json(Path(args.error_budget)),
        synthetic_probe=load_json(Path(args.synthetic_probe)),
        runbooks=load_json(Path(args.runbooks)),
        policy=load_json(Path(args.policy)),
    )
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'load-shedding-policy-audit.json'}")
    print(f"wrote {output_dir / 'load-shedding-policy-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
