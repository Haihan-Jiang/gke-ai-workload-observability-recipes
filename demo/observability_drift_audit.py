#!/usr/bin/env python3
"""Audit drift across alerting, dashboard, OpenSLO, and runbook evidence."""

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


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def check_evidence(report: dict[str, Any], check_name: str) -> dict[str, Any]:
    for item in report.get("checks", []):
        if item.get("name") == check_name:
            return dict(item.get("evidence", {}))
    return {}


def alert_scenarios(alerting: dict[str, Any]) -> set[str]:
    return {
        str(item.get("labels", {}).get("scenario"))
        for item in alerting.get("alerts", [])
        if item.get("labels", {}).get("scenario")
    }


def dashboard_scenarios(dashboard: dict[str, Any]) -> set[str]:
    scenarios = set(str(item) for item in dashboard.get("scenarios", []))
    scenarios.update(str(item) for item in check_evidence(dashboard, "scenario_coverage").get("observed", []))
    return scenarios


def dashboard_linked_scenarios(dashboard: dict[str, Any]) -> set[str]:
    return set(str(item) for item in check_evidence(dashboard, "runbook_links").get("linked_scenarios", []))


def openslo_scenarios(openslo: dict[str, Any]) -> set[str]:
    observed = check_evidence(openslo, "scenario_coverage").get("observed", [])
    return set(str(item) for item in observed)


def openslo_links(openslo: dict[str, Any]) -> set[str]:
    links = check_evidence(openslo, "operational_links").get("links", {})
    if isinstance(links, dict):
        return set(str(key) for key in links)
    return set()


def runbook_scenarios(runbooks: dict[str, Any]) -> set[str]:
    return {
        str(item.get("scenario"))
        for item in runbooks.get("runbooks", [])
        if item.get("scenario")
    }


def scenario_surface_map(
    *,
    alerting: dict[str, Any],
    dashboard: dict[str, Any],
    openslo: dict[str, Any],
    runbooks: dict[str, Any],
) -> dict[str, list[str]]:
    return {
        "alerting": sorted(alert_scenarios(alerting)),
        "dashboard": sorted(dashboard_scenarios(dashboard)),
        "openslo": sorted(openslo_scenarios(openslo)),
        "runbooks": sorted(runbook_scenarios(runbooks)),
    }


def missing_by_surface(surface_map: dict[str, list[str]], required: set[str]) -> dict[str, list[str]]:
    return {
        surface: sorted(required - set(scenarios))
        for surface, scenarios in surface_map.items()
        if required - set(scenarios)
    }


def alert_metadata_violations(alerting: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    required_annotations = set(policy.get("required_alert_annotations", []))
    expected_severity = dict(policy.get("required_severity_by_scenario", {}))
    violations: list[dict[str, Any]] = []
    for item in alerting.get("alerts", []):
        labels = item.get("labels", {})
        annotations = item.get("annotations", {})
        scenario = str(labels.get("scenario", ""))
        alert_name = str(item.get("alert", "unnamed"))
        severity = str(labels.get("severity", ""))
        expected = expected_severity.get(scenario)
        if expected and severity != expected:
            violations.append(
                {
                    "alert": alert_name,
                    "scenario": scenario,
                    "field": "severity",
                    "expected": expected,
                    "observed": severity,
                }
            )
        missing_annotations = sorted(required_annotations - set(annotations))
        if missing_annotations:
            violations.append(
                {
                    "alert": alert_name,
                    "scenario": scenario,
                    "field": "annotations",
                    "missing": missing_annotations,
                }
            )
        runbook_url = str(annotations.get("runbook_url", ""))
        if scenario and f"#{scenario}" not in runbook_url:
            violations.append(
                {
                    "alert": alert_name,
                    "scenario": scenario,
                    "field": "runbook_url",
                    "observed": runbook_url,
                }
            )
        if not str(annotations.get("dashboard_hint", "")):
            violations.append(
                {
                    "alert": alert_name,
                    "scenario": scenario,
                    "field": "dashboard_hint",
                    "observed": "",
                }
            )
    return violations


def runbook_violations(runbooks: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    required_fields = set(policy.get("required_runbook_fields", []))
    violations: list[dict[str, Any]] = []
    for item in runbooks.get("runbooks", []):
        scenario = str(item.get("scenario", "unknown"))
        missing = sorted(
            field
            for field in required_fields
            if not item.get(field)
        )
        if missing:
            violations.append({"scenario": scenario, "missing": missing})
    return violations


def evaluate_contract(
    *,
    alerting: dict[str, Any],
    dashboard: dict[str, Any],
    openslo: dict[str, Any],
    runbooks: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    required = set(str(item) for item in policy.get("required_scenarios", []))
    surface_map = scenario_surface_map(
        alerting=alerting,
        dashboard=dashboard,
        openslo=openslo,
        runbooks=runbooks,
    )
    missing = missing_by_surface(surface_map, required)
    linked_dashboard = dashboard_linked_scenarios(dashboard)
    alert_violations = alert_metadata_violations(alerting, policy)
    runbook_gaps = runbook_violations(runbooks, policy)
    openslo_link_set = openslo_links(openslo)
    checks = [
        check(
            "scenario_contract",
            not missing,
            {
                "required": sorted(required),
                "surfaces": surface_map,
                "missing_by_surface": missing,
            },
        ),
        check(
            "alert_metadata_contract",
            alerting.get("status") == PASS
            and int(alerting.get("rule_count", 0)) >= int(policy.get("minimum_alert_rules", 0))
            and not alert_violations,
            {
                "rule_count": alerting.get("rule_count"),
                "required_rule_count": policy.get("minimum_alert_rules"),
                "violations": alert_violations,
            },
        ),
        check(
            "dashboard_contract",
            dashboard.get("status") == PASS
            and int(dashboard.get("panel_count", 0)) >= int(policy.get("minimum_dashboard_panels", 0))
            and linked_dashboard >= required,
            {
                "panel_count": dashboard.get("panel_count"),
                "required_panel_count": policy.get("minimum_dashboard_panels"),
                "linked_scenarios": sorted(linked_dashboard),
            },
        ),
        check(
            "openslo_contract",
            openslo.get("status") == PASS
            and float(openslo.get("objective_target", 0)) >= float(policy.get("minimum_openslo_objective_target", 0))
            and openslo_link_set >= set(policy.get("required_openslo_links", [])),
            {
                "objective_target": openslo.get("objective_target"),
                "minimum_target": policy.get("minimum_openslo_objective_target"),
                "links": sorted(openslo_link_set),
            },
        ),
        check(
            "runbook_contract",
            runbooks.get("runbooks") is not None
            and runbook_scenarios(runbooks) >= required
            and not runbook_gaps,
            {"violations": runbook_gaps},
        ),
    ]
    return {
        "status": PASS if all(item["ok"] for item in checks) else FAIL,
        "checks": checks,
        "failed_count": sum(1 for item in checks if not item["ok"]),
        "scenario_surfaces": surface_map,
    }


def remove_from_check_list(report: dict[str, Any], check_name: str, evidence_key: str, scenario: str) -> None:
    for item in report.get("checks", []):
        if item.get("name") != check_name:
            continue
        evidence = item.setdefault("evidence", {})
        values = evidence.get(evidence_key, [])
        if isinstance(values, list):
            evidence[evidence_key] = [value for value in values if value != scenario]


def mutate_fixture(
    *,
    alerting: dict[str, Any],
    dashboard: dict[str, Any],
    openslo: dict[str, Any],
    runbooks: dict[str, Any],
    fixture: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    scenario = str(fixture.get("scenario", ""))
    mutated = {
        "alerting": copy.deepcopy(alerting),
        "dashboard": copy.deepcopy(dashboard),
        "openslo": copy.deepcopy(openslo),
        "runbooks": copy.deepcopy(runbooks),
    }
    mutation = fixture["mutation"]
    if mutation == "remove_alert_scenario":
        mutated["alerting"]["alerts"] = [
            item
            for item in mutated["alerting"].get("alerts", [])
            if item.get("labels", {}).get("scenario") != scenario
        ]
        mutated["alerting"]["rule_count"] = len(mutated["alerting"].get("alerts", []))
    elif mutation == "remove_dashboard_scenario":
        mutated["dashboard"]["scenarios"] = [
            item
            for item in mutated["dashboard"].get("scenarios", [])
            if item != scenario
        ]
        remove_from_check_list(mutated["dashboard"], "scenario_coverage", "observed", scenario)
        remove_from_check_list(mutated["dashboard"], "runbook_links", "linked_scenarios", scenario)
    elif mutation == "remove_openslo_scenario":
        remove_from_check_list(mutated["openslo"], "scenario_coverage", "observed", scenario)
        mutated["openslo"]["scenario_count"] = max(0, int(mutated["openslo"].get("scenario_count", 0)) - 1)
    elif mutation == "remove_runbook_scenario":
        mutated["runbooks"]["runbooks"] = [
            item
            for item in mutated["runbooks"].get("runbooks", [])
            if item.get("scenario") != scenario
        ]
    elif mutation == "set_alert_severity":
        for item in mutated["alerting"].get("alerts", []):
            if item.get("labels", {}).get("scenario") == scenario:
                item.setdefault("labels", {})["severity"] = str(fixture["severity"])
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    *,
    alerting: dict[str, Any],
    dashboard: dict[str, Any],
    openslo: dict[str, Any],
    runbooks: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("drift_fixtures", []):
        mutated = mutate_fixture(
            alerting=alerting,
            dashboard=dashboard,
            openslo=openslo,
            runbooks=runbooks,
            fixture=fixture,
        )
        report = evaluate_contract(
            alerting=mutated["alerting"],
            dashboard=mutated["dashboard"],
            openslo=mutated["openslo"],
            runbooks=mutated["runbooks"],
            policy=policy,
        )
        expected_failed_check = fixture["expected_failed_check"]
        failed_checks = [item["name"] for item in report["checks"] if not item["ok"]]
        results.append(
            {
                "name": fixture["name"],
                "mutation": fixture["mutation"],
                "scenario": fixture.get("scenario"),
                "expected_failed_check": expected_failed_check,
                "failed_checks": failed_checks,
                "detected": expected_failed_check in failed_checks,
            }
        )
    return results


def build_report(
    *,
    alerting: dict[str, Any],
    dashboard: dict[str, Any],
    openslo: dict[str, Any],
    runbooks: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    contract = evaluate_contract(
        alerting=alerting,
        dashboard=dashboard,
        openslo=openslo,
        runbooks=runbooks,
        policy=policy,
    )
    fixture_results = evaluate_fixtures(
        alerting=alerting,
        dashboard=dashboard,
        openslo=openslo,
        runbooks=runbooks,
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
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "required_scenario_count": len(policy.get("required_scenarios", [])),
        "surface_count": len(contract["scenario_surfaces"]),
        "fixture_count": len(fixture_results),
        "detected_fixture_count": sum(1 for item in fixture_results if item["detected"]),
        "failed_count": failed_count,
        "scenario_surfaces": contract["scenario_surfaces"],
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "observability-drift-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    status = str(report["status"]).upper()
    lines = [
        "# Observability Drift Audit",
        "",
        f"Overall status: **{status}**",
        "",
        "This audit compares the generated SLO alerting evidence, Grafana",
        "dashboard evidence, OpenSLO evidence, and incident runbooks. The goal is",
        "to catch semantic drift where each artifact passes by itself but no",
        "longer describes the same operating contract.",
        "",
        "## Scenario Surfaces",
        "",
        "| Surface | Scenarios |",
        "| --- | --- |",
    ]
    for surface, scenarios in report["scenario_surfaces"].items():
        lines.append(f"| `{surface}` | {', '.join(f'`{item}`' for item in scenarios)} |")
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Drift Fixtures", "", "| Fixture | Scenario | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item.get('scenario', '')}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "observability-drift-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/observability-drift-policy.json")
    parser.add_argument("--alerting", default="docs/evidence/alerting-rules.json")
    parser.add_argument("--dashboard", default="docs/evidence/grafana-dashboard.json")
    parser.add_argument("--openslo", default="docs/evidence/openslo-contract.json")
    parser.add_argument("--runbooks", default="docs/evidence/incident-runbooks.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(
        alerting=load_json(Path(args.alerting)),
        dashboard=load_json(Path(args.dashboard)),
        openslo=load_json(Path(args.openslo)),
        runbooks=load_json(Path(args.runbooks)),
        policy=load_json(Path(args.policy)),
    )
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'observability-drift-audit.json'}")
    print(f"wrote {output_dir / 'observability-drift-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
