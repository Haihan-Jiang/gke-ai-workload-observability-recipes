#!/usr/bin/env python3
"""Audit the shortest reviewer path for reproducible current-head evidence."""

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


def aggregate_text(files: dict[str, str | None]) -> str:
    return "\n".join(text for text in files.values() if text)


def evaluate_documents(
    repo_root: Path,
    files: dict[str, str | None],
    policy: dict[str, Any],
    release_readiness_source: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_files = list(policy["required_files"])
    missing_files = [path for path in required_files if files.get(path) is None]
    reviewer_surface = str(policy["reviewer_surface"])
    reviewer_text = files.get(reviewer_surface)
    all_text = aggregate_text(files)

    missing_reviewer_commands = missing_terms(reviewer_text, list(policy.get("required_commands", [])))
    aggregate_command_gaps = missing_terms(all_text, list(policy.get("required_commands", [])))
    command_count = len(policy.get("required_commands", [])) - len(aggregate_command_gaps)

    missing_evidence_paths = []
    existing_evidence_path_count = 0
    for evidence_path in policy.get("required_evidence_paths", []):
        missing = []
        if reviewer_text is None or evidence_path not in reviewer_text:
            missing.append("not referenced")
        if not (repo_root / evidence_path).is_file():
            missing.append("missing target")
        else:
            existing_evidence_path_count += 1
        if missing:
            missing_evidence_paths.append({"path": evidence_path, "missing": missing})

    missing_boundary_terms = missing_terms(all_text, list(policy.get("required_boundary_terms", [])))
    boundary_term_count = len(policy.get("required_boundary_terms", [])) - len(missing_boundary_terms)

    release_check_names = release_checks(release_readiness_source)
    release_control_gaps = []
    release_control_count = 0
    for control in policy.get("required_release_controls", []):
        missing = []
        if reviewer_text is None or control not in reviewer_text:
            missing.append("not referenced")
        if control not in release_check_names:
            missing.append("missing release-readiness check")
        if missing:
            release_control_gaps.append({"control": control, "missing": missing})
        else:
            release_control_count += 1

    checks = [
        check(
            "required_files",
            not missing_files
            and len(required_files) >= int(policy.get("minimum_required_file_count", 0)),
            {"missing_files": missing_files, "required_files": required_files},
        ),
        check(
            "reviewer_command_contract",
            not missing_reviewer_commands
            and not aggregate_command_gaps
            and command_count >= int(policy.get("minimum_command_count", 0)),
            {
                "missing_reviewer_commands": missing_reviewer_commands,
                "missing_aggregate_commands": aggregate_command_gaps,
                "command_count": command_count,
                "minimum_command_count": policy.get("minimum_command_count"),
            },
        ),
        check(
            "evidence_packet_contract",
            not missing_evidence_paths
            and len(policy.get("required_evidence_paths", [])) >= int(policy.get("minimum_evidence_path_count", 0)),
            {
                "evidence_path_count": len(policy.get("required_evidence_paths", [])),
                "existing_evidence_path_count": existing_evidence_path_count,
                "missing_evidence_paths": missing_evidence_paths,
            },
        ),
        check(
            "review_boundary_contract",
            not missing_boundary_terms
            and boundary_term_count >= int(policy.get("minimum_boundary_term_count", 0)),
            {
                "boundary_term_count": boundary_term_count,
                "missing_boundary_terms": missing_boundary_terms,
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
        "command_count": command_count,
        "evidence_path_count": len(policy.get("required_evidence_paths", [])),
        "existing_evidence_path_count": existing_evidence_path_count,
        "boundary_term_count": boundary_term_count,
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
    paths = set(policy["required_files"])
    paths.add(str(policy["reviewer_surface"]))
    files = read_files(repo_root, sorted(paths))
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
    (output_dir / "reviewer-reproducibility-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Reviewer Reproducibility Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that reviewers have a short current-head proof path,",
        "including reproducible commands, committed evidence packet links,",
        "release-readiness control linkage, and project boundary language.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Required files | {report['required_file_count']} |",
        f"| Present files | {report['present_file_count']} |",
        f"| Commands | {report['command_count']} |",
        f"| Evidence paths | {report['evidence_path_count']} |",
        f"| Existing evidence paths | {report['existing_evidence_path_count']} |",
        f"| Boundary terms | {report['boundary_term_count']} |",
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
    (output_dir / "reviewer-reproducibility-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/reviewer-reproducibility-policy.json")
    parser.add_argument("--release-readiness-source", default="demo/release_readiness.py")
    parser.add_argument("--output-dir", default="out/reviewer-reproducibility-audit")
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
    print(f"wrote {output_dir / 'reviewer-reproducibility-audit.json'}")
    print(f"wrote {output_dir / 'reviewer-reproducibility-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
