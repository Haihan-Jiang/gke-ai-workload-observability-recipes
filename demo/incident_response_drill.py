#!/usr/bin/env python3
"""Verify incident-response routes from alert to mitigation evidence."""

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


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def phase_minutes(timeline: list[dict[str, Any]]) -> dict[str, int]:
    return {
        str(item["phase"]): int(item["minute"])
        for item in timeline
        if item.get("phase") is not None and item.get("minute") is not None
    }


def route_for_severity(policy: dict[str, Any], severity: str) -> dict[str, Any] | None:
    route = policy.get("severity_routes", {}).get(severity)
    return dict(route) if isinstance(route, dict) else None


def baseline_timeline(policy: dict[str, Any]) -> list[dict[str, Any]]:
    return copy.deepcopy(policy.get("baseline_control_timeline", []))


def alert_by_scenario(alerting: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for alert in alerting.get("alerts", []):
        scenario = alert.get("labels", {}).get("scenario")
        if scenario:
            result[str(scenario)] = alert
    return result


def evidence_links(scenario: str, policy: dict[str, Any]) -> list[str]:
    links = list(policy.get("required_core_evidence", []))
    if scenario in set(policy.get("incident_scenarios", [])):
        links.extend(policy.get("required_incident_evidence", []))
    return links


def build_responses(
    *,
    alerting: dict[str, Any],
    runbooks: dict[str, Any],
    incident_correlation: dict[str, Any],
    rollback_drill: dict[str, Any],
    post_incident_review: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    alerts = alert_by_scenario(alerting)
    runbook_by_name = by_scenario(runbooks.get("runbooks", []))
    correlation_by_name = by_scenario(incident_correlation.get("incidents", []))
    drill_by_name = by_scenario(rollback_drill.get("drills", []))
    review_by_name = by_scenario(post_incident_review.get("reviews", []))
    responses = []
    for scenario in policy.get("required_scenarios", []):
        alert = alerts.get(str(scenario), {})
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        severity = str(labels.get("severity", "missing"))
        route = route_for_severity(policy, severity)
        runbook = runbook_by_name.get(str(scenario), {})
        drill = drill_by_name.get(str(scenario))
        timeline = copy.deepcopy(drill["timeline"]) if drill else baseline_timeline(policy)
        minutes = phase_minutes(timeline)
        response = {
            "scenario": scenario,
            "alert": alert.get("alert", "missing"),
            "severity": severity,
            "route_known": route is not None,
            "runbook_owner": runbook.get("owner", ""),
            "runbook_url": annotations.get("runbook_url", ""),
            "ack_minutes": minutes.get("acknowledge"),
            "mitigation_minutes": minutes.get("mitigate"),
            "verification_minutes": minutes.get("verify"),
            "ack_sla_minutes": route.get("ack_sla_minutes") if route else None,
            "mitigation_sla_minutes": route.get("mitigation_sla_minutes") if route else None,
            "verification_sla_minutes": route.get("verification_sla_minutes") if route else None,
            "escalation": route.get("escalation", []) if route else [],
            "minimum_escalation_steps": route.get("minimum_escalation_steps") if route else None,
            "timeline": timeline,
            "timeline_phases": sorted(minutes),
            "correlation_key": correlation_by_name.get(str(scenario), {}).get("dedupe_key"),
            "rollback_response_type": drill.get("response_type") if drill else "baseline_control",
            "post_incident_review_status": review_by_name.get(str(scenario), {}).get("status"),
            "evidence_links": evidence_links(str(scenario), policy),
        }
        response["within_ack_sla"] = (
            response["ack_minutes"] is not None
            and response["ack_sla_minutes"] is not None
            and int(response["ack_minutes"]) <= int(response["ack_sla_minutes"])
        )
        response["within_mitigation_sla"] = (
            response["mitigation_minutes"] is not None
            and response["mitigation_sla_minutes"] is not None
            and int(response["mitigation_minutes"]) <= int(response["mitigation_sla_minutes"])
        )
        response["within_verification_sla"] = (
            response["verification_minutes"] is not None
            and response["verification_sla_minutes"] is not None
            and int(response["verification_minutes"]) <= int(response["verification_sla_minutes"])
        )
        responses.append(response)
    return responses


def evaluate_contract(
    *,
    alerting: dict[str, Any],
    runbooks: dict[str, Any],
    incident_correlation: dict[str, Any],
    rollback_drill: dict[str, Any],
    post_incident_review: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    required = set(str(item) for item in policy.get("required_scenarios", []))
    incident_scenarios = set(str(item) for item in policy.get("incident_scenarios", []))
    alerts = alert_by_scenario(alerting)
    runbook_by_name = by_scenario(runbooks.get("runbooks", []))
    correlation_by_name = by_scenario(incident_correlation.get("incidents", []))
    drill_by_name = by_scenario(rollback_drill.get("drills", []))
    review_by_name = by_scenario(post_incident_review.get("reviews", []))
    responses = build_responses(
        alerting=alerting,
        runbooks=runbooks,
        incident_correlation=incident_correlation,
        rollback_drill=rollback_drill,
        post_incident_review=post_incident_review,
        policy=policy,
    )
    response_by_name = by_scenario(responses)
    missing_alerts = sorted(required - set(alerts))
    missing_runbooks = sorted(required - set(runbook_by_name))
    missing_incident_correlation = sorted(incident_scenarios - set(correlation_by_name))
    missing_drills = sorted(incident_scenarios - set(drill_by_name))
    missing_reviews = sorted(incident_scenarios - set(review_by_name))
    missing_owners = sorted(
        item["scenario"]
        for item in responses
        if not str(item.get("runbook_owner", "")).strip()
    )
    sla_violations = [
        {
            "scenario": item["scenario"],
            "severity": item["severity"],
            "ack": item["ack_minutes"],
            "ack_sla": item["ack_sla_minutes"],
            "mitigate": item["mitigation_minutes"],
            "mitigation_sla": item["mitigation_sla_minutes"],
            "verify": item["verification_minutes"],
            "verification_sla": item["verification_sla_minutes"],
        }
        for item in responses
        if not item["route_known"]
        or not item["within_ack_sla"]
        or not item["within_mitigation_sla"]
        or not item["within_verification_sla"]
    ]
    required_phases = set(policy.get("required_timeline_phases", []))
    missing_phases = {
        item["scenario"]: sorted(required_phases - set(item.get("timeline_phases", [])))
        for item in responses
        if required_phases - set(item.get("timeline_phases", []))
    }
    escalation_gaps = [
        {
            "scenario": item["scenario"],
            "severity": item["severity"],
            "steps": len(item.get("escalation", [])),
            "minimum": item.get("minimum_escalation_steps"),
        }
        for item in responses
        if not item["route_known"]
        or len(item.get("escalation", [])) < int(item.get("minimum_escalation_steps") or 0)
    ]
    checks = [
        check(
            "route_coverage",
            len(responses) >= int(policy.get("minimum_responses", 0))
            and not missing_alerts
            and not missing_runbooks,
            {
                "response_scenarios": sorted(response_by_name),
                "missing_alerts": missing_alerts,
                "missing_runbooks": missing_runbooks,
            },
        ),
        check(
            "owner_coverage",
            not missing_owners,
            {"missing_runbook_owners": missing_owners},
        ),
        check(
            "timeline_phase_coverage",
            not missing_phases,
            {"missing_phases": missing_phases},
        ),
        check(
            "response_sla",
            not sla_violations,
            {"violations": sla_violations},
        ),
        check(
            "escalation_coverage",
            not escalation_gaps,
            {"gaps": escalation_gaps},
        ),
        check(
            "incident_evidence_linkage",
            len(incident_scenarios) >= int(policy.get("minimum_incident_responses", 0))
            and not missing_incident_correlation
            and not missing_drills
            and not missing_reviews,
            {
                "incident_scenarios": sorted(incident_scenarios),
                "missing_correlation": missing_incident_correlation,
                "missing_rollback_drill": missing_drills,
                "missing_post_incident_review": missing_reviews,
            },
        ),
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "checks": checks,
        "failed_count": sum(1 for item in checks if not item["ok"]),
        "responses": responses,
    }


def set_timeline_phase_minute(timeline: list[dict[str, Any]], phase: str, minute: int) -> None:
    for item in timeline:
        if item.get("phase") == phase:
            item["minute"] = minute
            return


def mutate_fixture(
    *,
    alerting: dict[str, Any],
    runbooks: dict[str, Any],
    incident_correlation: dict[str, Any],
    rollback_drill: dict[str, Any],
    post_incident_review: dict[str, Any],
    policy: dict[str, Any],
    fixture: dict[str, Any],
) -> dict[str, Any]:
    mutated = {
        "alerting": copy.deepcopy(alerting),
        "runbooks": copy.deepcopy(runbooks),
        "incident_correlation": copy.deepcopy(incident_correlation),
        "rollback_drill": copy.deepcopy(rollback_drill),
        "post_incident_review": copy.deepcopy(post_incident_review),
        "policy": copy.deepcopy(policy),
    }
    scenario = str(fixture.get("scenario", ""))
    mutation = fixture["mutation"]
    if mutation == "remove_runbook_owner":
        for item in mutated["runbooks"].get("runbooks", []):
            if item.get("scenario") == scenario:
                item["owner"] = ""
    elif mutation == "slow_acknowledgement":
        severity = "page"
        for alert in mutated["alerting"].get("alerts", []):
            if alert.get("labels", {}).get("scenario") == scenario:
                severity = str(alert.get("labels", {}).get("severity", severity))
        route = mutated["policy"]["severity_routes"].get(severity, {})
        slow_minute = int(route.get("ack_sla_minutes", 0)) + 1
        for drill in mutated["rollback_drill"].get("drills", []):
            if drill.get("scenario") == scenario:
                set_timeline_phase_minute(drill.get("timeline", []), "acknowledge", slow_minute)
    elif mutation == "remove_escalation":
        severity = str(fixture["severity"])
        mutated["policy"]["severity_routes"].setdefault(severity, {})["escalation"] = []
    elif mutation == "remove_post_incident_review":
        mutated["post_incident_review"]["reviews"] = [
            item
            for item in mutated["post_incident_review"].get("reviews", [])
            if item.get("scenario") != scenario
        ]
    elif mutation == "set_alert_severity":
        for alert in mutated["alerting"].get("alerts", []):
            if alert.get("labels", {}).get("scenario") == scenario:
                alert.setdefault("labels", {})["severity"] = str(fixture["severity"])
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    *,
    alerting: dict[str, Any],
    runbooks: dict[str, Any],
    incident_correlation: dict[str, Any],
    rollback_drill: dict[str, Any],
    post_incident_review: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("drill_fixtures", []):
        mutated = mutate_fixture(
            alerting=alerting,
            runbooks=runbooks,
            incident_correlation=incident_correlation,
            rollback_drill=rollback_drill,
            post_incident_review=post_incident_review,
            policy=policy,
            fixture=fixture,
        )
        report = evaluate_contract(
            alerting=mutated["alerting"],
            runbooks=mutated["runbooks"],
            incident_correlation=mutated["incident_correlation"],
            rollback_drill=mutated["rollback_drill"],
            post_incident_review=mutated["post_incident_review"],
            policy=mutated["policy"],
        )
        expected_failed_check = fixture["expected_failed_check"]
        failed_checks = [item["name"] for item in report["checks"] if not item["ok"]]
        results.append(
            {
                "name": fixture["name"],
                "mutation": fixture["mutation"],
                "scenario": fixture.get("scenario"),
                "severity": fixture.get("severity"),
                "expected_failed_check": expected_failed_check,
                "failed_checks": failed_checks,
                "detected": expected_failed_check in failed_checks,
            }
        )
    return results


def build_report(
    *,
    alerting: dict[str, Any],
    runbooks: dict[str, Any],
    incident_correlation: dict[str, Any],
    rollback_drill: dict[str, Any],
    post_incident_review: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    contract = evaluate_contract(
        alerting=alerting,
        runbooks=runbooks,
        incident_correlation=incident_correlation,
        rollback_drill=rollback_drill,
        post_incident_review=post_incident_review,
        policy=policy,
    )
    fixture_results = evaluate_fixtures(
        alerting=alerting,
        runbooks=runbooks,
        incident_correlation=incident_correlation,
        rollback_drill=rollback_drill,
        post_incident_review=post_incident_review,
        policy=policy,
    )
    undetected = [item for item in fixture_results if not item["detected"]]
    checks = contract["checks"] + [
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
    responses = contract["responses"]
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "response_count": len(responses),
        "incident_response_count": sum(1 for item in responses if item["scenario"] in policy.get("incident_scenarios", [])),
        "page_count": sum(1 for item in responses if item["severity"] == "page"),
        "ticket_count": sum(1 for item in responses if item["severity"] == "ticket"),
        "fixture_count": len(fixture_results),
        "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
        "failed_count": failed_count,
        "responses": responses,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "incident-response-drill.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Incident Response Drill",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This drill verifies the executable response path behind the lab's",
        "generated alerts. It checks that each alert has a runbook owner, an",
        "SLA-bound acknowledgement/mitigation/verification path, escalation",
        "steps, and incident evidence for rollback and post-incident review.",
        "",
        "## Summary",
        "",
        f"- Responses: `{report['response_count']}`",
        f"- Incident responses: `{report['incident_response_count']}`",
        f"- Page routes: `{report['page_count']}`",
        f"- Ticket routes: `{report['ticket_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Routes",
        "",
        "| Scenario | Severity | Owner | Ack | Mitigate | Verify |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for item in report["responses"]:
        lines.append(
            "| `{scenario}` | `{severity}` | {runbook_owner} | {ack_minutes}m/{ack_sla_minutes}m | {mitigation_minutes}m/{mitigation_sla_minutes}m | {verification_minutes}m/{verification_sla_minutes}m |".format(
                **item
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Scenario | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        target = item.get("scenario") or item.get("severity") or ""
        lines.append(
            f"| `{item['name']}` | `{target}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "incident-response-drill.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/incident-response-policy.json")
    parser.add_argument("--alerting", default="docs/evidence/alerting-rules.json")
    parser.add_argument("--runbooks", default="docs/evidence/incident-runbooks.json")
    parser.add_argument("--incident-correlation", default="docs/evidence/incident-correlation.json")
    parser.add_argument("--rollback-drill", default="docs/evidence/rollback-drill.json")
    parser.add_argument("--post-incident-review", default="docs/evidence/post-incident-review.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(
        alerting=load_json(Path(args.alerting)),
        runbooks=load_json(Path(args.runbooks)),
        incident_correlation=load_json(Path(args.incident_correlation)),
        rollback_drill=load_json(Path(args.rollback_drill)),
        post_incident_review=load_json(Path(args.post_incident_review)),
        policy=load_json(Path(args.policy)),
    )
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'incident-response-drill.json'}")
    print(f"wrote {output_dir / 'incident-response-drill.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
