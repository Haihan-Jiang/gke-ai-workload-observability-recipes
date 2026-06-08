#!/usr/bin/env python3
"""Audit local developer runtime and command-entry contracts."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
TARGET_RE = re.compile(r"^(?P<target>[A-Za-z0-9_.-]+):(?:\\s|$)")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_files(repo_root: Path, paths: list[str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for path in paths:
        absolute = repo_root / path
        result[path] = absolute.read_text(encoding="utf-8") if absolute.is_file() else None
    return result


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def parse_make_targets(makefile: str | None) -> dict[str, list[str]]:
    if not makefile:
        return {}
    targets: dict[str, list[str]] = {}
    current: str | None = None
    for line in makefile.splitlines():
        match = TARGET_RE.match(line)
        if match and not line.startswith("."):
            current = match.group("target")
            targets[current] = []
            continue
        if current and line.startswith("\t"):
            targets[current].append(line.strip())
    return targets


def parse_phony_targets(makefile: str | None) -> set[str]:
    phony: set[str] = set()
    for line in (makefile or "").splitlines():
        if line.startswith(".PHONY:"):
            phony.update(line.split(":", 1)[1].split())
    return phony


def missing_terms(text: str | None, terms: list[str]) -> list[str]:
    if text is None:
        return terms
    return [term for term in terms if term not in text]


def evaluate_files(files: dict[str, str | None], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_files = list(policy["required_files"])
    missing_files = [path for path in required_files if files.get(path) is None]
    makefile = files.get("Makefile")
    targets = parse_make_targets(makefile)
    phony = parse_phony_targets(makefile)
    required_targets = list(policy.get("required_make_targets", []))
    missing_targets = [target for target in required_targets if target not in targets]
    missing_phony = [target for target in required_targets if target not in phony]
    command_gaps = []
    for target, fragment in policy.get("target_command_fragments", {}).items():
        body = "\n".join(targets.get(target, []))
        if fragment not in body:
            command_gaps.append(
                {
                    "target": target,
                    "required_fragment": fragment,
                    "body": body,
                }
            )
    python_version = (files.get(".python-version") or "").strip()
    python_variable = policy.get("required_make_variable", "")
    docs_missing = missing_terms(
        files.get("docs/developer-runtime.md"),
        list(policy.get("required_docs_terms", [])),
    )
    gitignore_missing = missing_terms(
        files.get(".gitignore"),
        list(policy.get("required_gitignore_entries", [])),
    )
    checks = [
        check(
            "required_files",
            not missing_files,
            {"missing_files": missing_files, "required_files": required_files},
        ),
        check(
            "make_target_inventory",
            not missing_targets and not missing_phony,
            {
                "missing_targets": missing_targets,
                "missing_phony_targets": missing_phony,
                "targets": sorted(targets),
            },
        ),
        check(
            "make_command_contract",
            not command_gaps,
            {"command_gaps": command_gaps},
        ),
        check(
            "python_runtime_contract",
            python_version == policy.get("required_python_version")
            and makefile is not None
            and python_variable in makefile,
            {
                "python_version": python_version,
                "required_python_version": policy.get("required_python_version"),
                "python_variable_present": bool(makefile and python_variable in makefile),
            },
        ),
        check(
            "developer_runtime_docs",
            not docs_missing,
            {"missing_terms": docs_missing},
        ),
        check(
            "output_boundary",
            not gitignore_missing,
            {"missing_gitignore_entries": gitignore_missing},
        ),
    ]
    metrics = {
        "required_file_count": len(required_files),
        "present_file_count": len(required_files) - len(missing_files),
        "make_target_count": len(targets),
        "phony_target_count": len(phony),
    }
    return checks, metrics


def remove_make_target(makefile: str | None, target: str) -> str | None:
    if makefile is None:
        return None
    lines = makefile.splitlines()
    result = []
    skip = False
    for line in lines:
        match = TARGET_RE.match(line)
        if match and match.group("target") == target:
            skip = True
            continue
        if skip and line and not line.startswith("\t") and not line.startswith(" "):
            skip = False
        if skip:
            continue
        if line.startswith(".PHONY:"):
            parts = [part for part in line.split(":", 1)[1].split() if part != target]
            result.append(".PHONY: " + " ".join(parts))
            continue
        result.append(line)
    return "\n".join(result) + "\n"


def apply_fixture(files: dict[str, str | None], fixture: dict[str, Any]) -> dict[str, str | None]:
    mutated = copy.deepcopy(files)
    path = str(fixture.get("path", ""))
    mutation = fixture.get("mutation")
    if mutation == "remove_file":
        mutated[path] = None
    elif mutation == "replace_text":
        text = mutated.get(path)
        if text is not None:
            mutated[path] = text.replace(str(fixture.get("from", "")), str(fixture.get("to", "")))
    elif mutation == "remove_text":
        text = mutated.get(path)
        if text is not None:
            mutated[path] = text.replace(str(fixture.get("text", "")), "")
    elif mutation == "remove_make_target":
        mutated["Makefile"] = remove_make_target(mutated.get("Makefile"), str(fixture.get("target", "")))
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(files: dict[str, str | None], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(files, fixture)
        checks, _ = evaluate_files(mutated, policy)
        checks_by_name = {item["name"]: item for item in checks}
        expected = str(fixture.get("expected_failed_check"))
        detected = checks_by_name.get(expected, {}).get("ok") is False
        results.append(
            {
                "name": fixture.get("name"),
                "mutation": fixture.get("mutation"),
                "expected_failed_check": expected,
                "detected": detected,
            }
        )
    return results


def build_report(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    files = read_files(repo_root, list(policy["required_files"]))
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
        "required_file_count": metrics["required_file_count"],
        "present_file_count": metrics["present_file_count"],
        "make_target_count": metrics["make_target_count"],
        "phony_target_count": metrics["phony_target_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "checks": checks,
        "fixtures": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "developer-runtime-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Developer Runtime Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks whether contributors have a stable local runtime",
        "contract and repeatable command entrypoints for validation, evidence",
        "generation, demos, and optional Kubernetes smoke tests.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Required files | {report['required_file_count']} |",
        f"| Present files | {report['present_file_count']} |",
        f"| Make targets | {report['make_target_count']} |",
        f"| PHONY targets | {report['phony_target_count']} |",
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
    (output_dir / "developer-runtime-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/developer-runtime-policy.json")
    parser.add_argument("--output-dir", default="out/developer-runtime-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'developer-runtime-audit.json'}")
    print(f"wrote {output_dir / 'developer-runtime-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
