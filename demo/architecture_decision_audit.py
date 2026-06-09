#!/usr/bin/env python3
"""Audit Architecture Decision Records for evidence-backed release rationale."""

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


def decision_paths(policy: dict[str, Any]) -> list[str]:
    return [str(item["path"]) for item in policy.get("decisions", [])]


def evaluate_documents(
    files: dict[str, str | None],
    policy: dict[str, Any],
    repo_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_files = list(policy["required_files"])
    missing_files = [path for path in required_files if files.get(path) is None]
    required_sections = list(policy.get("required_sections", []))

    section_gaps = []
    rationale_gaps = []
    evidence_gaps = []
    release_control_gaps = []
    evidence_link_count = 0
    existing_evidence_link_count = 0
    release_control_count = 0
    accepted_decision_count = 0

    for decision in policy.get("decisions", []):
        path = str(decision["path"])
        text = files.get(path)
        if text and "Status: Accepted" in text:
            accepted_decision_count += 1

        missing_sections = missing_terms(text, required_sections)
        if missing_sections:
            section_gaps.append({"path": path, "missing_sections": missing_sections})

        missing_rationale = missing_terms(text, list(decision.get("required_terms", [])))
        if missing_rationale:
            rationale_gaps.append({"path": path, "missing_terms": missing_rationale})

        for evidence_path in decision.get("evidence_links", []):
            evidence_link_count += 1
            missing = []
            if text is None or evidence_path not in text:
                missing.append("not referenced")
            if not (repo_root / evidence_path).is_file():
                missing.append("missing target")
            else:
                existing_evidence_link_count += 1
            if missing:
                evidence_gaps.append({"path": path, "evidence": evidence_path, "missing": missing})

        for release_control in decision.get("release_controls", []):
            release_control_count += 1
            if text is None or release_control not in text:
                release_control_gaps.append({"path": path, "release_control": release_control})

    decision_count = len(policy.get("decisions", []))
    checks = [
        check(
            "required_files",
            not missing_files,
            {"missing_files": missing_files, "required_files": required_files},
        ),
        check(
            "adr_section_contract",
            not section_gaps
            and accepted_decision_count >= int(policy.get("minimum_decision_count", 0)),
            {
                "accepted_decision_count": accepted_decision_count,
                "minimum_decision_count": policy.get("minimum_decision_count"),
                "section_gaps": section_gaps,
            },
        ),
        check(
            "decision_rationale",
            not rationale_gaps,
            {"rationale_gaps": rationale_gaps},
        ),
        check(
            "evidence_linkage",
            not evidence_gaps
            and evidence_link_count >= int(policy.get("minimum_evidence_link_count", 0)),
            {
                "evidence_link_count": evidence_link_count,
                "existing_evidence_link_count": existing_evidence_link_count,
                "minimum_evidence_link_count": policy.get("minimum_evidence_link_count"),
                "evidence_gaps": evidence_gaps,
            },
        ),
        check(
            "release_control_linkage",
            not release_control_gaps
            and release_control_count >= int(policy.get("minimum_release_control_count", 0)),
            {
                "release_control_count": release_control_count,
                "minimum_release_control_count": policy.get("minimum_release_control_count"),
                "release_control_gaps": release_control_gaps,
            },
        ),
    ]
    metrics = {
        "required_file_count": len(required_files),
        "present_file_count": len(required_files) - len(missing_files),
        "decision_count": decision_count,
        "accepted_decision_count": accepted_decision_count,
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
    elif mutation == "replace_text":
        text = mutated.get(path)
        if text is not None:
            mutated[path] = text.replace(str(fixture.get("from", "")), str(fixture.get("to", "")))
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(
    files: dict[str, str | None],
    policy: dict[str, Any],
    repo_root: Path,
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(files, fixture)
        checks, _ = evaluate_documents(mutated, policy, repo_root)
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


def build_report(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    files = read_files(repo_root, list(policy["required_files"]))
    for path in decision_paths(policy):
        files.setdefault(path, (repo_root / path).read_text(encoding="utf-8") if (repo_root / path).is_file() else None)
    checks, metrics = evaluate_documents(files, policy, repo_root)
    fixtures = evaluate_fixtures(files, policy, repo_root)
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
    (output_dir / "architecture-decision-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Architecture Decision Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that Architecture Decision Records are accepted,",
        "include rationale and rejected alternatives, link to committed evidence,",
        "and name the release controls that enforce the decision.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Required files | {report['required_file_count']} |",
        f"| Present files | {report['present_file_count']} |",
        f"| Decisions | {report['decision_count']} |",
        f"| Accepted decisions | {report['accepted_decision_count']} |",
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
    (output_dir / "architecture-decision-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/architecture-decision-policy.json")
    parser.add_argument("--output-dir", default="out/architecture-decision-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'architecture-decision-audit.json'}")
    print(f"wrote {output_dir / 'architecture-decision-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
