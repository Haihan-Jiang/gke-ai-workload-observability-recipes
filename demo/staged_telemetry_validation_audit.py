#!/usr/bin/env python3
"""Audit staged rollout telemetry validation before promotion."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
INPUT_KEYS = [
    "rollout_guard",
    "trace_quality",
    "telemetry_redaction",
    "telemetry_cost",
    "telemetry_exporter_authority",
    "synthetic_probe",
    "model_release_safety",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": PASS if ok else FAIL, "reason": reason, "evidence": evidence}


def by_name(items: list[dict[str, Any]], field: str = "name") -> dict[str, dict[str, Any]]:
    return {str(item[field]): item for item in items if item.get(field)}


def scenario_values_from_trace(trace_quality: dict[str, Any]) -> set[str]:
    values = trace_quality.get("cardinality", {}).get("incident.scenario", {}).get("values", [])
    return {str(item) for item in values}


def redaction_scenarios(telemetry_redaction: dict[str, Any]) -> set[str]:
    for item in telemetry_redaction.get("checks", []):
        if item.get("name") == "payload_coverage":
            return {str(value) for value in item.get("evidence", {}).get("observed_scenarios", [])}
    return set()


def cost_scenarios(telemetry_cost: dict[str, Any]) -> set[str]:
    return {str(item.get("scenario")) for item in telemetry_cost.get("scenarios", []) if item.get("scenario")}


def probe_scenarios(synthetic_probe: dict[str, Any]) -> set[str]:
    return {str(item.get("scenario")) for item in synthetic_probe.get("probes", []) if item.get("scenario")}


def required_artifact_status(inputs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    artifacts = []
    for key in INPUT_KEYS:
        value = inputs[key]
        if key == "rollout_guard":
            ok = value.get("decision") == "rollback"
            artifacts.append({"artifact": key, "status": value.get("decision"), "ok": ok})
        else:
            ok = value.get("status") == PASS and int(value.get("failed_count", 0)) == 0
            artifacts.append(
                {
                    "artifact": key,
                    "status": value.get("status"),
                    "failed_count": value.get("failed_count", 0),
                    "ok": ok,
                }
            )
    return artifacts


def evaluate_inputs(inputs: dict[str, dict[str, Any]], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rollout_guard = inputs["rollout_guard"]
    trace_quality = inputs["trace_quality"]
    telemetry_redaction = inputs["telemetry_redaction"]
    telemetry_cost = inputs["telemetry_cost"]
    telemetry_exporter = inputs["telemetry_exporter_authority"]
    synthetic_probe = inputs["synthetic_probe"]
    model_release = inputs["model_release_safety"]

    artifact_statuses = required_artifact_status(inputs)
    rollout_expected = {
        "candidate": policy["rollout_candidate"],
        "candidate_version": policy["rollout_candidate_version"],
        "decision": policy["rollout_decision"],
    }
    rollout_ok = (
        rollout_guard.get("candidate") == rollout_expected["candidate"]
        and rollout_guard.get("candidate_version") == rollout_expected["candidate_version"]
        and rollout_guard.get("decision") == rollout_expected["decision"]
        and len(rollout_guard.get("violations", [])) >= 2
    )

    trace_attrs = trace_quality.get("cardinality", {})
    trace_attr_gaps = [
        attr
        for attr in policy.get("required_trace_attributes", [])
        if attr not in trace_attrs or not trace_attrs.get(attr, {}).get("ok")
    ]
    telemetry_ok = (
        trace_quality.get("status") == PASS
        and not trace_attr_gaps
        and telemetry_redaction.get("status") == PASS
        and int(telemetry_redaction.get("redaction_violation_count", -1)) == 0
        and int(telemetry_redaction.get("scenario_count", 0)) >= int(policy.get("minimum_scenario_count", 0))
        and telemetry_cost.get("status") == PASS
        and int(telemetry_cost.get("scenario_count", 0)) >= int(policy.get("minimum_scenario_count", 0))
        and telemetry_exporter.get("status") == PASS
        and int(telemetry_exporter.get("authoritative_pipeline_count", 0))
        >= int(policy.get("minimum_authoritative_pipeline_count", 0))
        and int(telemetry_exporter.get("queued_exporter_count", 0)) >= 1
        and int(telemetry_exporter.get("retry_enabled_count", 0)) >= 1
    )

    probes = by_name(synthetic_probe.get("probes", []))
    probe_types = {str(item.get("probe_type")) for item in synthetic_probe.get("probes", []) if item.get("probe_type")}
    canary_probe = probes.get(str(policy["canary_probe"]), {})
    telemetry_probe = probes.get(str(policy["telemetry_probe"]), {})
    probe_gaps = [
        probe_type
        for probe_type in policy.get("required_probe_types", [])
        if probe_type not in probe_types
    ]
    preflight_ok = (
        synthetic_probe.get("status") == PASS
        and not probe_gaps
        and int(synthetic_probe.get("preflight_block_count", 0)) >= int(policy.get("minimum_preflight_block_count", 0))
        and canary_probe.get("scenario") == policy["rollout_candidate"]
        and canary_probe.get("release_action") == policy["blocked_release_action"]
        and canary_probe.get("expected", {}).get("requires_rollback") is True
        and telemetry_probe.get("release_action") == policy["review_release_action"]
    )

    candidate_releases = [item for item in model_release.get("releases", []) if item.get("role") == "candidate"]
    blocked_candidates = [
        item
        for item in candidate_releases
        if item.get("release_action") == policy["blocked_release_action"]
        and item.get("rollout_guard", {}).get("decision") == policy["rollout_decision"]
    ]
    model_block_ok = (
        model_release.get("status") == PASS
        and int(model_release.get("blocked_candidate_count", 0)) >= int(policy.get("minimum_blocked_candidate_count", 0))
        and len(blocked_candidates) >= int(policy.get("minimum_blocked_candidate_count", 0))
    )

    expected_scenarios = {str(item) for item in policy.get("expected_scenarios", [])}
    surfaces = {
        "trace_quality": scenario_values_from_trace(trace_quality),
        "telemetry_redaction": redaction_scenarios(telemetry_redaction),
        "telemetry_cost": cost_scenarios(telemetry_cost),
        "synthetic_probe": probe_scenarios(synthetic_probe),
    }
    missing_by_surface = {
        surface: sorted(expected_scenarios - values)
        for surface, values in surfaces.items()
    }
    scenario_surface_ok = all(not missing for missing in missing_by_surface.values())

    checks = [
        check(
            "evidence_status_contract",
            all(item["ok"] for item in artifact_statuses),
            "All staged rollout telemetry inputs are successful before promotion evidence is trusted.",
            {"artifact_statuses": artifact_statuses},
        ),
        check(
            "staged_rollout_guard",
            rollout_ok,
            "The staged rollout candidate is evaluated as a rollback/block before expansion.",
            {"observed": rollout_guard, "expected": rollout_expected},
        ),
        check(
            "pre_promotion_telemetry_contract",
            telemetry_ok,
            "Trace quality, redaction, cost, exporter authority, queue, and retry evidence pass before promotion.",
            {
                "trace_attribute_gaps": trace_attr_gaps,
                "redaction_violation_count": telemetry_redaction.get("redaction_violation_count"),
                "telemetry_cost_scenario_count": telemetry_cost.get("scenario_count"),
                "authoritative_pipeline_count": telemetry_exporter.get("authoritative_pipeline_count"),
                "queued_exporter_count": telemetry_exporter.get("queued_exporter_count"),
                "retry_enabled_count": telemetry_exporter.get("retry_enabled_count"),
            },
        ),
        check(
            "synthetic_preflight_contract",
            preflight_ok,
            "Synthetic probes include readiness, canary, and telemetry-delivery preflight gates with blocking release actions.",
            {
                "probe_types": sorted(probe_types),
                "probe_type_gaps": probe_gaps,
                "preflight_block_count": synthetic_probe.get("preflight_block_count"),
                "canary_probe": canary_probe,
                "telemetry_probe": telemetry_probe,
            },
        ),
        check(
            "model_promotion_block",
            model_block_ok,
            "Unsafe model rollout candidates are blocked by staged telemetry and rollback evidence.",
            {"blocked_candidate_count": model_release.get("blocked_candidate_count"), "blocked_candidates": blocked_candidates},
        ),
        check(
            "scenario_surface_contract",
            scenario_surface_ok,
            "Baseline, dependency, rollout, and telemetry-delivery scenarios appear across telemetry evidence surfaces.",
            {"expected_scenarios": sorted(expected_scenarios), "missing_by_surface": missing_by_surface},
        ),
    ]
    metrics = {
        "artifact_count": len(INPUT_KEYS),
        "scenario_count": len(expected_scenarios),
        "validated_surface_count": len(surfaces),
        "authoritative_pipeline_count": int(telemetry_exporter.get("authoritative_pipeline_count", 0)),
        "preflight_block_count": int(synthetic_probe.get("preflight_block_count", 0)),
        "blocked_candidate_count": int(model_release.get("blocked_candidate_count", 0)),
        "artifact_statuses": artifact_statuses,
        "surfaces": {name: sorted(values) for name, values in surfaces.items()},
    }
    return checks, metrics


def apply_fixture(inputs: dict[str, dict[str, Any]], fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mutated = copy.deepcopy(inputs)
    mutation = fixture.get("mutation")
    if mutation == "set_rollout_decision":
        mutated["rollout_guard"]["decision"] = fixture.get("value")
    elif mutation == "set_artifact_status":
        mutated[str(fixture["artifact"])]["status"] = fixture.get("value")
    elif mutation == "set_field":
        mutated[str(fixture["artifact"])][str(fixture["field"])] = fixture.get("value")
    elif mutation == "remove_probe":
        probe = str(fixture["probe"])
        mutated["synthetic_probe"]["probes"] = [
            item for item in mutated["synthetic_probe"].get("probes", []) if item.get("name") != probe
        ]
    elif mutation == "remove_cost_scenario":
        scenario = str(fixture["scenario"])
        mutated["telemetry_cost"]["scenarios"] = [
            item for item in mutated["telemetry_cost"].get("scenarios", []) if item.get("scenario") != scenario
        ]
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(inputs: dict[str, dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        checks, _ = evaluate_inputs(apply_fixture(inputs, fixture), policy)
        failed_checks = [item["name"] for item in checks if item["status"] != PASS]
        expected = str(fixture.get("expected_failed_check"))
        results.append(
            {
                "name": fixture.get("name"),
                "mutation": fixture.get("mutation"),
                "expected_failed_check": expected,
                "failed_checks": failed_checks,
                "detected": expected in failed_checks,
            }
        )
    return results


def build_report(inputs: dict[str, dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    checks, metrics = evaluate_inputs(inputs, policy)
    fixtures = evaluate_fixtures(inputs, policy)
    detected_fixture_count = sum(1 for item in fixtures if item["detected"])
    checks.append(
        check(
            "negative_fixture_coverage",
            detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
            "Negative fixtures prove rollout promotion, telemetry quality, probe, model-block, and scenario-surface drift are detected.",
            {
                "detected_fixture_count": detected_fixture_count,
                "minimum_detected_fixtures": policy.get("minimum_detected_fixtures"),
                "fixtures": fixtures,
            },
        )
    )
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "artifact_count": metrics["artifact_count"],
        "scenario_count": metrics["scenario_count"],
        "validated_surface_count": metrics["validated_surface_count"],
        "authoritative_pipeline_count": metrics["authoritative_pipeline_count"],
        "preflight_block_count": metrics["preflight_block_count"],
        "blocked_candidate_count": metrics["blocked_candidate_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "artifact_statuses": metrics["artifact_statuses"],
        "surfaces": metrics["surfaces"],
        "checks": checks,
        "fixture_results": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "staged-telemetry-validation-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Staged Telemetry Validation Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit verifies that telemetry is treated as pre-promotion",
        "evidence during staged rollout. It ties rollout rollback decisions,",
        "trace quality, redaction, telemetry cost, exporter authority,",
        "synthetic probes, and model release blocking into one release gate.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Input artifacts | {report['artifact_count']} |",
        f"| Scenarios | {report['scenario_count']} |",
        f"| Validated surfaces | {report['validated_surface_count']} |",
        f"| Authoritative pipelines | {report['authoritative_pipeline_count']} |",
        f"| Preflight blocks | {report['preflight_block_count']} |",
        f"| Blocked candidates | {report['blocked_candidate_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {item['status'].upper()} |")
    lines.extend(["", "## Scenario Surfaces", "", "| Surface | Scenarios |", "| --- | --- |"])
    for surface, scenarios in report["surfaces"].items():
        lines.append(f"| `{surface}` | {', '.join(f'`{item}`' for item in scenarios)} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Expected Failed Check | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item['expected_failed_check']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    (output_dir / "staged-telemetry-validation-audit.md").write_text("\n".join(lines), encoding="utf-8")


def load_inputs(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    return {
        "rollout_guard": load_json(Path(args.rollout_guard)),
        "trace_quality": load_json(Path(args.trace_quality)),
        "telemetry_redaction": load_json(Path(args.telemetry_redaction)),
        "telemetry_cost": load_json(Path(args.telemetry_cost)),
        "telemetry_exporter_authority": load_json(Path(args.telemetry_exporter_authority)),
        "synthetic_probe": load_json(Path(args.synthetic_probe)),
        "model_release_safety": load_json(Path(args.model_release_safety)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/staged-telemetry-validation-policy.json")
    parser.add_argument("--rollout-guard", default="docs/evidence/rollout-guard.json")
    parser.add_argument("--trace-quality", default="docs/evidence/trace-quality-audit.json")
    parser.add_argument("--telemetry-redaction", default="docs/evidence/telemetry-redaction-audit.json")
    parser.add_argument("--telemetry-cost", default="docs/evidence/telemetry-cost-budget.json")
    parser.add_argument("--telemetry-exporter-authority", default="docs/evidence/telemetry-exporter-authority-audit.json")
    parser.add_argument("--synthetic-probe", default="docs/evidence/synthetic-probe-audit.json")
    parser.add_argument("--model-release-safety", default="docs/evidence/model-release-safety-audit.json")
    parser.add_argument("--output-dir", default="out/staged-telemetry-validation-audit")
    args = parser.parse_args()

    report = build_report(load_inputs(args), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'staged-telemetry-validation-audit.json'}")
    print(f"wrote {output_dir / 'staged-telemetry-validation-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
