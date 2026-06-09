#!/usr/bin/env python3
"""Audit GitHub issue, pull request, and support intake governance."""

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


def count_present_issue_templates(files: dict[str, str | None]) -> int:
    return sum(
        1
        for path, text in files.items()
        if path.startswith(".github/ISSUE_TEMPLATE/")
        and path.endswith((".yml", ".yaml"))
        and not path.endswith("config.yml")
        and text is not None
    )


def evaluate_documents(files: dict[str, str | None], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_files = list(policy["required_files"])
    missing_files = [path for path in required_files if files.get(path) is None]
    bug_text = files.get(".github/ISSUE_TEMPLATE/bug_report.yml")
    feature_text = files.get(".github/ISSUE_TEMPLATE/feature_request.yml")
    config_text = files.get(".github/ISSUE_TEMPLATE/config.yml")
    pr_text = files.get(".github/PULL_REQUEST_TEMPLATE.md")
    support_text = files.get("SUPPORT.md")
    contributing_text = files.get("CONTRIBUTING.md")

    bug_missing = missing_terms(bug_text, list(policy.get("required_bug_terms", [])))
    feature_missing = missing_terms(feature_text, list(policy.get("required_feature_terms", [])))
    security_surface = "\n".join(text for text in [bug_text, config_text, support_text] if text)
    security_missing = missing_terms(security_surface, list(policy.get("required_security_terms", [])))
    pr_missing = missing_terms(pr_text, list(policy.get("required_pr_terms", [])))
    validation_missing = missing_terms(pr_text, list(policy.get("required_validation_commands", [])))
    support_missing = missing_terms(support_text, list(policy.get("required_support_terms", [])))
    contribution_missing = missing_terms(contributing_text, list(policy.get("required_contribution_terms", [])))
    issue_template_count = count_present_issue_templates(files)
    pr_validation_command_count = len(policy.get("required_validation_commands", [])) - len(validation_missing)
    support_term_count = len(policy.get("required_support_terms", [])) - len(support_missing)

    checks = [
        check(
            "required_files",
            not missing_files,
            {"missing_files": missing_files, "required_files": required_files},
        ),
        check(
            "issue_intake_contract",
            not bug_missing and issue_template_count >= int(policy.get("minimum_issue_template_count", 0)),
            {
                "missing_terms": bug_missing,
                "issue_template_count": issue_template_count,
                "minimum_issue_template_count": policy.get("minimum_issue_template_count"),
            },
        ),
        check(
            "feature_request_contract",
            not feature_missing,
            {"missing_terms": feature_missing},
        ),
        check(
            "issue_security_boundary",
            not security_missing,
            {"missing_terms": security_missing},
        ),
        check(
            "pull_request_validation_contract",
            not pr_missing
            and not validation_missing
            and pr_validation_command_count >= int(policy.get("minimum_pr_validation_command_count", 0)),
            {
                "missing_terms": pr_missing,
                "missing_validation_commands": validation_missing,
                "pr_validation_command_count": pr_validation_command_count,
                "minimum_pr_validation_command_count": policy.get("minimum_pr_validation_command_count"),
            },
        ),
        check(
            "support_boundary",
            not support_missing and support_term_count >= int(policy.get("minimum_support_term_count", 0)),
            {
                "missing_terms": support_missing,
                "support_term_count": support_term_count,
                "minimum_support_term_count": policy.get("minimum_support_term_count"),
            },
        ),
        check(
            "contribution_summary_linkage",
            not contribution_missing,
            {"missing_terms": contribution_missing},
        ),
    ]
    metrics = {
        "required_file_count": len(required_files),
        "present_file_count": len(required_files) - len(missing_files),
        "issue_template_count": issue_template_count,
        "pr_validation_command_count": pr_validation_command_count,
        "support_term_count": support_term_count,
        "contribution_term_count": len(policy.get("required_contribution_terms", [])) - len(contribution_missing),
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
    (output_dir / "maintainer-intake-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Maintainer Intake Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that public issue, pull request, and support intake",
        "surfaces ask for reproducible evidence, validation commands, security",
        "routing, no-secret boundaries, and support expectations before the",
        "repository is treated as maintainer-ready.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Required files | {report['required_file_count']} |",
        f"| Present files | {report['present_file_count']} |",
        f"| Issue templates | {report['issue_template_count']} |",
        f"| PR validation commands | {report['pr_validation_command_count']} |",
        f"| Support terms | {report['support_term_count']} |",
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
    (output_dir / "maintainer-intake-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/maintainer-intake-policy.json")
    parser.add_argument("--output-dir", default="out/maintainer-intake-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'maintainer-intake-audit.json'}")
    print(f"wrote {output_dir / 'maintainer-intake-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
