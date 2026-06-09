#!/usr/bin/env python3
"""Audit synthetic preflight probes for AI inference release readiness."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def by_scenario(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item["scenario"]): item
        for item in items
        if item.get("scenario")
    }


def by_probe(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["name"]): item
        for item in policy.get("probes", [])
        if item.get("name")
    }


def alert_by_scenario(alerting: dict[str, Any]) -> dict[str, dict[str, Any]]:
    alerts = {}
    for item in alerting.get("alerts", []):
        scenario = item.get("labels", {}).get("scenario")
        if scenario:
            alerts[str(scenario)] = item
    return alerts


def contracts_by_name(dependency_contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["name"]): item
        for item in dependency_contract.get("contracts", [])
        if item.get("name")
    }


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def metric_ok(summary_item: dict[str, Any], probe: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    failures = []
    metric_rules = [
        ("max_p95_ms", "p95_ms", "<="),
        ("min_p95_ms", "p95_ms", ">="),
        ("max_errors", "errors", "<="),
        ("min_errors", "errors", ">="),
        ("min_cache_miss_rate", "cache_miss_rate", ">="),
        ("max_telemetry_loss_rate", "telemetry_loss_rate", "<="),
        ("min_telemetry_loss_rate", "telemetry_loss_rate", ">="),
    ]
    for policy_field, summary_field, operator in metric_rules:
        if policy_field not in probe:
            continue
        observed = summary_item.get(summary_field)
        expected = probe[policy_field]
        ok = (
            observed is not None
            and (
                float(observed) <= float(expected)
                if operator == "<="
                else float(observed) >= float(expected)
            )
        )
        if not ok:
            failures.append(
                {
                    "field": summary_field,
                    "operator": operator,
                    "expected": expected,
                    "observed": observed,
                }
            )
    equality_rules = [
        ("expected_service_version", "service_version"),
        ("expected_model_variant", "model_variant"),
        ("required_queue_pressure", "collector_queue_pressure"),
    ]
    for policy_field, summary_field in equality_rules:
        if policy_field not in probe:
            continue
        expected = probe[policy_field]
        observed = summary_item.get(summary_field)
        if observed != expected:
            failures.append(
                {
                    "field": summary_field,
                    "operator": "==",
                    "expected": expected,
                    "observed": observed,
                }
            )
    return not failures, failures


def build_probe_results(
    *,
    summary: list[dict[str, Any]],
    alerting: dict[str, Any],
    dependency_contract: dict[str, Any],
    incident_response: dict[str, Any],
    rollback_drill: dict[str, Any],
    error_budget: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    summary_by_name = by_scenario(summary)
    alerts = alert_by_scenario(alerting)
    responses = by_scenario(incident_response.get("responses", []))
    rollbacks = by_scenario(rollback_drill.get("drills", []))
    ledger = by_scenario(error_budget.get("ledger", []))
    contracts = contracts_by_name(dependency_contract)
    results = []
    for probe in policy.get("probes", []):
        scenario = str(probe["scenario"])
        summary_item = summary_by_name.get(scenario, {})
        alert = alerts.get(scenario, {})
        response = responses.get(scenario, {})
        rollback = rollbacks.get(scenario, {})
        ledger_item = ledger.get(scenario, {})
        dependency_name = probe.get("dependency")
        contract = contracts.get(str(dependency_name), {}) if dependency_name else {}
        signal_ok, signal_failures = metric_ok(summary_item, probe)
        results.append(
            {
                "name": probe["name"],
                "scenario": scenario,
                "probe_type": probe.get("probe_type"),
                "dependency": dependency_name,
                "observed": {
                    "p95_ms": summary_item.get("p95_ms"),
                    "errors": summary_item.get("errors"),
                    "cache_miss_rate": summary_item.get("cache_miss_rate"),
                    "telemetry_loss_rate": summary_item.get("telemetry_loss_rate"),
                    "collector_queue_pressure": summary_item.get("collector_queue_pressure"),
                    "service_version": summary_item.get("service_version"),
                    "model_variant": summary_item.get("model_variant"),
                },
                "expected": {
                    "alert_severity": probe.get("expected_alert_severity"),
                    "release_action": probe.get("expected_release_action"),
                    "rollback_response": probe.get("expected_rollback_response"),
                    "requires_rollback": bool(probe.get("requires_rollback")),
                },
                "signal_ok": signal_ok,
                "signal_failures": signal_failures,
                "alert": alert.get("alert"),
                "alert_severity": alert.get("labels", {}).get("severity"),
                "runbook_url": alert.get("annotations", {}).get("runbook_url"),
                "response_route_known": response.get("route_known"),
                "response_owner": response.get("runbook_owner"),
                "within_ack_sla": response.get("within_ack_sla"),
                "within_mitigation_sla": response.get("within_mitigation_sla"),
                "within_verification_sla": response.get("within_verification_sla"),
                "response_rollback_type": response.get("rollback_response_type"),
                "rollback_drill_type": rollback.get("response_type"),
                "rollback_within_rto": rollback.get("within_rto"),
                "budget_decision": ledger_item.get("decision"),
                "release_action": ledger_item.get("release_action"),
                "dependency_contract": {
                    "name": contract.get("name"),
                    "scenario": contract.get("scenario"),
                    "owner": contract.get("owner"),
                    "alert_severity": contract.get("alert_severity"),
                    "release_action": contract.get("release_action"),
                    "rollback_response": contract.get("rollback_response"),
                },
            }
        )
    return results


def evaluate_probes(probes: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    missing_summary = [item["name"] for item in probes if item["observed"]["p95_ms"] is None]
    incident_probes = [item for item in probes if item["scenario"] != "baseline"]
    signal_failures = [
        {"probe": item["name"], "failures": item["signal_failures"]}
        for item in probes
        if not item["signal_ok"]
    ]
    dependency_gaps = []
    for item in incident_probes:
        dependency = item.get("dependency")
        contract = item.get("dependency_contract", {})
        if not dependency or not contract.get("name"):
            dependency_gaps.append({"probe": item["name"], "reason": "missing_dependency_contract"})
            continue
        expected = item["expected"]
        mismatches = []
        if contract.get("scenario") != item["scenario"]:
            mismatches.append("scenario")
        if contract.get("alert_severity") != expected.get("alert_severity"):
            mismatches.append("alert_severity")
        if contract.get("release_action") != expected.get("release_action"):
            mismatches.append("release_action")
        if contract.get("rollback_response") != expected.get("rollback_response"):
            mismatches.append("rollback_response")
        if mismatches:
            dependency_gaps.append(
                {
                    "probe": item["name"],
                    "dependency": dependency,
                    "mismatches": mismatches,
                }
            )
    alert_gaps = []
    for item in probes:
        if (
            not item.get("alert")
            or item.get("alert_severity") != item["expected"].get("alert_severity")
            or not item.get("response_route_known")
            or f"#{item['scenario']}" not in str(item.get("runbook_url", ""))
            or item.get("within_ack_sla") is not True
            or item.get("within_mitigation_sla") is not True
            or item.get("within_verification_sla") is not True
        ):
            alert_gaps.append(
                {
                    "probe": item["name"],
                    "alert": item.get("alert"),
                    "expected_severity": item["expected"].get("alert_severity"),
                    "observed_severity": item.get("alert_severity"),
                    "route_known": item.get("response_route_known"),
                    "runbook_url": item.get("runbook_url"),
                }
            )
    preflight_gaps = []
    preflight_block_count = 0
    for item in probes:
        expected = item["expected"]
        if item.get("release_action") != expected.get("release_action"):
            preflight_gaps.append(
                {
                    "probe": item["name"],
                    "expected_release_action": expected.get("release_action"),
                    "observed_release_action": item.get("release_action"),
                }
            )
        if item.get("release_action") == "block_release_or_rollback":
            preflight_block_count += 1
        if expected.get("requires_rollback"):
            if (
                item.get("response_rollback_type") != expected.get("rollback_response")
                or item.get("rollback_drill_type") != expected.get("rollback_response")
                or item.get("rollback_within_rto") is not True
            ):
                preflight_gaps.append(
                    {
                        "probe": item["name"],
                        "expected_rollback_response": expected.get("rollback_response"),
                        "response_rollback_type": item.get("response_rollback_type"),
                        "rollback_drill_type": item.get("rollback_drill_type"),
                        "rollback_within_rto": item.get("rollback_within_rto"),
                    }
                )
    checks = [
        check(
            "probe_inventory",
            len(probes) >= int(policy.get("minimum_probe_count", 0))
            and len(incident_probes) >= int(policy.get("minimum_incident_probe_count", 0))
            and not missing_summary,
            {
                "probe_count": len(probes),
                "incident_probe_count": len(incident_probes),
                "missing_summary": missing_summary,
            },
        ),
        check("signal_contract", not signal_failures, {"failures": signal_failures}),
        check("dependency_contract_linkage", not dependency_gaps, {"gaps": dependency_gaps}),
        check("alert_response_contract", not alert_gaps, {"gaps": alert_gaps}),
        check(
            "rollout_preflight_guard",
            not preflight_gaps
            and preflight_block_count >= int(policy.get("minimum_preflight_block_count", 0)),
            {
                "gaps": preflight_gaps,
                "preflight_block_count": preflight_block_count,
            },
        ),
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "checks": checks,
        "preflight_block_count": preflight_block_count,
        "failed_count": sum(1 for item in checks if not item["ok"]),
    }


def mutate_fixture(
    *,
    summary: list[dict[str, Any]],
    alerting: dict[str, Any],
    incident_response: dict[str, Any],
    rollback_drill: dict[str, Any],
    policy: dict[str, Any],
    fixture: dict[str, Any],
) -> dict[str, Any]:
    mutated = {
        "summary": copy.deepcopy(summary),
        "alerting": copy.deepcopy(alerting),
        "incident_response": copy.deepcopy(incident_response),
        "rollback_drill": copy.deepcopy(rollback_drill),
        "policy": copy.deepcopy(policy),
    }
    probes = by_probe(mutated["policy"])
    probe = probes[str(fixture["probe"])]
    scenario = str(probe["scenario"])
    mutation = fixture["mutation"]
    if mutation == "remove_probe":
        mutated["policy"]["probes"] = [
            item
            for item in mutated["policy"].get("probes", [])
            if item.get("name") != fixture["probe"]
        ]
    elif mutation == "set_summary_value":
        for item in mutated["summary"]:
            if item.get("scenario") == scenario:
                item[str(fixture["field"])] = fixture["value"]
    elif mutation == "clear_probe_dependency":
        probe["dependency"] = ""
    elif mutation == "set_alert_severity":
        for item in mutated["alerting"].get("alerts", []):
            if item.get("labels", {}).get("scenario") == scenario:
                item.setdefault("labels", {})["severity"] = str(fixture["severity"])
    elif mutation == "set_rollback_response":
        for item in mutated["rollback_drill"].get("drills", []):
            if item.get("scenario") == scenario:
                item["response_type"] = str(fixture["response_type"])
        for item in mutated["incident_response"].get("responses", []):
            if item.get("scenario") == scenario:
                item["rollback_response_type"] = str(fixture["response_type"])
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    *,
    summary: list[dict[str, Any]],
    alerting: dict[str, Any],
    dependency_contract: dict[str, Any],
    incident_response: dict[str, Any],
    rollback_drill: dict[str, Any],
    error_budget: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = mutate_fixture(
            summary=summary,
            alerting=alerting,
            incident_response=incident_response,
            rollback_drill=rollback_drill,
            policy=policy,
            fixture=fixture,
        )
        probes = build_probe_results(
            summary=mutated["summary"],
            alerting=mutated["alerting"],
            dependency_contract=dependency_contract,
            incident_response=mutated["incident_response"],
            rollback_drill=mutated["rollback_drill"],
            error_budget=error_budget,
            policy=mutated["policy"],
        )
        report = evaluate_probes(probes, mutated["policy"])
        expected_failed_check = fixture["expected_failed_check"]
        failed_checks = [item["name"] for item in report["checks"] if not item["ok"]]
        results.append(
            {
                "name": fixture["name"],
                "mutation": fixture["mutation"],
                "probe": fixture["probe"],
                "expected_failed_check": expected_failed_check,
                "failed_checks": failed_checks,
                "detected": expected_failed_check in failed_checks,
            }
        )
    return results


def build_report(
    *,
    summary: list[dict[str, Any]],
    alerting: dict[str, Any],
    dependency_contract: dict[str, Any],
    incident_response: dict[str, Any],
    rollback_drill: dict[str, Any],
    error_budget: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    probes = build_probe_results(
        summary=summary,
        alerting=alerting,
        dependency_contract=dependency_contract,
        incident_response=incident_response,
        rollback_drill=rollback_drill,
        error_budget=error_budget,
        policy=policy,
    )
    probe_report = evaluate_probes(probes, policy)
    fixture_results = evaluate_fixtures(
        summary=summary,
        alerting=alerting,
        dependency_contract=dependency_contract,
        incident_response=incident_response,
        rollback_drill=rollback_drill,
        error_budget=error_budget,
        policy=policy,
    )
    undetected = [item for item in fixture_results if not item["detected"]]
    checks = probe_report["checks"] + [
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
        "probe_count": len(probes),
        "incident_probe_count": len([item for item in probes if item["scenario"] != "baseline"]),
        "preflight_block_count": probe_report["preflight_block_count"],
        "fixture_count": len(fixture_results),
        "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
        "failed_count": failed_count,
        "probes": probes,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "synthetic-probe-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Synthetic Probe Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that preflight synthetic probes cover the healthy",
        "baseline, dependency failures, canary regression, and telemetry",
        "delivery failure before release promotion. Each probe must connect",
        "its replayed signal to alert routing, incident response, dependency",
        "contracts, error-budget action, and rollback evidence where needed.",
        "",
        "## Summary",
        "",
        f"- Probes: `{report['probe_count']}`",
        f"- Incident probes: `{report['incident_probe_count']}`",
        f"- Preflight block probes: `{report['preflight_block_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Probes",
        "",
        "| Probe | Scenario | Type | Dependency | Alert | Release action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["probes"]:
        dependency = item.get("dependency") or "none"
        lines.append(
            "| `{name}` | `{scenario}` | `{probe_type}` | `{dependency}` | `{alert_severity}` | `{release_action}` |".format(
                dependency=dependency,
                name=item["name"],
                scenario=item["scenario"],
                probe_type=item["probe_type"],
                alert_severity=item["alert_severity"],
                release_action=item["release_action"],
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Probe | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item['probe']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "synthetic-probe-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/synthetic-probe-policy.json")
    parser.add_argument("--summary", default="docs/evidence/sample-summary.json")
    parser.add_argument("--alerting", default="docs/evidence/alerting-rules.json")
    parser.add_argument("--dependency-contract", default="docs/evidence/dependency-contract-audit.json")
    parser.add_argument("--incident-response", default="docs/evidence/incident-response-drill.json")
    parser.add_argument("--rollback-drill", default="docs/evidence/rollback-drill.json")
    parser.add_argument("--error-budget", default="docs/evidence/error-budget-ledger.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(
        summary=load_json(Path(args.summary)),
        alerting=load_json(Path(args.alerting)),
        dependency_contract=load_json(Path(args.dependency_contract)),
        incident_response=load_json(Path(args.incident_response)),
        rollback_drill=load_json(Path(args.rollback_drill)),
        error_budget=load_json(Path(args.error_budget)),
        policy=load_json(Path(args.policy)),
    )
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'synthetic-probe-audit.json'}")
    print(f"wrote {output_dir / 'synthetic-probe-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
