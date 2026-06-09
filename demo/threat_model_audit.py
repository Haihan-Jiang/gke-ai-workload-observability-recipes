#!/usr/bin/env python3
"""Audit the evidence-backed threat model and risk register."""

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


def read_files(repo_root: Path, paths: list[str]) -> dict[str, str | None]:
    return {
        path: (repo_root / path).read_text(encoding="utf-8") if (repo_root / path).is_file() else None
        for path in paths
    }


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def missing_terms(text: str | None, terms: list[str]) -> list[str]:
    if text is None:
        return terms
    return [term for term in terms if term not in text]


def release_checks(source_text: str) -> set[str]:
    checks: set[str] = set()
    for line in source_text.splitlines():
        stripped = line.strip()
        if stripped.startswith('"name": '):
            parts = stripped.split('"')
            if len(parts) >= 4:
                checks.add(parts[3])
    return checks


def threat_model_paths(policy: dict[str, Any]) -> list[str]:
    paths = set(policy["required_files"])
    paths.add(str(policy["threat_model_surface"]))
    return sorted(paths)


def evaluate_documents(
    repo_root: Path,
    files: dict[str, str | None],
    policy: dict[str, Any],
    release_readiness_source: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_files = list(policy["required_files"])
    missing_files = [path for path in required_files if files.get(path) is None]
    surface = str(policy["threat_model_surface"])
    text = files.get(surface)
    release_check_names = release_checks(release_readiness_source)

    missing_sections = missing_terms(text, list(policy.get("required_sections", [])))
    missing_assets = missing_terms(text, list(policy.get("required_assets", [])))
    missing_boundaries = missing_terms(text, list(policy.get("required_trust_boundaries", [])))
    asset_count = len(policy.get("required_assets", [])) - len(missing_assets)
    trust_boundary_count = len(policy.get("required_trust_boundaries", [])) - len(missing_boundaries)

    threat_gaps = []
    mitigation_gaps = []
    residual_risk_gaps = []
    owner_gaps = []
    evidence_gaps = []
    release_control_gaps = []
    threat_count = 0
    mitigation_count = 0
    residual_risk_count = 0
    owner_count = 0
    evidence_link_count = 0
    existing_evidence_link_count = 0
    release_control_count = 0

    for threat in policy.get("threats", []):
        threat_id = str(threat["id"])
        title = str(threat["title"])
        heading = f"{threat_id}: {title}"
        missing_threat_terms = missing_terms(text, [heading])
        if missing_threat_terms:
            threat_gaps.append({"threat": threat_id, "missing_terms": missing_threat_terms})
        else:
            threat_count += 1

        missing_mitigations = missing_terms(text, list(threat.get("required_terms", [])))
        if missing_mitigations:
            mitigation_gaps.append({"threat": threat_id, "missing_terms": missing_mitigations})
        mitigation_count += len(threat.get("required_terms", [])) - len(missing_mitigations)

        owner = str(threat.get("owner", ""))
        if owner and text is not None and owner in text:
            owner_count += 1
        else:
            owner_gaps.append({"threat": threat_id, "owner": owner})

        residual_risk = str(threat.get("residual_risk", ""))
        if residual_risk and text is not None and residual_risk in text:
            residual_risk_count += 1
        else:
            residual_risk_gaps.append({"threat": threat_id, "residual_risk": residual_risk})

        for evidence_path in threat.get("evidence_links", []):
            evidence_link_count += 1
            missing = []
            if text is None or evidence_path not in text:
                missing.append("not referenced")
            if not (repo_root / evidence_path).is_file():
                missing.append("missing target")
            else:
                existing_evidence_link_count += 1
            if missing:
                evidence_gaps.append({"threat": threat_id, "path": evidence_path, "missing": missing})

        for release_control in threat.get("release_controls", []):
            release_control_count += 1
            missing = []
            if text is None or release_control not in text:
                missing.append("not referenced")
            if release_control not in release_check_names:
                missing.append("missing release-readiness check")
            if missing:
                release_control_gaps.append({"threat": threat_id, "control": release_control, "missing": missing})

    checks = [
        check(
            "required_files",
            not missing_files
            and len(required_files) >= int(policy.get("minimum_required_file_count", 0)),
            {"missing_files": missing_files, "required_files": required_files},
        ),
        check(
            "scope_boundary_contract",
            not missing_sections
            and not missing_assets
            and not missing_boundaries
            and asset_count >= int(policy.get("minimum_asset_count", 0))
            and trust_boundary_count >= int(policy.get("minimum_trust_boundary_count", 0)),
            {
                "missing_sections": missing_sections,
                "asset_count": asset_count,
                "missing_assets": missing_assets,
                "trust_boundary_count": trust_boundary_count,
                "missing_trust_boundaries": missing_boundaries,
            },
        ),
        check(
            "threat_register_contract",
            not threat_gaps and threat_count >= int(policy.get("minimum_threat_count", 0)),
            {"threat_count": threat_count, "threat_gaps": threat_gaps},
        ),
        check(
            "mitigation_contract",
            not mitigation_gaps and mitigation_count >= int(policy.get("minimum_mitigation_count", 0)),
            {"mitigation_count": mitigation_count, "mitigation_gaps": mitigation_gaps},
        ),
        check(
            "residual_risk_contract",
            not residual_risk_gaps
            and not owner_gaps
            and residual_risk_count >= int(policy.get("minimum_residual_risk_count", 0))
            and owner_count >= int(policy.get("minimum_owner_count", 0)),
            {
                "residual_risk_count": residual_risk_count,
                "owner_count": owner_count,
                "residual_risk_gaps": residual_risk_gaps,
                "owner_gaps": owner_gaps,
            },
        ),
        check(
            "evidence_linkage",
            not evidence_gaps
            and evidence_link_count >= int(policy.get("minimum_evidence_link_count", 0)),
            {
                "evidence_link_count": evidence_link_count,
                "existing_evidence_link_count": existing_evidence_link_count,
                "evidence_gaps": evidence_gaps,
            },
        ),
        check(
            "release_control_linkage",
            not release_control_gaps
            and release_control_count >= int(policy.get("minimum_release_control_count", 0)),
            {
                "release_control_count": release_control_count,
                "release_control_gaps": release_control_gaps,
            },
        ),
    ]
    metrics = {
        "required_file_count": len(required_files),
        "present_file_count": len(required_files) - len(missing_files),
        "asset_count": asset_count,
        "trust_boundary_count": trust_boundary_count,
        "threat_count": threat_count,
        "mitigation_count": mitigation_count,
        "owner_count": owner_count,
        "residual_risk_count": residual_risk_count,
        "evidence_link_count": evidence_link_count,
        "existing_evidence_link_count": existing_evidence_link_count,
        "release_control_count": release_control_count,
    }
    return checks, metrics


def apply_fixture(files: dict[str, str | None], fixture: dict[str, Any]) -> dict[str, str | None]:
    mutated = copy.deepcopy(files)
    path = str(fixture.get("path", ""))
    mutation = fixture.get("mutation")
    if mutation == "remove_file":
        mutated[path] = None
    elif mutation == "remove_text":
        text = mutated.get(path)
        if text is not None:
            mutated[path] = text.replace(str(fixture.get("text", "")), "")
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    repo_root: Path,
    files: dict[str, str | None],
    policy: dict[str, Any],
    release_readiness_source: str,
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(files, fixture)
        checks, _ = evaluate_documents(repo_root, mutated, policy, release_readiness_source)
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


def build_report(
    repo_root: Path,
    policy: dict[str, Any],
    *,
    release_readiness_source: Path = Path("demo/release_readiness.py"),
) -> dict[str, Any]:
    files = read_files(repo_root, threat_model_paths(policy))
    release_source_path = release_readiness_source
    if not release_source_path.is_absolute():
        release_source_path = repo_root / release_source_path
    release_source = release_source_path.read_text(encoding="utf-8")
    checks, metrics = evaluate_documents(repo_root, files, policy, release_source)
    fixtures = evaluate_fixtures(repo_root, files, policy, release_source)
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
        "fixtures": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "threat-model-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Threat Model Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that the lab threat model has explicit assets,",
        "trust boundaries, abuse cases, owners, residual risk statements,",
        "committed evidence links, and release-readiness control bindings.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Required files | {report['required_file_count']} |",
        f"| Present files | {report['present_file_count']} |",
        f"| Assets | {report['asset_count']} |",
        f"| Trust boundaries | {report['trust_boundary_count']} |",
        f"| Threats | {report['threat_count']} |",
        f"| Mitigations | {report['mitigation_count']} |",
        f"| Owners | {report['owner_count']} |",
        f"| Residual risk statements | {report['residual_risk_count']} |",
        f"| Evidence links | {report['evidence_link_count']} |",
        f"| Existing evidence links | {report['existing_evidence_link_count']} |",
        f"| Release controls | {report['release_control_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Expected Failed Check | Detected |", "| --- | --- | --- |"])
    for item in report["fixtures"]:
        lines.append(
            f"| `{item['name']}` | `{item['expected_failed_check']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    (output_dir / "threat-model-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/threat-model-policy.json")
    parser.add_argument("--release-readiness-source", default="demo/release_readiness.py")
    parser.add_argument("--output-dir", default="out/threat-model-audit")
    args = parser.parse_args()

    report = build_report(
        Path(args.repo_root),
        load_json(Path(args.policy)),
        release_readiness_source=Path(args.release_readiness_source),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'threat-model-audit.json'}")
    print(f"wrote {output_dir / 'threat-model-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
