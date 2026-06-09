#!/usr/bin/env python3
"""Audit open-source license, NOTICE, and third-party reference boundaries."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
ACTION_RE = re.compile(r"\buses:\s*([^\s#]+)")
IMAGE_RE = re.compile(r"\bimage:\s*['\"]?([^'\"\s#]+)")


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


def collect_matches(files: dict[str, str | None], paths: list[str], regex: re.Pattern[str]) -> list[dict[str, str]]:
    matches = []
    for path in paths:
        for value in regex.findall(files.get(path) or ""):
            matches.append({"path": path, "value": value})
    return matches


def evaluate_files(files: dict[str, str | None], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    license_path = str(policy["license_file"])
    notice_path = str(policy["notice_file"])
    readme_path = str(policy["readme_file"])
    workflow_files = list(policy.get("workflow_files", []))
    image_files = list(policy.get("image_files", []))
    actions = collect_matches(files, workflow_files, ACTION_RE)
    images = collect_matches(files, image_files, IMAGE_RE)
    allowed_actions = set(policy.get("allowed_actions", []))
    allowed_images = set(policy.get("allowed_images", []))
    action_violations = [item for item in actions if item["value"] not in allowed_actions]
    image_violations = [item for item in images if item["value"] not in allowed_images]
    license_missing = files.get(license_path) is None
    notice_missing = files.get(notice_path) is None
    readme_missing = files.get(readme_path) is None
    license_term_gaps = missing_terms(files.get(license_path), list(policy.get("required_license_terms", [])))
    notice_term_gaps = missing_terms(files.get(notice_path), list(policy.get("required_notice_terms", [])))
    readme_term_gaps = missing_terms(files.get(readme_path), list(policy.get("required_readme_terms", [])))
    checks = [
        check(
            "license_file",
            not license_missing and not license_term_gaps,
            {"path": license_path, "missing_terms": license_term_gaps},
        ),
        check(
            "notice_file",
            not notice_missing and not notice_term_gaps,
            {"path": notice_path, "missing_terms": notice_term_gaps},
        ),
        check(
            "readme_license_reference",
            not readme_missing and not readme_term_gaps,
            {"path": readme_path, "missing_terms": readme_term_gaps},
        ),
        check("approved_actions", not action_violations, {"actions": actions, "violations": action_violations}),
        check("approved_images", not image_violations, {"images": images, "violations": image_violations}),
        check(
            "third_party_reference_inventory",
            len(actions) >= 2 and len(images) >= 4,
            {"action_count": len(actions), "image_count": len(images)},
        ),
    ]
    metrics = {
        "action_count": len(actions),
        "image_count": len(images),
        "third_party_reference_count": len(actions) + len(images),
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
    elif mutation == "append_text":
        mutated[path] = (mutated.get(path) or "") + str(fixture.get("text", ""))
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(files: dict[str, str | None], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        checks, _ = evaluate_files(apply_fixture(files, fixture), policy)
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


def policy_paths(policy: dict[str, Any]) -> list[str]:
    paths = [policy["license_file"], policy["notice_file"], policy["readme_file"]]
    paths.extend(policy.get("workflow_files", []))
    paths.extend(policy.get("image_files", []))
    return sorted({str(path) for path in paths})


def build_report(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    files = read_files(repo_root, policy_paths(policy))
    checks, metrics = evaluate_files(files, policy)
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
    (output_dir / "oss-license-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# OSS License Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks the public open-source compliance boundary for the",
        "lab: Apache-2.0 license text, NOTICE coverage, README license links,",
        "approved GitHub Actions, approved container images, and third-party",
        "reference inventory.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| GitHub Actions references | {report['action_count']} |",
        f"| Container image references | {report['image_count']} |",
        f"| Third-party references | {report['third_party_reference_count']} |",
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
    (output_dir / "oss-license-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/oss-license-policy.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'oss-license-audit.json'}")
    print(f"wrote {output_dir / 'oss-license-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
