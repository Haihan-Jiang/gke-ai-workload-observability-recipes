#!/usr/bin/env python3
"""Audit model release safety for AI inference rollout evidence."""

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


def artifact_pinned(release: dict[str, Any]) -> bool:
    artifact_uri = str(release.get("artifact_uri", ""))
    artifact_sha = str(release.get("artifact_sha256", ""))
    return (
        len(artifact_sha) == 64
        and all(char in "0123456789abcdef" for char in artifact_sha)
        and f"@sha256:{artifact_sha}" in artifact_uri
        and ":latest" not in artifact_uri
    )


def build_releases(
    *,
    policy: dict[str, Any],
    rollout_guard: dict[str, Any],
    trace_quality: dict[str, Any],
    token_cost: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    synthetic_probe: dict[str, Any],
) -> list[dict[str, Any]]:
    costs_by_scenario = by_scenario(token_cost.get("scenarios", []))
    ledger_by_scenario = by_scenario(error_budget.get("ledger", []))
    rollback_by_scenario = by_scenario(rollback_drill.get("drills", []))
    probe_by_scenario = by_scenario(synthetic_probe.get("probes", []))
    releases = []
    for release in policy.get("releases", []):
        scenario = str(release["scenario"])
        cost = costs_by_scenario.get(scenario, {})
        ledger = ledger_by_scenario.get(scenario, {})
        rollback = rollback_by_scenario.get(scenario, {})
        probe = probe_by_scenario.get(scenario, {})
        releases.append(
            {
                "name": release["name"],
                "role": release.get("role"),
                "scenario": scenario,
                "model_variant": release.get("model_variant"),
                "service_version": release.get("service_version"),
                "artifact_uri": release.get("artifact_uri"),
                "artifact_sha256": release.get("artifact_sha256"),
                "artifact_pinned": artifact_pinned(release),
                "quality_score": release.get("quality_score"),
                "minimum_quality_score": release.get("minimum_quality_score"),
                "schema_compatible": release.get("schema_compatible"),
                "safety_eval_passed": release.get("safety_eval_passed"),
                "canary_percent": release.get("canary_percent"),
                "previous_release": release.get("previous_release"),
                "rollback_target": release.get("rollback_target"),
                "max_cost_delta_percent": release.get("max_cost_delta_percent"),
                "expected": {
                    "probe": release.get("expected_probe"),
                    "budget_decision": release.get("expected_budget_decision"),
                    "release_action": release.get("expected_release_action"),
                    "cost_decision": release.get("expected_cost_decision"),
                    "rollout_decision": release.get("expected_rollout_decision"),
                    "requires_rollback": bool(release.get("requires_rollback")),
                },
                "cost": {
                    "decision": cost.get("decision"),
                    "model_variant": cost.get("model_variant"),
                    "estimated_cost_per_1k_requests": cost.get("estimated_cost_per_1k_requests"),
                    "violations": cost.get("violations", []),
                },
                "budget_decision": ledger.get("decision"),
                "release_action": ledger.get("release_action"),
                "rollback": {
                    "response_type": rollback.get("response_type"),
                    "within_rto": rollback.get("within_rto"),
                    "completion_minutes": rollback.get("completion_minutes"),
                },
                "probe": {
                    "name": probe.get("name"),
                    "signal_ok": probe.get("signal_ok"),
                    "release_action": probe.get("release_action"),
                    "model_variant": (probe.get("observed") or {}).get("model_variant"),
                    "service_version": (probe.get("observed") or {}).get("service_version"),
                },
                "rollout_guard": {
                    "candidate": rollout_guard.get("candidate"),
                    "candidate_version": rollout_guard.get("candidate_version"),
                    "decision": rollout_guard.get("decision"),
                    "violations": rollout_guard.get("violations", []),
                },
                "trace_quality_status": trace_quality.get("status"),
            }
        )
    return releases


def cost_delta_percent(release: dict[str, Any], baseline: dict[str, Any]) -> float:
    release_cost = float(release["cost"].get("estimated_cost_per_1k_requests") or 0.0)
    baseline_cost = float(baseline["cost"].get("estimated_cost_per_1k_requests") or 0.0)
    if baseline_cost <= 0:
        return 0.0
    return round(((release_cost - baseline_cost) / baseline_cost) * 100, 2)


def trace_service_versions(trace_quality: dict[str, Any]) -> set[str]:
    service_version = trace_quality.get("cardinality", {}).get("service.version", {})
    return {str(item) for item in service_version.get("values", [])}


def evaluate_releases(
    releases: list[dict[str, Any]],
    policy: dict[str, Any],
    trace_quality: dict[str, Any],
) -> dict[str, Any]:
    releases_by_name = by_name(releases)
    stable_releases = [item for item in releases if item.get("role") == "stable"]
    candidate_releases = [item for item in releases if item.get("role") == "candidate"]
    baseline = stable_releases[0] if stable_releases else {}
    artifact_gaps = []
    for item in releases:
        if not item["artifact_pinned"]:
            artifact_gaps.append({"release": item["name"], "reason": "artifact_not_pinned"})
        previous = item.get("previous_release")
        rollback_target = item.get("rollback_target")
        if previous and previous not in releases_by_name:
            artifact_gaps.append({"release": item["name"], "reason": "missing_previous_release", "previous": previous})
        if rollback_target and rollback_target not in releases_by_name:
            artifact_gaps.append(
                {"release": item["name"], "reason": "missing_rollback_target", "rollback_target": rollback_target}
            )
    eval_gaps = []
    for item in releases:
        quality_score = float(item.get("quality_score") or 0.0)
        minimum_quality_score = float(item.get("minimum_quality_score") or 0.0)
        eval_ok = (
            quality_score >= minimum_quality_score
            and item.get("schema_compatible") is True
            and item.get("safety_eval_passed") is True
        )
        if item.get("role") == "stable" and not eval_ok:
            eval_gaps.append({"release": item["name"], "reason": "stable_release_failed_eval"})
        if item.get("role") == "candidate" and not eval_ok and item.get("release_action") != "block_release_or_rollback":
            eval_gaps.append(
                {
                    "release": item["name"],
                    "reason": "unsafe_candidate_not_blocked",
                    "release_action": item.get("release_action"),
                }
            )
    canary_gaps = []
    max_canary_percent = int(policy.get("max_candidate_canary_percent", 0))
    for item in candidate_releases:
        canary_percent = int(item.get("canary_percent") or 0)
        if canary_percent <= 0 or canary_percent > max_canary_percent:
            canary_gaps.append(
                {
                    "release": item["name"],
                    "reason": "canary_percent_out_of_bounds",
                    "canary_percent": canary_percent,
                    "max_canary_percent": max_canary_percent,
                }
            )
        rollout = item["rollout_guard"]
        expected = item["expected"]
        if rollout.get("candidate") != item.get("scenario") or rollout.get("candidate_version") != item.get("service_version"):
            canary_gaps.append({"release": item["name"], "reason": "rollout_guard_candidate_mismatch", "rollout": rollout})
        if rollout.get("decision") != expected.get("rollout_decision"):
            canary_gaps.append(
                {
                    "release": item["name"],
                    "reason": "rollout_decision_mismatch",
                    "expected": expected.get("rollout_decision"),
                    "observed": rollout.get("decision"),
                }
            )
        if rollout.get("decision") == "rollback" and item.get("release_action") != "block_release_or_rollback":
            canary_gaps.append({"release": item["name"], "reason": "rollback_decision_not_blocked"})
    cost_gaps = []
    for item in releases:
        expected = item["expected"]
        if item["cost"].get("decision") != expected.get("cost_decision"):
            cost_gaps.append(
                {
                    "release": item["name"],
                    "reason": "cost_decision_mismatch",
                    "expected": expected.get("cost_decision"),
                    "observed": item["cost"].get("decision"),
                }
            )
        if item.get("role") == "candidate" and baseline:
            observed_delta = cost_delta_percent(item, baseline)
            max_delta = float(item.get("max_cost_delta_percent") or 0.0)
            item["cost"]["delta_percent_vs_stable"] = observed_delta
            if observed_delta > max_delta and item.get("release_action") not in BLOCKING_ACTIONS:
                cost_gaps.append(
                    {
                        "release": item["name"],
                        "reason": "cost_delta_not_blocked",
                        "delta_percent": observed_delta,
                        "max_cost_delta_percent": max_delta,
                    }
                )
    release_gaps = []
    for item in releases:
        expected = item["expected"]
        if item.get("budget_decision") != expected.get("budget_decision"):
            release_gaps.append(
                {
                    "release": item["name"],
                    "reason": "budget_decision_mismatch",
                    "expected": expected.get("budget_decision"),
                    "observed": item.get("budget_decision"),
                }
            )
        if item.get("release_action") != expected.get("release_action"):
            release_gaps.append(
                {
                    "release": item["name"],
                    "reason": "release_action_mismatch",
                    "expected": expected.get("release_action"),
                    "observed": item.get("release_action"),
                }
            )
    rollback_gaps = []
    for item in candidate_releases:
        expected = item["expected"]
        if not expected.get("requires_rollback") and item.get("release_action") != "block_release_or_rollback":
            continue
        rollback_target = item.get("rollback_target")
        target = releases_by_name.get(str(rollback_target), {})
        if not rollback_target:
            rollback_gaps.append({"release": item["name"], "reason": "missing_rollback_target"})
        elif not target.get("artifact_pinned"):
            rollback_gaps.append({"release": item["name"], "reason": "rollback_target_not_pinned", "target": rollback_target})
        rollback = item["rollback"]
        if rollback.get("response_type") != "rollback_required" or rollback.get("within_rto") is not True:
            rollback_gaps.append({"release": item["name"], "reason": "rollback_drill_not_ready", "rollback": rollback})
    observability_gaps = []
    service_versions = trace_service_versions(trace_quality)
    for item in releases:
        if item.get("trace_quality_status") != "pass":
            observability_gaps.append({"release": item["name"], "reason": "trace_quality_not_pass"})
        if str(item.get("service_version")) not in service_versions:
            observability_gaps.append(
                {
                    "release": item["name"],
                    "reason": "missing_service_version_trace_label",
                    "service_version": item.get("service_version"),
                }
            )
        probe = item["probe"]
        expected = item["expected"]
        if probe.get("name") != expected.get("probe") or probe.get("signal_ok") is not True:
            observability_gaps.append(
                {
                    "release": item["name"],
                    "reason": "probe_mismatch",
                    "expected": expected.get("probe"),
                    "observed": probe,
                }
            )
        if probe.get("model_variant") != item.get("model_variant"):
            observability_gaps.append(
                {
                    "release": item["name"],
                    "reason": "probe_model_variant_mismatch",
                    "expected": item.get("model_variant"),
                    "observed": probe.get("model_variant"),
                }
            )
        if probe.get("release_action") != item.get("release_action"):
            observability_gaps.append(
                {
                    "release": item["name"],
                    "reason": "probe_release_action_mismatch",
                    "probe_release_action": probe.get("release_action"),
                    "release_action": item.get("release_action"),
                }
            )
    checks = [
        check(
            "artifact_inventory",
            len(releases) >= int(policy.get("minimum_release_count", 0))
            and len(candidate_releases) >= int(policy.get("minimum_candidate_count", 0))
            and not artifact_gaps,
            {
                "release_count": len(releases),
                "candidate_count": len(candidate_releases),
                "gaps": artifact_gaps,
            },
        ),
        check("eval_schema_gate", not eval_gaps, {"gaps": eval_gaps}),
        check("canary_rollout_gate", not canary_gaps, {"gaps": canary_gaps}),
        check("cost_budget_gate", not cost_gaps, {"gaps": cost_gaps}),
        check("release_budget_linkage", not release_gaps, {"gaps": release_gaps}),
        check("rollback_contract", not rollback_gaps, {"gaps": rollback_gaps}),
        check("observability_contract", not observability_gaps, {"gaps": observability_gaps}),
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "checks": checks,
        "candidate_count": len(candidate_releases),
        "blocked_candidate_count": sum(1 for item in candidate_releases if item.get("release_action") == "block_release_or_rollback"),
        "failed_count": sum(1 for item in checks if not item["ok"]),
    }


def mutate_fixture(policy: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(policy)
    releases = by_name(mutated.get("releases", []))
    release_name = str(fixture["release"])
    mutation = fixture["mutation"]
    if mutation == "remove_release":
        mutated["releases"] = [
            item
            for item in mutated.get("releases", [])
            if item.get("name") != release_name
        ]
    elif mutation == "set_artifact_uri":
        releases[release_name]["artifact_uri"] = fixture["artifact_uri"]
    elif mutation == "set_quality_score":
        releases[release_name]["quality_score"] = float(fixture["quality_score"])
    elif mutation == "set_canary_percent":
        releases[release_name]["canary_percent"] = int(fixture["canary_percent"])
    elif mutation == "set_expected_cost_decision":
        releases[release_name]["expected_cost_decision"] = str(fixture["expected_cost_decision"])
    elif mutation == "set_rollback_target":
        releases[release_name]["rollback_target"] = fixture.get("rollback_target")
    elif mutation == "set_expected_probe":
        releases[release_name]["expected_probe"] = str(fixture["expected_probe"])
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    *,
    policy: dict[str, Any],
    rollout_guard: dict[str, Any],
    trace_quality: dict[str, Any],
    token_cost: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    synthetic_probe: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_policy = mutate_fixture(policy, fixture)
        releases = build_releases(
            policy=mutated_policy,
            rollout_guard=rollout_guard,
            trace_quality=trace_quality,
            token_cost=token_cost,
            error_budget=error_budget,
            rollback_drill=rollback_drill,
            synthetic_probe=synthetic_probe,
        )
        report = evaluate_releases(releases, mutated_policy, trace_quality)
        expected_failed_check = fixture["expected_failed_check"]
        failed_checks = [item["name"] for item in report["checks"] if not item["ok"]]
        results.append(
            {
                "name": fixture["name"],
                "mutation": fixture["mutation"],
                "release": fixture["release"],
                "expected_failed_check": expected_failed_check,
                "failed_checks": failed_checks,
                "detected": expected_failed_check in failed_checks,
            }
        )
    return results


def build_report(
    *,
    policy: dict[str, Any],
    rollout_guard: dict[str, Any],
    trace_quality: dict[str, Any],
    token_cost: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    synthetic_probe: dict[str, Any],
) -> dict[str, Any]:
    releases = build_releases(
        policy=policy,
        rollout_guard=rollout_guard,
        trace_quality=trace_quality,
        token_cost=token_cost,
        error_budget=error_budget,
        rollback_drill=rollback_drill,
        synthetic_probe=synthetic_probe,
    )
    release_report = evaluate_releases(releases, policy, trace_quality)
    fixture_results = evaluate_fixtures(
        policy=policy,
        rollout_guard=rollout_guard,
        trace_quality=trace_quality,
        token_cost=token_cost,
        error_budget=error_budget,
        rollback_drill=rollback_drill,
        synthetic_probe=synthetic_probe,
    )
    undetected = [item for item in fixture_results if not item["detected"]]
    checks = release_report["checks"] + [
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
        "release_count": len(releases),
        "candidate_count": release_report["candidate_count"],
        "blocked_candidate_count": release_report["blocked_candidate_count"],
        "fixture_count": len(fixture_results),
        "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
        "failed_count": failed_count,
        "releases": releases,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "model-release-safety-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Model Release Safety Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that model-version rollout decisions are tied to",
        "artifact pinning, offline evaluation, schema compatibility, canary",
        "signals, token/GPU cost deltas, rollback evidence, and observability",
        "labels before production promotion.",
        "",
        "## Summary",
        "",
        f"- Releases: `{report['release_count']}`",
        f"- Candidate releases: `{report['candidate_count']}`",
        f"- Blocked candidates: `{report['blocked_candidate_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Releases",
        "",
        "| Release | Role | Scenario | Model | Version | Release action | Cost decision |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["releases"]:
        lines.append(
            "| `{name}` | `{role}` | `{scenario}` | `{model}` | `{version}` | `{release_action}` | `{cost}` |".format(
                name=item["name"],
                role=item["role"],
                scenario=item["scenario"],
                model=item["model_variant"],
                version=item["service_version"],
                release_action=item["release_action"],
                cost=item["cost"].get("decision"),
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Release | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item['release']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "model-release-safety-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/model-release-policy.json")
    parser.add_argument("--rollout-guard", default="docs/evidence/rollout-guard.json")
    parser.add_argument("--trace-quality", default="docs/evidence/trace-quality-audit.json")
    parser.add_argument("--token-cost", default="docs/evidence/token-cost-guard.json")
    parser.add_argument("--error-budget", default="docs/evidence/error-budget-ledger.json")
    parser.add_argument("--rollback-drill", default="docs/evidence/rollback-drill.json")
    parser.add_argument("--synthetic-probe", default="docs/evidence/synthetic-probe-audit.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(
        policy=load_json(Path(args.policy)),
        rollout_guard=load_json(Path(args.rollout_guard)),
        trace_quality=load_json(Path(args.trace_quality)),
        token_cost=load_json(Path(args.token_cost)),
        error_budget=load_json(Path(args.error_budget)),
        rollback_drill=load_json(Path(args.rollback_drill)),
        synthetic_probe=load_json(Path(args.synthetic_probe)),
    )
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'model-release-safety-audit.json'}")
    print(f"wrote {output_dir / 'model-release-safety-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
