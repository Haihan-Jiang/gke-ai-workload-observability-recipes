#!/usr/bin/env python3
"""Audit that public project claims are backed by committed evidence."""

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


def load_surfaces(repo_root: Path, policy: dict[str, Any]) -> dict[str, str]:
    paths = {
        str(item.get("surface"))
        for item in policy.get("claims", [])
        if item.get("surface")
    }
    paths.update(
        str(item.get("surface"))
        for item in policy.get("boundary_statements", [])
        if item.get("surface")
    )
    paths.update(
        str(item.get("surface"))
        for item in policy.get("forbidden_phrases", [])
        if item.get("surface")
    )
    return {
        path: (repo_root / path).read_text(encoding="utf-8")
        for path in sorted(paths)
    }


def load_evidence(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for claim in policy.get("claims", []):
        path = str(claim.get("evidence_json", ""))
        if path and path not in evidence:
            absolute = repo_root / path
            evidence[path] = load_json(absolute) if absolute.is_file() else None
    return evidence


def release_checks(source_text: str) -> set[str]:
    checks: set[str] = set()
    for line in source_text.splitlines():
        stripped = line.strip()
        if stripped.startswith('"name": '):
            parts = stripped.split('"')
            if len(parts) >= 4:
                checks.add(parts[3])
    return checks


def claim_by_id(policy: dict[str, Any], claim_id: str) -> dict[str, Any]:
    for claim in policy.get("claims", []):
        if claim.get("id") == claim_id:
            return claim
    raise KeyError(f"unknown claim id: {claim_id}")


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def evaluate_inputs(
    repo_root: Path,
    policy: dict[str, Any],
    *,
    surfaces: dict[str, str],
    evidence: dict[str, Any],
    release_source: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    claims = list(policy.get("claims", []))
    release_check_names = release_checks(release_source)
    missing_claims = []
    missing_evidence = []
    bad_status = []
    metric_gaps = []
    release_gaps = []
    doc_gaps = []

    for claim in claims:
        claim_id = str(claim["id"])
        surface = str(claim["surface"])
        required_text = str(claim["required_text"])
        if required_text not in surfaces.get(surface, ""):
            missing_claims.append({"claim": claim_id, "surface": surface, "text": required_text})

        evidence_json = str(claim.get("evidence_json", ""))
        evidence_doc = str(claim.get("evidence_doc", ""))
        data = evidence.get(evidence_json)
        if evidence_doc and not (repo_root / evidence_doc).is_file():
            doc_gaps.append({"claim": claim_id, "path": evidence_doc})
        if not isinstance(data, dict):
            missing_evidence.append({"claim": claim_id, "path": evidence_json})
            continue
        if data.get("status") != PASS:
            bad_status.append({"claim": claim_id, "path": evidence_json, "status": data.get("status")})

        for field, minimum in claim.get("minimum_metrics", {}).items():
            observed = number(data.get(field))
            if observed is None or observed < float(minimum):
                metric_gaps.append(
                    {
                        "claim": claim_id,
                        "field": field,
                        "contract": "minimum",
                        "limit": minimum,
                        "observed": data.get(field),
                    }
                )
        for field, maximum in claim.get("maximum_metrics", {}).items():
            observed = number(data.get(field))
            if observed is None or observed > float(maximum):
                metric_gaps.append(
                    {
                        "claim": claim_id,
                        "field": field,
                        "contract": "maximum",
                        "limit": maximum,
                        "observed": data.get(field),
                    }
                )

        release_check = str(claim.get("release_check", ""))
        if release_check and release_check not in release_check_names:
            release_gaps.append({"claim": claim_id, "release_check": release_check})

    missing_boundaries = [
        {"surface": item["surface"], "text": item["text"]}
        for item in policy.get("boundary_statements", [])
        if str(item["text"]) not in surfaces.get(str(item["surface"]), "")
    ]
    forbidden_present = [
        {"surface": item["surface"], "text": item["text"]}
        for item in policy.get("forbidden_phrases", [])
        if str(item["text"]) in surfaces.get(str(item["surface"]), "")
    ]

    evidence_claim_count = sum(1 for claim in claims if claim.get("evidence_json"))
    release_check_count = sum(1 for claim in claims if claim.get("release_check"))
    checks = [
        check(
            "claim_text_contract",
            not missing_claims and len(claims) >= int(policy.get("minimum_claim_count", 0)),
            {
                "claim_count": len(claims),
                "minimum_claim_count": policy.get("minimum_claim_count"),
                "missing_claims": missing_claims,
            },
        ),
        check(
            "evidence_status_contract",
            not missing_evidence
            and not bad_status
            and not doc_gaps
            and evidence_claim_count >= int(policy.get("minimum_evidence_claim_count", 0)),
            {
                "evidence_claim_count": evidence_claim_count,
                "missing_evidence": missing_evidence,
                "bad_status": bad_status,
                "missing_docs": doc_gaps,
            },
        ),
        check("evidence_metric_contract", not metric_gaps, {"metric_gaps": metric_gaps}),
        check(
            "release_check_contract",
            not release_gaps
            and release_check_count >= int(policy.get("minimum_release_check_count", 0)),
            {
                "release_check_count": release_check_count,
                "release_gaps": release_gaps,
            },
        ),
        check(
            "boundary_language_contract",
            not missing_boundaries
            and not forbidden_present
            and len(policy.get("boundary_statements", [])) >= int(policy.get("minimum_boundary_statement_count", 0)),
            {
                "boundary_statement_count": len(policy.get("boundary_statements", [])),
                "missing_boundaries": missing_boundaries,
                "forbidden_present": forbidden_present,
            },
        ),
    ]
    metrics = {
        "claim_count": len(claims),
        "evidence_claim_count": evidence_claim_count,
        "release_check_count": release_check_count,
        "boundary_statement_count": len(policy.get("boundary_statements", [])),
        "forbidden_phrase_count": len(forbidden_present),
        "missing_claim_count": len(missing_claims),
        "missing_evidence_count": len(missing_evidence),
        "missing_doc_count": len(doc_gaps),
        "metric_gap_count": len(metric_gaps),
        "release_gap_count": len(release_gaps),
        "surface_count": len(surfaces),
    }
    return checks, metrics


def apply_fixture(
    repo_root: Path,
    policy: dict[str, Any],
    surfaces: dict[str, str],
    evidence: dict[str, Any],
    release_source: str,
    fixture: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any], str]:
    mutated_surfaces = copy.deepcopy(surfaces)
    mutated_evidence = copy.deepcopy(evidence)
    mutated_release_source = release_source
    mutation = fixture.get("mutation")

    if mutation == "remove_claim_text":
        claim = claim_by_id(policy, str(fixture.get("claim", "")))
        surface = str(claim["surface"])
        mutated_surfaces[surface] = mutated_surfaces[surface].replace(str(claim["required_text"]), "")
        return mutated_surfaces, mutated_evidence, mutated_release_source
    if mutation == "set_evidence_status":
        claim = claim_by_id(policy, str(fixture.get("claim", "")))
        path = str(claim["evidence_json"])
        mutated_evidence[path]["status"] = fixture.get("status")
        return mutated_surfaces, mutated_evidence, mutated_release_source
    if mutation == "set_evidence_metric":
        claim = claim_by_id(policy, str(fixture.get("claim", "")))
        path = str(claim["evidence_json"])
        mutated_evidence[path][str(fixture.get("field"))] = fixture.get("value")
        return mutated_surfaces, mutated_evidence, mutated_release_source
    if mutation == "remove_release_check":
        claim = claim_by_id(policy, str(fixture.get("claim", "")))
        release_check = str(claim["release_check"])
        mutated_release_source = mutated_release_source.replace(f'"name": "{release_check}"', '"name": "missing_release_check"')
        return mutated_surfaces, mutated_evidence, mutated_release_source
    if mutation == "remove_boundary_statement":
        statement = policy["boundary_statements"][int(fixture.get("index", 0))]
        surface = str(statement["surface"])
        mutated_surfaces[surface] = mutated_surfaces[surface].replace(str(statement["text"]), "")
        return mutated_surfaces, mutated_evidence, mutated_release_source
    if mutation == "append_forbidden_phrase":
        phrase = policy["forbidden_phrases"][int(fixture.get("index", 0))]
        surface = str(phrase["surface"])
        mutated_surfaces[surface] = mutated_surfaces[surface] + "\n" + str(phrase["text"])
        return mutated_surfaces, mutated_evidence, mutated_release_source
    raise ValueError(f"unsupported fixture mutation: {mutation}")


def evaluate_fixtures(
    repo_root: Path,
    policy: dict[str, Any],
    surfaces: dict[str, str],
    evidence: dict[str, Any],
    release_source: str,
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_surfaces, mutated_evidence, mutated_release_source = apply_fixture(
            repo_root,
            policy,
            surfaces,
            evidence,
            release_source,
            fixture,
        )
        checks, _ = evaluate_inputs(
            repo_root,
            policy,
            surfaces=mutated_surfaces,
            evidence=mutated_evidence,
            release_source=mutated_release_source,
        )
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
    release_readiness_source: Path,
) -> dict[str, Any]:
    surfaces = load_surfaces(repo_root, policy)
    evidence = load_evidence(repo_root, policy)
    release_source = (repo_root / release_readiness_source).read_text(encoding="utf-8")
    checks, metrics = evaluate_inputs(
        repo_root,
        policy,
        surfaces=surfaces,
        evidence=evidence,
        release_source=release_source,
    )
    fixtures = evaluate_fixtures(repo_root, policy, surfaces, evidence, release_source)
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
        "check_count": len(checks),
        "failed_count": failed_count,
        "detected_fixture_count": detected_fixture_count,
        **metrics,
        "checks": checks,
        "fixture_results": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "public-claim-evidence-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Public Claim Evidence Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit verifies that public README and industry-map claims are",
        "backed by committed evidence, release-readiness source checks, and",
        "explicit boundary language.",
        "",
        "## Summary",
        "",
        f"- Claims checked: `{report['claim_count']}`",
        f"- Evidence-backed claims: `{report['evidence_claim_count']}`",
        f"- Release checks referenced: `{report['release_check_count']}`",
        f"- Boundary statements: `{report['boundary_statement_count']}`",
        f"- Surfaces checked: `{report['surface_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Detected |", "| --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(f"| `{item['name']}` | {'yes' if item['detected'] else 'no'} |")
    lines.append("")
    (output_dir / "public-claim-evidence-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/public-claim-evidence-policy.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--release-readiness-source", default="demo/release_readiness.py")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    report = build_report(
        repo_root,
        load_json(repo_root / args.policy),
        release_readiness_source=Path(args.release_readiness_source),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'public-claim-evidence-audit.json'}")
    print(f"wrote {output_dir / 'public-claim-evidence-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
