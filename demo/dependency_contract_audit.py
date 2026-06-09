#!/usr/bin/env python3
"""Audit dependency contracts for AI inference incident paths."""

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


def by_dependency(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["name"]): item
        for item in policy.get("dependencies", [])
        if item.get("name")
    }


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def alert_by_scenario(alerting: dict[str, Any]) -> dict[str, dict[str, Any]]:
    alerts = {}
    for item in alerting.get("alerts", []):
        scenario = item.get("labels", {}).get("scenario")
        if scenario:
            alerts[str(scenario)] = item
    return alerts


def latency_for_dependency(dependency: dict[str, Any], critical_path: dict[str, Any]) -> float | None:
    span_name = dependency.get("span_name")
    if not span_name:
        return None
    scenario = str(dependency["scenario"])
    for item in critical_path.get("scenarios", []):
        if item.get("scenario") != scenario:
            continue
        spans = item.get("average_child_span_ms", {})
        value = spans.get(span_name)
        return float(value) if value is not None else None
    return None


def dominant_span_for_scenario(scenario: str, critical_path: dict[str, Any]) -> str | None:
    for item in critical_path.get("scenarios", []):
        if item.get("scenario") == scenario:
            return item.get("dominant_span")
    return None


def trace_attributes_present(required: list[str], summary_item: dict[str, Any]) -> bool:
    known = {
        "cache.result": "cache_miss_rate",
        "collector.queue_pressure": "collector_queue_pressure",
        "dependency.name": "dependency_ms",
        "incident.scenario": "scenario",
        "model.variant": "model_variant",
        "service.version": "service_version",
        "telemetry.loss_rate": "telemetry_loss_rate",
    }
    return all(known.get(attribute) in summary_item for attribute in required)


def build_contracts(
    *,
    summary: list[dict[str, Any]],
    critical_path: dict[str, Any],
    runbooks: dict[str, Any],
    alerting: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    summary_by_name = by_scenario(summary)
    runbook_by_name = by_scenario(runbooks.get("runbooks", []))
    alerts = alert_by_scenario(alerting)
    ledger_by_name = by_scenario(error_budget.get("ledger", []))
    rollback_by_name = by_scenario(rollback_drill.get("drills", []))
    contracts = []
    for dependency in policy.get("dependencies", []):
        scenario = str(dependency["scenario"])
        summary_item = summary_by_name.get(scenario, {})
        runbook = runbook_by_name.get(scenario, {})
        alert = alerts.get(scenario, {})
        ledger = ledger_by_name.get(scenario, {})
        rollback = rollback_by_name.get(scenario, {})
        observed_latency_ms = latency_for_dependency(dependency, critical_path)
        telemetry_loss = summary_item.get("telemetry_loss_rate")
        contracts.append(
            {
                "name": dependency["name"],
                "scenario": scenario,
                "owner": dependency.get("owner"),
                "runbook_owner": runbook.get("owner"),
                "alert": alert.get("alert"),
                "alert_severity": alert.get("labels", {}).get("severity"),
                "runbook_url": alert.get("annotations", {}).get("runbook_url"),
                "observed_latency_ms": observed_latency_ms,
                "observed_telemetry_loss_rate": telemetry_loss,
                "dominant_span": dominant_span_for_scenario(scenario, critical_path),
                "span_name": dependency.get("span_name"),
                "budget_decision": ledger.get("decision"),
                "release_action": ledger.get("release_action"),
                "rollback_response": rollback.get("response_type"),
                "timeout_ms": dependency.get("timeout_ms"),
                "max_retries": dependency.get("max_retries"),
                "fallback": dependency.get("fallback"),
                "circuit_breaker": bool(dependency.get("circuit_breaker")),
                "persistent_queue_required": bool(dependency.get("persistent_queue_required")),
                "trace_attributes_present": trace_attributes_present(
                    list(dependency.get("required_trace_attributes", [])),
                    summary_item,
                ),
                "expected": {
                    "alert_severity": dependency.get("required_alert_severity"),
                    "budget_decision": dependency.get("required_budget_decision"),
                    "release_action": dependency.get("required_release_action"),
                    "rollback_response": dependency.get("required_rollback_response"),
                    "incident_trigger_ms": dependency.get("incident_trigger_ms"),
                    "telemetry_loss_trigger": dependency.get("telemetry_loss_trigger"),
                },
            }
        )
    return contracts


def evaluate_contracts(contracts: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    missing_contracts = [
        item["name"]
        for item in contracts
        if not item.get("scenario")
        or not item.get("runbook_owner")
        or not item.get("alert")
        or not item.get("budget_decision")
    ]
    owner_mismatches = [
        {
            "dependency": item["name"],
            "expected": item["owner"],
            "observed": item.get("runbook_owner"),
        }
        for item in contracts
        if item.get("owner") != item.get("runbook_owner")
    ]
    alert_violations = [
        {
            "dependency": item["name"],
            "scenario": item["scenario"],
            "expected": item["expected"]["alert_severity"],
            "observed": item.get("alert_severity"),
            "runbook_url": item.get("runbook_url"),
        }
        for item in contracts
        if item.get("alert_severity") != item["expected"]["alert_severity"]
        or f"#{item['scenario']}" not in str(item.get("runbook_url", ""))
    ]
    failure_signal_gaps = []
    dominant_count = 0
    for item in contracts:
        expected = item["expected"]
        if expected.get("incident_trigger_ms") is not None:
            observed = item.get("observed_latency_ms")
            if item.get("dominant_span") == item.get("span_name"):
                dominant_count += 1
            if observed is None or float(observed) < float(expected["incident_trigger_ms"]):
                failure_signal_gaps.append(
                    {
                        "dependency": item["name"],
                        "observed_latency_ms": observed,
                        "trigger_ms": expected["incident_trigger_ms"],
                    }
                )
        if expected.get("telemetry_loss_trigger") is not None:
            observed_loss = item.get("observed_telemetry_loss_rate")
            if observed_loss is None or float(observed_loss) < float(expected["telemetry_loss_trigger"]):
                failure_signal_gaps.append(
                    {
                        "dependency": item["name"],
                        "observed_telemetry_loss_rate": observed_loss,
                        "trigger": expected["telemetry_loss_trigger"],
                    }
                )
    release_action_gaps = [
        {
            "dependency": item["name"],
            "budget_decision": item.get("budget_decision"),
            "expected_budget_decision": item["expected"]["budget_decision"],
            "release_action": item.get("release_action"),
            "expected_release_action": item["expected"]["release_action"],
            "rollback_response": item.get("rollback_response"),
            "expected_rollback_response": item["expected"]["rollback_response"],
        }
        for item in contracts
        if item.get("budget_decision") != item["expected"]["budget_decision"]
        or item.get("release_action") != item["expected"]["release_action"]
        or item.get("rollback_response") != item["expected"]["rollback_response"]
    ]
    resilience_gaps = [
        item["name"]
        for item in contracts
        if not item.get("fallback")
        or int(item.get("max_retries") or 999) > 3
        or int(item.get("timeout_ms") or 0) <= 0
        or (
            item["name"] != "telemetry_exporter"
            and not item.get("circuit_breaker")
        )
        or (
            item["name"] == "telemetry_exporter"
            and not item.get("persistent_queue_required")
        )
        or not item.get("trace_attributes_present")
    ]
    checks = [
        check(
            "dependency_inventory",
            len(contracts) >= int(policy.get("minimum_dependency_count", 0))
            and not missing_contracts,
            {
                "dependency_count": len(contracts),
                "missing_contracts": missing_contracts,
            },
        ),
        check(
            "owner_runbook_contract",
            not owner_mismatches,
            {"mismatches": owner_mismatches},
        ),
        check(
            "alert_contract",
            not alert_violations,
            {"violations": alert_violations},
        ),
        check(
            "failure_mode_contract",
            not failure_signal_gaps and dominant_count >= 3,
            {"gaps": failure_signal_gaps, "dominant_dependency_count": dominant_count},
        ),
        check(
            "release_action_contract",
            not release_action_gaps,
            {"gaps": release_action_gaps},
        ),
        check(
            "resilience_settings",
            not resilience_gaps,
            {"gaps": resilience_gaps},
        ),
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "checks": checks,
        "failed_count": sum(1 for item in checks if not item["ok"]),
        "dominant_dependency_count": dominant_count,
        "contracts": contracts,
    }


def mutate_fixture(
    *,
    summary: list[dict[str, Any]],
    critical_path: dict[str, Any],
    alerting: dict[str, Any],
    error_budget: dict[str, Any],
    policy: dict[str, Any],
    fixture: dict[str, Any],
) -> dict[str, Any]:
    mutated = {
        "summary": copy.deepcopy(summary),
        "critical_path": copy.deepcopy(critical_path),
        "alerting": copy.deepcopy(alerting),
        "error_budget": copy.deepcopy(error_budget),
        "policy": copy.deepcopy(policy),
    }
    dependencies = by_dependency(mutated["policy"])
    dependency = dependencies[str(fixture["dependency"])]
    scenario = str(dependency["scenario"])
    mutation = fixture["mutation"]
    if mutation == "remove_dependency_owner":
        dependency["owner"] = ""
    elif mutation == "set_alert_severity":
        for alert in mutated["alerting"].get("alerts", []):
            if alert.get("labels", {}).get("scenario") == scenario:
                alert.setdefault("labels", {})["severity"] = str(fixture["severity"])
    elif mutation == "remove_fallback":
        dependency["fallback"] = ""
    elif mutation == "set_release_action":
        for item in mutated["error_budget"].get("ledger", []):
            if item.get("scenario") == scenario:
                item["release_action"] = str(fixture["release_action"])
    elif mutation == "lower_failure_signal":
        span_name = dependency.get("span_name")
        for item in mutated["critical_path"].get("scenarios", []):
            if item.get("scenario") == scenario and span_name:
                item.setdefault("average_child_span_ms", {})[span_name] = fixture["observed_ms"]
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    *,
    summary: list[dict[str, Any]],
    critical_path: dict[str, Any],
    runbooks: dict[str, Any],
    alerting: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = mutate_fixture(
            summary=summary,
            critical_path=critical_path,
            alerting=alerting,
            error_budget=error_budget,
            policy=policy,
            fixture=fixture,
        )
        contracts = build_contracts(
            summary=mutated["summary"],
            critical_path=mutated["critical_path"],
            runbooks=runbooks,
            alerting=mutated["alerting"],
            error_budget=mutated["error_budget"],
            rollback_drill=rollback_drill,
            policy=mutated["policy"],
        )
        report = evaluate_contracts(contracts, mutated["policy"])
        expected_failed_check = fixture["expected_failed_check"]
        failed_checks = [item["name"] for item in report["checks"] if not item["ok"]]
        results.append(
            {
                "name": fixture["name"],
                "mutation": fixture["mutation"],
                "dependency": fixture["dependency"],
                "expected_failed_check": expected_failed_check,
                "failed_checks": failed_checks,
                "detected": expected_failed_check in failed_checks,
            }
        )
    return results


def build_report(
    *,
    summary: list[dict[str, Any]],
    critical_path: dict[str, Any],
    runbooks: dict[str, Any],
    alerting: dict[str, Any],
    error_budget: dict[str, Any],
    rollback_drill: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    contracts = build_contracts(
        summary=summary,
        critical_path=critical_path,
        runbooks=runbooks,
        alerting=alerting,
        error_budget=error_budget,
        rollback_drill=rollback_drill,
        policy=policy,
    )
    contract_report = evaluate_contracts(contracts, policy)
    fixture_results = evaluate_fixtures(
        summary=summary,
        critical_path=critical_path,
        runbooks=runbooks,
        alerting=alerting,
        error_budget=error_budget,
        rollback_drill=rollback_drill,
        policy=policy,
    )
    undetected = [item for item in fixture_results if not item["detected"]]
    checks = contract_report["checks"] + [
        check(
            "negative_fixture_coverage",
            not undetected and len(fixture_results) >= 5,
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
        "dependency_count": len(contracts),
        "incident_contract_count": len([item for item in contracts if item.get("scenario") != "baseline"]),
        "dominant_dependency_count": contract_report["dominant_dependency_count"],
        "fixture_count": len(fixture_results),
        "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
        "failed_count": failed_count,
        "contracts": contracts,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dependency-contract-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Dependency Contract Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that critical inference dependencies have owners,",
        "timeout/retry/fallback controls, alert routing, runbook linkage,",
        "failure-mode evidence, and release-action linkage before their",
        "signals are trusted by the release gate.",
        "",
        "## Summary",
        "",
        f"- Dependencies: `{report['dependency_count']}`",
        f"- Incident contracts: `{report['incident_contract_count']}`",
        f"- Dominant dependency signals: `{report['dominant_dependency_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Contracts",
        "",
        "| Dependency | Scenario | Owner | Alert | Release action | Signal |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for item in report["contracts"]:
        signal = item.get("observed_latency_ms")
        if signal is None:
            signal = item.get("observed_telemetry_loss_rate")
        lines.append(
            "| `{name}` | `{scenario}` | {owner} | `{alert_severity}` | `{release_action}` | `{signal}` |".format(
                signal=signal,
                **item,
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Dependency | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item['dependency']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dependency-contract-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/dependency-contract-policy.json")
    parser.add_argument("--summary", default="docs/evidence/sample-summary.json")
    parser.add_argument("--critical-path", default="docs/evidence/critical-path-attribution.json")
    parser.add_argument("--runbooks", default="docs/evidence/incident-runbooks.json")
    parser.add_argument("--alerting", default="docs/evidence/alerting-rules.json")
    parser.add_argument("--error-budget", default="docs/evidence/error-budget-ledger.json")
    parser.add_argument("--rollback-drill", default="docs/evidence/rollback-drill.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(
        summary=load_json(Path(args.summary)),
        critical_path=load_json(Path(args.critical_path)),
        runbooks=load_json(Path(args.runbooks)),
        alerting=load_json(Path(args.alerting)),
        error_budget=load_json(Path(args.error_budget)),
        rollback_drill=load_json(Path(args.rollback_drill)),
        policy=load_json(Path(args.policy)),
    )
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'dependency-contract-audit.json'}")
    print(f"wrote {output_dir / 'dependency-contract-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
