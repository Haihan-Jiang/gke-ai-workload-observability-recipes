#!/usr/bin/env python3
"""Audit release-note and change-management documentation contracts."""

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


def all_text(files: dict[str, str | None]) -> str:
    return "\n".join(text for text in files.values() if text is not None)


def missing_terms(text: str | None, terms: list[str]) -> list[str]:
    if text is None:
        return terms
    return [term for term in terms if term not in text]


def evaluate_documents(files: dict[str, str | None], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_files = list(policy["required_files"])
    missing_files = [path for path in required_files if files.get(path) is None]
    release_process = files.get("docs/release-process.md")
    combined = all_text(files)
    missing_note_fields = missing_terms(
        release_process,
        list(policy.get("required_release_note_fields", [])),
    )
    missing_evidence_refs = missing_terms(
        release_process,
        list(policy.get("required_evidence_references", [])),
    )
    missing_validation_commands = missing_terms(
        combined,
        list(policy.get("required_validation_commands", [])),
    )
    missing_boundaries = [
        {"path": item["path"], "text": item["text"]}
        for item in policy.get("boundary_statements", [])
        if str(item["text"]) not in (files.get(str(item["path"])) or "")
    ]
    missing_contribution_terms = missing_terms(
        files.get("CONTRIBUTING.md"),
        list(policy.get("required_contribution_terms", [])),
    )
    checks = [
        check(
            "required_files",
            not missing_files,
            {"missing_files": missing_files, "required_files": required_files},
        ),
        check(
            "release_notes_template",
            not missing_note_fields
            and len(policy.get("required_release_note_fields", [])) >= int(policy.get("minimum_release_note_field_count", 0)),
            {
                "missing_fields": missing_note_fields,
                "release_note_field_count": len(policy.get("required_release_note_fields", [])),
                "minimum_release_note_field_count": policy.get("minimum_release_note_field_count"),
            },
        ),
        check(
            "evidence_reference_contract",
            not missing_evidence_refs
            and len(policy.get("required_evidence_references", [])) >= int(policy.get("minimum_evidence_reference_count", 0)),
            {
                "missing_references": missing_evidence_refs,
                "evidence_reference_count": len(policy.get("required_evidence_references", [])),
                "minimum_evidence_reference_count": policy.get("minimum_evidence_reference_count"),
            },
        ),
        check(
            "validation_command_contract",
            not missing_validation_commands
            and len(policy.get("required_validation_commands", [])) >= int(policy.get("minimum_validation_command_count", 0)),
            {
                "missing_commands": missing_validation_commands,
                "validation_command_count": len(policy.get("required_validation_commands", [])),
                "minimum_validation_command_count": policy.get("minimum_validation_command_count"),
            },
        ),
        check(
            "boundary_language_contract",
            not missing_boundaries
            and len(policy.get("boundary_statements", [])) >= int(policy.get("minimum_boundary_statement_count", 0)),
            {
                "missing_boundaries": missing_boundaries,
                "boundary_statement_count": len(policy.get("boundary_statements", [])),
                "minimum_boundary_statement_count": policy.get("minimum_boundary_statement_count"),
            },
        ),
        check(
            "contribution_change_summary",
            not missing_contribution_terms,
            {"missing_terms": missing_contribution_terms},
        ),
    ]
    metrics = {
        "required_file_count": len(required_files),
        "present_file_count": len(required_files) - len(missing_files),
        "release_note_field_count": len(policy.get("required_release_note_fields", [])),
        "evidence_reference_count": len(policy.get("required_evidence_references", [])),
        "validation_command_count": len(policy.get("required_validation_commands", [])),
        "boundary_statement_count": len(policy.get("boundary_statements", [])),
        "contribution_term_count": len(policy.get("required_contribution_terms", [])),
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


def evaluate_fixtures(files: dict[str, str | None], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(files, fixture)
        checks, _ = evaluate_documents(mutated, policy)
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
    checks, metrics = evaluate_documents(files, policy)
    fixtures = evaluate_fixtures(files, policy)
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
    (output_dir / "release-notes-contract-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Release Notes Contract Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that release notes and contribution guidance disclose",
        "the changed capability, evidence artifacts, validation commands, and",
        "deployment boundaries before a release packet is trusted.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Required files | {report['required_file_count']} |",
        f"| Present files | {report['present_file_count']} |",
        f"| Release-note fields | {report['release_note_field_count']} |",
        f"| Evidence references | {report['evidence_reference_count']} |",
        f"| Validation commands | {report['validation_command_count']} |",
        f"| Boundary statements | {report['boundary_statement_count']} |",
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
    (output_dir / "release-notes-contract-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/release-notes-contract-policy.json")
    parser.add_argument("--output-dir", default="out/release-notes-contract-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'release-notes-contract-audit.json'}")
    print(f"wrote {output_dir / 'release-notes-contract-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
