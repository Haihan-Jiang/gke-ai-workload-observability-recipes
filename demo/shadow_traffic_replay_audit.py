#!/usr/bin/env python3
"""Audit shadow traffic replay safety for AI inference releases."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
BLOCKING_ACTIONS = {"block_release_or_rollback", "require_sre_review_before_rollout"}


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


def build_replays(
    *,
    policy: dict[str, Any],
    summary: list[dict[str, Any]],
    telemetry_redaction: dict[str, Any],
    rollout_guard: dict[str, Any],
    token_cost: dict[str, Any],
    synthetic_probe: dict[str, Any],
    model_release_safety: dict[str, Any],
) -> list[dict[str, Any]]:
    summary_by_scenario = by_scenario(summary)
    cost_by_scenario = by_scenario(token_cost.get("scenarios", []))
    probe_by_scenario = by_scenario(synthetic_probe.get("probes", []))
    replays = []
    for replay in policy.get("replays", []):
        scenario = str(replay["scenario"])
        observed = summary_by_scenario.get(scenario, {})
        cost = cost_by_scenario.get(scenario, {})
        probe = probe_by_scenario.get(scenario, {})
        replays.append(
            {
                "name": replay["name"],
                "scenario": scenario,
                "role": replay.get("role"),
                "model_variant": replay.get("model_variant"),
                "service_version": replay.get("service_version"),
                "shadow_percent": replay.get("shadow_percent"),
                "sample_requests": replay.get("sample_requests"),
                "served_to_users": replay.get("served_to_users"),
                "writes_disabled": replay.get("writes_disabled"),
                "side_effects_disabled": replay.get("side_effects_disabled"),
                "store_prompt": replay.get("store_prompt"),
                "store_response": replay.get("store_response"),
                "requires_redaction": replay.get("requires_redaction"),
                "observed": {
                    "requests": observed.get("requests"),
                    "errors": observed.get("errors"),
                    "p95_ms": observed.get("p95_ms"),
                    "cache_miss_rate": observed.get("cache_miss_rate"),
                    "telemetry_loss_rate": observed.get("telemetry_loss_rate"),
                    "model_variant": observed.get("model_variant"),
                    "service_version": observed.get("service_version"),
                },
                "expected": {
                    "probe": replay.get("expected_probe"),
                    "release_action": replay.get("expected_release_action"),
                    "cost_decision": replay.get("expected_cost_decision"),
                    "rollout_decision": replay.get("expected_rollout_decision"),
                    "requires_rollback": bool(replay.get("requires_rollback")),
                },
                "cost": {
                    "decision": cost.get("decision"),
                    "model_variant": cost.get("model_variant"),
                    "estimated_cost_per_1k_requests": cost.get("estimated_cost_per_1k_requests"),
                    "violations": cost.get("violations", []),
                },
                "probe": {
                    "name": probe.get("name"),
                    "signal_ok": probe.get("signal_ok"),
                    "release_action": probe.get("release_action"),
                    "model_variant": (probe.get("observed") or {}).get("model_variant"),
                    "service_version": (probe.get("observed") or {}).get("service_version"),
                    "rollback_within_rto": probe.get("rollback_within_rto"),
                },
                "rollout_guard": {
                    "candidate": rollout_guard.get("candidate"),
                    "candidate_version": rollout_guard.get("candidate_version"),
                    "decision": rollout_guard.get("decision"),
                    "violations": rollout_guard.get("violations", []),
                },
                "telemetry_redaction": {
                    "status": telemetry_redaction.get("status"),
                    "payload_count": telemetry_redaction.get("payload_count"),
                    "redaction_violation_count": telemetry_redaction.get("redaction_violation_count"),
                },
                "model_release_safety": {
                    "status": model_release_safety.get("status"),
                    "blocked_candidate_count": model_release_safety.get("blocked_candidate_count"),
                },
            }
        )
    return replays


def evaluate_replays(replays: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    candidate_replays = [item for item in replays if item.get("role") == "candidate"]
    inventory_gaps = []
    for item in replays:
        if not item["observed"].get("requests"):
            inventory_gaps.append({"replay": item["name"], "reason": "missing_summary_scenario"})
        if item.get("sample_requests", 0) < int(policy.get("minimum_sample_requests", 0)):
            inventory_gaps.append(
                {
                    "replay": item["name"],
                    "reason": "sample_too_small",
                    "sample_requests": item.get("sample_requests"),
                }
            )
        if item["observed"].get("model_variant") != item.get("model_variant"):
            inventory_gaps.append(
                {
                    "replay": item["name"],
                    "reason": "model_variant_mismatch",
                    "expected": item.get("model_variant"),
                    "observed": item["observed"].get("model_variant"),
                }
            )
    isolation_gaps = []
    max_shadow_percent = int(policy.get("max_shadow_percent", 0))
    for item in replays:
        if item.get("served_to_users") is not False:
            isolation_gaps.append({"replay": item["name"], "reason": "shadow_serves_users"})
        if item.get("writes_disabled") is not True:
            isolation_gaps.append({"replay": item["name"], "reason": "writes_not_disabled"})
        if item.get("side_effects_disabled") is not True:
            isolation_gaps.append({"replay": item["name"], "reason": "side_effects_not_disabled"})
        if int(item.get("shadow_percent") or 0) > max_shadow_percent:
            isolation_gaps.append(
                {
                    "replay": item["name"],
                    "reason": "shadow_percent_too_high",
                    "shadow_percent": item.get("shadow_percent"),
                    "max_shadow_percent": max_shadow_percent,
                }
            )
    privacy_gaps = []
    for item in replays:
        if item.get("requires_redaction") and item["telemetry_redaction"].get("status") != "pass":
            privacy_gaps.append({"replay": item["name"], "reason": "redaction_not_pass"})
        if int(item["telemetry_redaction"].get("redaction_violation_count") or 0) != 0:
            privacy_gaps.append({"replay": item["name"], "reason": "redaction_violations_present"})
        if item.get("store_prompt") is not False:
            privacy_gaps.append({"replay": item["name"], "reason": "prompt_storage_enabled"})
        if item.get("store_response") is not False:
            privacy_gaps.append({"replay": item["name"], "reason": "response_storage_enabled"})
    comparison_gaps = []
    for item in candidate_replays:
        rollout = item["rollout_guard"]
        expected = item["expected"]
        if rollout.get("candidate") != item.get("scenario") or rollout.get("candidate_version") != item.get("service_version"):
            comparison_gaps.append({"replay": item["name"], "reason": "rollout_candidate_mismatch", "rollout": rollout})
        if rollout.get("decision") != expected.get("rollout_decision"):
            comparison_gaps.append(
                {
                    "replay": item["name"],
                    "reason": "rollout_decision_mismatch",
                    "expected": expected.get("rollout_decision"),
                    "observed": rollout.get("decision"),
                }
            )
        if rollout.get("decision") == "rollback" and expected.get("release_action") not in BLOCKING_ACTIONS:
            comparison_gaps.append({"replay": item["name"], "reason": "rollback_not_blocking_release"})
    cost_gaps = []
    for item in replays:
        expected = item["expected"]
        if item["cost"].get("decision") != expected.get("cost_decision"):
            cost_gaps.append(
                {
                    "replay": item["name"],
                    "reason": "cost_decision_mismatch",
                    "expected": expected.get("cost_decision"),
                    "observed": item["cost"].get("decision"),
                }
            )
        if item["cost"].get("decision") == "block_or_review" and expected.get("release_action") not in BLOCKING_ACTIONS:
            cost_gaps.append({"replay": item["name"], "reason": "cost_review_not_blocking_release"})
    linkage_gaps = []
    for item in replays:
        expected = item["expected"]
        probe = item["probe"]
        if probe.get("name") != expected.get("probe") or probe.get("signal_ok") is not True:
            linkage_gaps.append(
                {
                    "replay": item["name"],
                    "reason": "probe_mismatch",
                    "expected": expected.get("probe"),
                    "observed": probe,
                }
            )
        if probe.get("release_action") != expected.get("release_action"):
            linkage_gaps.append(
                {
                    "replay": item["name"],
                    "reason": "probe_release_action_mismatch",
                    "expected": expected.get("release_action"),
                    "observed": probe.get("release_action"),
                }
            )
        if expected.get("requires_rollback") and probe.get("rollback_within_rto") is not True:
            linkage_gaps.append({"replay": item["name"], "reason": "rollback_probe_not_within_rto"})
        if item.get("role") == "candidate":
            release_safety = item["model_release_safety"]
            if release_safety.get("status") != "pass" or int(release_safety.get("blocked_candidate_count") or 0) < 1:
                linkage_gaps.append({"replay": item["name"], "reason": "model_release_safety_not_blocking_candidate"})
    checks = [
        check(
            "shadow_inventory",
            len(replays) >= int(policy.get("minimum_replay_count", 0))
            and len(candidate_replays) >= int(policy.get("minimum_candidate_replay_count", 0))
            and not inventory_gaps,
            {
                "replay_count": len(replays),
                "candidate_replay_count": len(candidate_replays),
                "gaps": inventory_gaps,
            },
        ),
        check("isolation_contract", not isolation_gaps, {"gaps": isolation_gaps}),
        check("privacy_contract", not privacy_gaps, {"gaps": privacy_gaps}),
        check("candidate_comparison_gate", not comparison_gaps, {"gaps": comparison_gaps}),
        check("cost_budget_gate", not cost_gaps, {"gaps": cost_gaps}),
        check("rollback_probe_linkage", not linkage_gaps, {"gaps": linkage_gaps}),
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "checks": checks,
        "candidate_replay_count": len(candidate_replays),
        "blocked_shadow_count": sum(
            1
            for item in candidate_replays
            if item["expected"].get("release_action") in BLOCKING_ACTIONS
        ),
        "failed_count": sum(1 for item in checks if not item["ok"]),
    }


def mutate_fixture(policy: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(policy)
    replays = by_name(mutated.get("replays", []))
    replay_name = str(fixture["replay"])
    mutation = fixture["mutation"]
    if mutation == "remove_replay":
        mutated["replays"] = [
            item
            for item in mutated.get("replays", [])
            if item.get("name") != replay_name
        ]
    elif mutation == "set_served_to_users":
        replays[replay_name]["served_to_users"] = bool(fixture["served_to_users"])
    elif mutation == "set_shadow_percent":
        replays[replay_name]["shadow_percent"] = int(fixture["shadow_percent"])
    elif mutation == "set_store_prompt":
        replays[replay_name]["store_prompt"] = bool(fixture["store_prompt"])
    elif mutation == "set_expected_rollout_decision":
        replays[replay_name]["expected_rollout_decision"] = str(fixture["expected_rollout_decision"])
    elif mutation == "set_expected_cost_decision":
        replays[replay_name]["expected_cost_decision"] = str(fixture["expected_cost_decision"])
    elif mutation == "set_expected_probe":
        replays[replay_name]["expected_probe"] = str(fixture["expected_probe"])
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    *,
    policy: dict[str, Any],
    summary: list[dict[str, Any]],
    telemetry_redaction: dict[str, Any],
    rollout_guard: dict[str, Any],
    token_cost: dict[str, Any],
    synthetic_probe: dict[str, Any],
    model_release_safety: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_policy = mutate_fixture(policy, fixture)
        replays = build_replays(
            policy=mutated_policy,
            summary=summary,
            telemetry_redaction=telemetry_redaction,
            rollout_guard=rollout_guard,
            token_cost=token_cost,
            synthetic_probe=synthetic_probe,
            model_release_safety=model_release_safety,
        )
        report = evaluate_replays(replays, mutated_policy)
        expected_failed_check = fixture["expected_failed_check"]
        failed_checks = [item["name"] for item in report["checks"] if not item["ok"]]
        results.append(
            {
                "name": fixture["name"],
                "mutation": fixture["mutation"],
                "replay": fixture["replay"],
                "expected_failed_check": expected_failed_check,
                "failed_checks": failed_checks,
                "detected": expected_failed_check in failed_checks,
            }
        )
    return results


def build_report(
    *,
    policy: dict[str, Any],
    summary: list[dict[str, Any]],
    telemetry_redaction: dict[str, Any],
    rollout_guard: dict[str, Any],
    token_cost: dict[str, Any],
    synthetic_probe: dict[str, Any],
    model_release_safety: dict[str, Any],
) -> dict[str, Any]:
    replays = build_replays(
        policy=policy,
        summary=summary,
        telemetry_redaction=telemetry_redaction,
        rollout_guard=rollout_guard,
        token_cost=token_cost,
        synthetic_probe=synthetic_probe,
        model_release_safety=model_release_safety,
    )
    replay_report = evaluate_replays(replays, policy)
    fixture_results = evaluate_fixtures(
        policy=policy,
        summary=summary,
        telemetry_redaction=telemetry_redaction,
        rollout_guard=rollout_guard,
        token_cost=token_cost,
        synthetic_probe=synthetic_probe,
        model_release_safety=model_release_safety,
    )
    undetected = [item for item in fixture_results if not item["detected"]]
    checks = replay_report["checks"] + [
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
        "replay_count": len(replays),
        "candidate_replay_count": replay_report["candidate_replay_count"],
        "blocked_shadow_count": replay_report["blocked_shadow_count"],
        "fixture_count": len(fixture_results),
        "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
        "failed_count": failed_count,
        "replays": replays,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "shadow-traffic-replay-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Shadow Traffic Replay Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that shadow traffic for an AI inference candidate is",
        "isolated from users, privacy-safe, sampled enough to be useful, compared",
        "against rollout and cost gates, and linked to rollback/probe evidence.",
        "",
        "## Summary",
        "",
        f"- Replays: `{report['replay_count']}`",
        f"- Candidate replays: `{report['candidate_replay_count']}`",
        f"- Blocked shadow candidates: `{report['blocked_shadow_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Replays",
        "",
        "| Replay | Role | Scenario | Shadow % | Served to users | Expected action |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in report["replays"]:
        lines.append(
            "| `{name}` | `{role}` | `{scenario}` | {shadow_percent} | `{served}` | `{action}` |".format(
                name=item["name"],
                role=item["role"],
                scenario=item["scenario"],
                shadow_percent=item["shadow_percent"],
                served=item["served_to_users"],
                action=item["expected"].get("release_action"),
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Replay | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item['replay']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "shadow-traffic-replay-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/shadow-traffic-policy.json")
    parser.add_argument("--summary", default="docs/evidence/sample-summary.json")
    parser.add_argument("--telemetry-redaction", default="docs/evidence/telemetry-redaction-audit.json")
    parser.add_argument("--rollout-guard", default="docs/evidence/rollout-guard.json")
    parser.add_argument("--token-cost", default="docs/evidence/token-cost-guard.json")
    parser.add_argument("--synthetic-probe", default="docs/evidence/synthetic-probe-audit.json")
    parser.add_argument("--model-release-safety", default="docs/evidence/model-release-safety-audit.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(
        policy=load_json(Path(args.policy)),
        summary=load_json(Path(args.summary)),
        telemetry_redaction=load_json(Path(args.telemetry_redaction)),
        rollout_guard=load_json(Path(args.rollout_guard)),
        token_cost=load_json(Path(args.token_cost)),
        synthetic_probe=load_json(Path(args.synthetic_probe)),
        model_release_safety=load_json(Path(args.model_release_safety)),
    )
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'shadow-traffic-replay-audit.json'}")
    print(f"wrote {output_dir / 'shadow-traffic-replay-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
