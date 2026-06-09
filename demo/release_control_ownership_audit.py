#!/usr/bin/env python3
"""Audit ownership metadata for release-readiness controls."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
CHECK_NAME_RE = re.compile(r'"name":\s*"([^"]+)"')


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def extract_release_checks(path: Path) -> set[str]:
    return set(CHECK_NAME_RE.findall(path.read_text(encoding="utf-8")))


def control_names(policy: dict[str, Any]) -> list[str]:
    return [str(item.get("name", "")) for item in policy.get("controls", [])]


def duplicate_names(names: list[str]) -> list[str]:
    return sorted({name for name in names if names.count(name) > 1})


def evaluate_controls(policy: dict[str, Any], release_checks: set[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    controls = list(policy.get("controls", []))
    owners = dict(policy.get("owners", {}))
    names = control_names(policy)
    configured = set(names)
    allowed_tier_list = [str(item) for item in policy.get("allowed_tiers", [])]
    allowed_cadence_list = [str(item) for item in policy.get("allowed_review_cadences", [])]
    allowed_tiers = set(allowed_tier_list)
    allowed_cadences = set(allowed_cadence_list)
    duplicates = duplicate_names(names)
    missing_release_checks = sorted(release_checks - configured)
    unknown_release_checks = sorted(configured - release_checks)
    metadata_gaps = []
    owner_gaps = []
    tier_gaps = []
    cadence_gaps = []
    evidence_path_gaps = []
    owner_groups = set()
    tier_counts = {tier: 0 for tier in allowed_tier_list}
    cadence_counts = {cadence: 0 for cadence in allowed_cadence_list}

    for control in controls:
        name = str(control.get("name", ""))
        owner_key = str(control.get("owner", ""))
        owner = owners.get(owner_key, {})
        tier = str(control.get("tier", ""))
        cadence = str(control.get("review_cadence", ""))
        evidence_path = str(control.get("evidence_path", ""))

        missing_fields = [
            field
            for field in ["name", "owner", "tier", "review_cadence", "evidence_path"]
            if not control.get(field)
        ]
        if missing_fields:
            metadata_gaps.append({"control": name, "missing_fields": missing_fields})

        if owner_key not in owners:
            owner_gaps.append({"control": name, "owner": owner_key, "reason": "unknown_owner"})
        else:
            missing_owner_fields = [
                field
                for field in ["owner_group", "escalation", "rollback_action"]
                if not owner.get(field)
            ]
            if missing_owner_fields:
                owner_gaps.append(
                    {
                        "control": name,
                        "owner": owner_key,
                        "reason": "owner_metadata_gap",
                        "missing_fields": missing_owner_fields,
                    }
                )
            owner_groups.add(str(owner.get("owner_group", "")))

        if tier not in allowed_tiers:
            tier_gaps.append({"control": name, "tier": tier})
        else:
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        if cadence not in allowed_cadences:
            cadence_gaps.append({"control": name, "review_cadence": cadence})
        else:
            cadence_counts[cadence] = cadence_counts.get(cadence, 0) + 1

        if not evidence_path.startswith("docs/evidence/") or not evidence_path.endswith((".json", ".md", ".svg")):
            evidence_path_gaps.append({"control": name, "evidence_path": evidence_path})

    checks = [
        check(
            "control_inventory",
            not duplicates
            and not missing_release_checks
            and not unknown_release_checks
            and len(controls) >= int(policy.get("minimum_control_count", 0)),
            {
                "control_count": len(controls),
                "release_check_count": len(release_checks),
                "minimum_control_count": policy.get("minimum_control_count"),
                "duplicate_controls": duplicates,
                "missing_release_checks": missing_release_checks,
                "unknown_release_checks": unknown_release_checks,
            },
        ),
        check("ownership_metadata", not metadata_gaps and not owner_gaps, {"metadata_gaps": metadata_gaps, "owner_gaps": owner_gaps}),
        check(
            "tier_contract",
            not tier_gaps
            and tier_counts.get("tier_0_release_blocker", 0) >= int(policy.get("minimum_tier0_count", 0)),
            {
                "tier_counts": tier_counts,
                "tier_gaps": tier_gaps,
                "minimum_tier0_count": policy.get("minimum_tier0_count"),
            },
        ),
        check(
            "review_cadence_contract",
            not cadence_gaps
            and cadence_counts.get("every_release", 0) >= int(policy.get("minimum_every_release_count", 0)),
            {
                "cadence_counts": cadence_counts,
                "cadence_gaps": cadence_gaps,
                "minimum_every_release_count": policy.get("minimum_every_release_count"),
            },
        ),
        check(
            "owner_group_coverage",
            len({group for group in owner_groups if group}) >= int(policy.get("minimum_owner_group_count", 0)),
            {
                "owner_group_count": len({group for group in owner_groups if group}),
                "minimum_owner_group_count": policy.get("minimum_owner_group_count"),
                "owner_groups": sorted(group for group in owner_groups if group),
            },
        ),
        check("evidence_path_contract", not evidence_path_gaps, {"evidence_path_gaps": evidence_path_gaps}),
    ]
    metrics = {
        "control_count": len(controls),
        "release_check_count": len(release_checks),
        "covered_release_check_count": len(configured & release_checks),
        "tier0_count": tier_counts.get("tier_0_release_blocker", 0),
        "every_release_count": cadence_counts.get("every_release", 0),
        "owner_group_count": len({group for group in owner_groups if group}),
    }
    return checks, metrics


def apply_fixture(policy: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(policy)
    controls = mutated.get("controls", [])
    mutation = fixture.get("mutation")
    control_name = str(fixture.get("control", ""))
    if mutation == "remove_control":
        mutated["controls"] = [item for item in controls if item.get("name") != control_name]
    elif mutation == "set_name":
        for control in controls:
            if control.get("name") == control_name:
                control["name"] = fixture.get("value")
    elif mutation == "remove_field":
        for control in controls:
            if control.get("name") == control_name:
                control.pop(str(fixture.get("field")), None)
    elif mutation == "set_field":
        for control in controls:
            if control.get("name") == control_name:
                control[str(fixture.get("field"))] = fixture.get("value")
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(policy: dict[str, Any], release_checks: set[str]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        checks, _ = evaluate_controls(apply_fixture(policy, fixture), release_checks)
        failed_checks = [item["name"] for item in checks if not item["ok"]]
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


def build_report(policy: dict[str, Any], release_readiness_source: Path) -> dict[str, Any]:
    release_checks = extract_release_checks(release_readiness_source)
    checks, metrics = evaluate_controls(policy, release_checks)
    fixtures = evaluate_fixtures(policy, release_checks)
    detected_fixture_count = sum(1 for item in fixtures if item["detected"])
    checks.append(
        check(
            "negative_fixture_coverage",
            detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
            {
                "detected_fixture_count": detected_fixture_count,
                "minimum_detected_fixtures": policy.get("minimum_detected_fixtures"),
                "fixtures": fixtures,
            },
        )
    )
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "failed_count": failed_count,
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        **metrics,
        "checks": checks,
        "controls": policy.get("controls", []),
        "fixtures": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "release-control-ownership-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Release Control Ownership Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit verifies that every release-readiness check has an owner,",
        "severity tier, review cadence, escalation path, rollback action, and",
        "evidence path before the final release gate passes.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Controls | {report['control_count']} |",
        f"| Release checks | {report['release_check_count']} |",
        f"| Covered release checks | {report['covered_release_check_count']} |",
        f"| Tier 0 controls | {report['tier0_count']} |",
        f"| Every-release controls | {report['every_release_count']} |",
        f"| Owner groups | {report['owner_group_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Controls", "", "| Control | Owner | Tier | Cadence | Evidence |", "| --- | --- | --- | --- | --- |"])
    for item in report["controls"]:
        lines.append(
            f"| `{item['name']}` | `{item['owner']}` | `{item['tier']}` | `{item['review_cadence']}` | `{item['evidence_path']}` |"
        )
    lines.append("")
    (output_dir / "release-control-ownership-audit.md").write_text("\n".join(lines), encoding="utf-8")


def resolve_repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/release-control-ownership-policy.json")
    parser.add_argument("--release-readiness-source", default="demo/release_readiness.py")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    policy = load_json(resolve_repo_path(repo_root, args.policy))
    report = build_report(policy, resolve_repo_path(repo_root, args.release_readiness_source))
    output_dir = resolve_repo_path(repo_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'release-control-ownership-audit.json'}")
    print(f"wrote {output_dir / 'release-control-ownership-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
