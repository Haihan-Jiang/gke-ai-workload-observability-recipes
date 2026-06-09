#!/usr/bin/env python3
"""Audit accelerator quota fairness for AI inference tenants."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
BLOCKING_ACTIONS = {"block_release_or_rollback", "require_sre_review_before_rollout"}
PROTECTIVE_TRAFFIC_ACTIONS = {
    "protect_telemetry",
    "rate_limit_retrieval",
    "rollback_canary",
    "shed_best_effort",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def by_name(items: list[dict[str, Any]], field: str = "name") -> dict[str, dict[str, Any]]:
    return {
        str(item[field]): item
        for item in items
        if item.get(field)
    }


def by_scenario(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item["scenario"]): item
        for item in items
        if item.get("scenario")
    }


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def build_quotas(
    *,
    policy: dict[str, Any],
    capacity: dict[str, Any],
    tenant_blast_radius: dict[str, Any],
    token_cost: dict[str, Any],
    load_shedding: dict[str, Any],
    shadow_traffic: dict[str, Any],
    model_release_safety: dict[str, Any],
) -> list[dict[str, Any]]:
    capacity_by_scenario = by_scenario(capacity.get("scenarios", []))
    tenant_by_scenario = by_scenario(tenant_blast_radius.get("scenarios", []))
    cost_by_scenario = by_scenario(token_cost.get("scenarios", []))
    action_by_scenario = by_scenario(load_shedding.get("actions", []))
    shadow_by_scenario = by_scenario(shadow_traffic.get("replays", []))
    quotas = []
    for quota in policy.get("quotas", []):
        scenario = str(quota["scenario"])
        tenant = tenant_by_scenario.get(scenario, {})
        cost = cost_by_scenario.get(scenario, {})
        capacity_item = capacity_by_scenario.get(scenario, {})
        action = action_by_scenario.get(scenario, {})
        shadow = shadow_by_scenario.get(scenario, {})
        tier = str(quota["tenant_tier"])
        tier_policy = policy.get("tiers", {}).get(tier, {})
        quotas.append(
            {
                "name": quota["name"],
                "scenario": scenario,
                "tenant_tier": tier,
                "tier_max_gpu_ms": tier_policy.get("max_gpu_ms"),
                "tier_reserved_share": tier_policy.get("reserved_share"),
                "expected": {
                    "cost_decision": quota.get("expected_cost_decision"),
                    "release_action": quota.get("expected_release_action"),
                    "traffic_action": quota.get("expected_traffic_action"),
                    "requires_shadow_block": bool(quota.get("requires_shadow_block")),
                    "protect_tiers": list(quota.get("protect_tiers", [])),
                    "shed_tiers": list(quota.get("shed_tiers", [])),
                },
                "observed": {
                    "tenant_tier": tenant.get("tenant_tier"),
                    "blast_radius": tenant.get("blast_radius"),
                    "tenant_violations": tenant.get("violations", []),
                    "gpu_ms": cost.get("gpu_ms"),
                    "tokens": cost.get("total_tokens"),
                    "cost_decision": cost.get("decision"),
                    "cost_violations": cost.get("violations", []),
                    "required_replicas": capacity_item.get("required_replicas"),
                    "max_replicas_budget": capacity.get("max_replicas_budget"),
                    "capacity_warnings": capacity_item.get("warnings", []),
                    "traffic_action": action.get("traffic_action"),
                    "release_action": action.get("release_action"),
                    "protected_tiers": action.get("protected_tiers", []),
                    "shed_tiers": action.get("shed_tiers", []),
                    "fallback": action.get("fallback"),
                    "shadow_role": shadow.get("role"),
                    "shadow_percent": shadow.get("shadow_percent"),
                    "shadow_served_to_users": shadow.get("served_to_users"),
                },
                "shadow_traffic_status": shadow_traffic.get("status"),
                "blocked_shadow_count": shadow_traffic.get("blocked_shadow_count"),
                "model_release_safety_status": model_release_safety.get("status"),
                "blocked_candidate_count": model_release_safety.get("blocked_candidate_count"),
            }
        )
    return quotas


def evaluate_quotas(quotas: list[dict[str, Any]], policy: dict[str, Any], token_cost: dict[str, Any]) -> dict[str, Any]:
    quota_scenarios = {item["scenario"] for item in quotas}
    cost_scenarios = {
        str(item["scenario"])
        for item in token_cost.get("scenarios", [])
        if item.get("scenario")
    }
    missing_scenarios = sorted(cost_scenarios - quota_scenarios)
    budget_gaps = []
    for item in quotas:
        observed = item["observed"]
        expected = item["expected"]
        gpu_ms = int(observed.get("gpu_ms") or 0)
        max_gpu_ms = int(item.get("tier_max_gpu_ms") or 0)
        cost_decision = observed.get("cost_decision")
        release_action = observed.get("release_action")
        expected_cost_decision = expected.get("cost_decision")
        required_replicas = int(observed.get("required_replicas") or 0)
        max_replicas_budget = int(observed.get("max_replicas_budget") or 0)
        if observed.get("tenant_tier") != item.get("tenant_tier"):
            budget_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "tenant_tier_mismatch",
                    "expected": item.get("tenant_tier"),
                    "observed": observed.get("tenant_tier"),
                }
            )
        if cost_decision != expected_cost_decision:
            budget_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "cost_decision_mismatch",
                    "expected": expected_cost_decision,
                    "observed": cost_decision,
                }
            )
        over_gpu_quota = gpu_ms > max_gpu_ms
        over_replica_budget = required_replicas > max_replicas_budget > 0
        if (over_gpu_quota or over_replica_budget) and release_action not in BLOCKING_ACTIONS:
            budget_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "accelerator_overage_not_blocked",
                    "gpu_ms": gpu_ms,
                    "max_gpu_ms": max_gpu_ms,
                    "required_replicas": required_replicas,
                    "max_replicas_budget": max_replicas_budget,
                    "release_action": release_action,
                }
            )
        if over_gpu_quota and expected_cost_decision != "block_or_review":
            budget_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "overage_expected_cost_not_review",
                    "gpu_ms": gpu_ms,
                    "max_gpu_ms": max_gpu_ms,
                    "expected_cost_decision": expected_cost_decision,
                }
            )
    fairness_gaps = []
    for item in quotas:
        observed = item["observed"]
        expected = item["expected"]
        tier = item["tenant_tier"]
        protected = set(observed.get("protected_tiers") or [])
        shed = set(observed.get("shed_tiers") or [])
        expected_protected = set(expected.get("protect_tiers") or [])
        expected_shed = set(expected.get("shed_tiers") or [])
        tenant_violations = observed.get("tenant_violations") or []
        if tenant_violations and tier not in expected_protected:
            fairness_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "policy_does_not_protect_violating_tenant",
                    "tier": tier,
                    "expected_protect_tiers": sorted(expected_protected),
                }
            )
        if tenant_violations and tier not in protected:
            fairness_gaps.append({"quota": item["name"], "reason": "violating_tenant_not_protected", "tier": tier})
        if tier in shed:
            fairness_gaps.append({"quota": item["name"], "reason": "protected_tenant_is_shed", "tier": tier})
        if not expected_protected.issubset(protected):
            fairness_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "missing_expected_protected_tier",
                    "expected": sorted(expected_protected),
                    "observed": sorted(protected),
                }
            )
        if expected_shed and not expected_shed.issubset(shed):
            fairness_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "missing_expected_shed_tier",
                    "expected": sorted(expected_shed),
                    "observed": sorted(shed),
                }
            )
        if item["scenario"] != "baseline" and "best_effort" not in shed:
            fairness_gaps.append({"quota": item["name"], "reason": "best_effort_not_shed_first"})
        if item["scenario"] != "baseline" and "best_effort" not in expected_shed:
            fairness_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "policy_does_not_shed_best_effort_first",
                    "expected_shed_tiers": sorted(expected_shed),
                }
            )
    linkage_gaps = []
    for item in quotas:
        observed = item["observed"]
        expected = item["expected"]
        traffic_action = observed.get("traffic_action")
        release_action = observed.get("release_action")
        if traffic_action != expected.get("traffic_action"):
            linkage_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "traffic_action_mismatch",
                    "expected": expected.get("traffic_action"),
                    "observed": traffic_action,
                }
            )
        if release_action != expected.get("release_action"):
            linkage_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "release_action_mismatch",
                    "expected": expected.get("release_action"),
                    "observed": release_action,
                }
            )
        if observed.get("capacity_warnings") and traffic_action not in PROTECTIVE_TRAFFIC_ACTIONS:
            linkage_gaps.append(
                {
                    "quota": item["name"],
                    "reason": "capacity_warning_without_protective_action",
                    "traffic_action": traffic_action,
                    "warnings": observed.get("capacity_warnings"),
                }
            )
        if traffic_action in PROTECTIVE_TRAFFIC_ACTIONS and not observed.get("fallback"):
            linkage_gaps.append({"quota": item["name"], "reason": "missing_fallback"})
    shadow_gaps = []
    for item in quotas:
        expected = item["expected"]
        if not expected.get("requires_shadow_block") and item["scenario"] != "rollout_regression":
            continue
        if expected.get("requires_shadow_block") is not True:
            shadow_gaps.append({"quota": item["name"], "reason": "candidate_does_not_require_shadow_block"})
        if item.get("shadow_traffic_status") != "pass" or int(item.get("blocked_shadow_count") or 0) < 1:
            shadow_gaps.append({"quota": item["name"], "reason": "shadow_traffic_not_blocking_candidate"})
        if item.get("model_release_safety_status") != "pass" or int(item.get("blocked_candidate_count") or 0) < 1:
            shadow_gaps.append({"quota": item["name"], "reason": "model_release_safety_not_blocking_candidate"})
        if item["observed"].get("shadow_served_to_users") is not False:
            shadow_gaps.append({"quota": item["name"], "reason": "candidate_shadow_serves_users"})
    checks = [
        check(
            "quota_inventory",
            len(quotas) >= int(policy.get("minimum_quota_count", 0)) and not missing_scenarios,
            {
                "quota_count": len(quotas),
                "missing_scenarios": missing_scenarios,
            },
        ),
        check("accelerator_budget_guard", not budget_gaps, {"gaps": budget_gaps}),
        check("tenant_fairness_contract", not fairness_gaps, {"gaps": fairness_gaps}),
        check("load_shedding_linkage", not linkage_gaps, {"gaps": linkage_gaps}),
        check("shadow_candidate_quota", not shadow_gaps, {"gaps": shadow_gaps}),
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "checks": checks,
        "candidate_quota_count": sum(1 for item in quotas if item["scenario"] == "rollout_regression"),
        "protected_tier_count": len({tier for item in quotas for tier in item["observed"].get("protected_tiers", [])}),
        "failed_count": sum(1 for item in checks if not item["ok"]),
    }


def mutate_fixture(policy: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(policy)
    quotas = by_name(mutated.get("quotas", []))
    mutation = fixture["mutation"]
    if mutation == "remove_quota":
        quota_name = str(fixture["quota"])
        mutated["quotas"] = [
            item
            for item in mutated.get("quotas", [])
            if item.get("name") != quota_name
        ]
    elif mutation == "set_tier_max_gpu_ms":
        mutated["tiers"][str(fixture["tier"])]["max_gpu_ms"] = int(fixture["max_gpu_ms"])
    elif mutation == "set_expected_cost_decision":
        quotas[str(fixture["quota"])]["expected_cost_decision"] = str(fixture["expected_cost_decision"])
    elif mutation == "remove_protect_tier":
        quota = quotas[str(fixture["quota"])]
        quota["protect_tiers"] = [tier for tier in quota.get("protect_tiers", []) if tier != fixture["tier"]]
    elif mutation == "remove_shed_tier":
        quota = quotas[str(fixture["quota"])]
        quota["shed_tiers"] = [tier for tier in quota.get("shed_tiers", []) if tier != fixture["tier"]]
    elif mutation == "set_expected_traffic_action":
        quotas[str(fixture["quota"])]["expected_traffic_action"] = str(fixture["expected_traffic_action"])
    elif mutation == "set_requires_shadow_block":
        quotas[str(fixture["quota"])]["requires_shadow_block"] = bool(fixture["requires_shadow_block"])
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    *,
    policy: dict[str, Any],
    capacity: dict[str, Any],
    tenant_blast_radius: dict[str, Any],
    token_cost: dict[str, Any],
    load_shedding: dict[str, Any],
    shadow_traffic: dict[str, Any],
    model_release_safety: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_policy = mutate_fixture(policy, fixture)
        quotas = build_quotas(
            policy=mutated_policy,
            capacity=capacity,
            tenant_blast_radius=tenant_blast_radius,
            token_cost=token_cost,
            load_shedding=load_shedding,
            shadow_traffic=shadow_traffic,
            model_release_safety=model_release_safety,
        )
        report = evaluate_quotas(quotas, mutated_policy, token_cost)
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
    tenant_blast_radius: dict[str, Any],
    token_cost: dict[str, Any],
    load_shedding: dict[str, Any],
    shadow_traffic: dict[str, Any],
    model_release_safety: dict[str, Any],
) -> dict[str, Any]:
    quotas = build_quotas(
        policy=policy,
        capacity=capacity,
        tenant_blast_radius=tenant_blast_radius,
        token_cost=token_cost,
        load_shedding=load_shedding,
        shadow_traffic=shadow_traffic,
        model_release_safety=model_release_safety,
    )
    quota_report = evaluate_quotas(quotas, policy, token_cost)
    fixture_results = evaluate_fixtures(
        policy=policy,
        capacity=capacity,
        tenant_blast_radius=tenant_blast_radius,
        token_cost=token_cost,
        load_shedding=load_shedding,
        shadow_traffic=shadow_traffic,
        model_release_safety=model_release_safety,
    )
    undetected = [item for item in fixture_results if not item["detected"]]
    checks = quota_report["checks"] + [
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
        "quota_count": len(quotas),
        "candidate_quota_count": quota_report["candidate_quota_count"],
        "protected_tier_count": quota_report["protected_tier_count"],
        "fixture_count": len(fixture_results),
        "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
        "failed_count": failed_count,
        "quotas": quotas,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "accelerator-quota-fairness-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Accelerator Quota Fairness Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that GPU/accelerator use is bounded by tenant tier,",
        "that over-quota or over-capacity paths are blocked or reviewed, and",
        "that load shedding protects premium and standard traffic before",
        "best-effort traffic consumes release capacity.",
        "",
        "## Summary",
        "",
        f"- Quotas: `{report['quota_count']}`",
        f"- Candidate quotas: `{report['candidate_quota_count']}`",
        f"- Protected tiers: `{report['protected_tier_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Quotas",
        "",
        "| Quota | Scenario | Tier | GPU ms | Cost decision | Traffic action |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in report["quotas"]:
        observed = item["observed"]
        lines.append(
            "| `{name}` | `{scenario}` | `{tier}` | {gpu_ms} | `{cost}` | `{traffic}` |".format(
                name=item["name"],
                scenario=item["scenario"],
                tier=item["tenant_tier"],
                gpu_ms=observed.get("gpu_ms"),
                cost=observed.get("cost_decision"),
                traffic=observed.get("traffic_action"),
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
    (output_dir / "accelerator-quota-fairness-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/accelerator-quota-policy.json")
    parser.add_argument("--capacity", default="docs/evidence/capacity-plan.json")
    parser.add_argument("--tenant-blast-radius", default="docs/evidence/tenant-blast-radius.json")
    parser.add_argument("--token-cost", default="docs/evidence/token-cost-guard.json")
    parser.add_argument("--load-shedding", default="docs/evidence/load-shedding-policy-audit.json")
    parser.add_argument("--shadow-traffic", default="docs/evidence/shadow-traffic-replay-audit.json")
    parser.add_argument("--model-release-safety", default="docs/evidence/model-release-safety-audit.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(
        policy=load_json(Path(args.policy)),
        capacity=load_json(Path(args.capacity)),
        tenant_blast_radius=load_json(Path(args.tenant_blast_radius)),
        token_cost=load_json(Path(args.token_cost)),
        load_shedding=load_json(Path(args.load_shedding)),
        shadow_traffic=load_json(Path(args.shadow_traffic)),
        model_release_safety=load_json(Path(args.model_release_safety)),
    )
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'accelerator-quota-fairness-audit.json'}")
    print(f"wrote {output_dir / 'accelerator-quota-fairness-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
