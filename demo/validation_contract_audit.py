#!/usr/bin/env python3
"""Audit that validation scripts cover the committed release evidence surface."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
PYTHON_COMMAND_RE = re.compile(r"^\s*python3\s+(demo/[A-Za-z0-9_]+\.py)\b", re.MULTILINE)
CONFIG_JSON_RE = re.compile(r"python3\s+-m\s+json\.tool\s+(config/[^\s]+\.json)\b")
EVIDENCE_JSON_RE = re.compile(r"python3\s+-m\s+json\.tool\s+(docs/evidence/[^\s]+\.json)\b")
RELEASE_ARGUMENT_RE = re.compile(r"parser\.add_argument\(\"--([a-z0-9-]+)\"")
SHELL_ARGUMENT_RE = re.compile(r"(?<![\w-])--([a-z0-9-]+)\b")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def shell_script(repo_root: Path, relative_path: str) -> str:
    return (repo_root / relative_path).read_text(encoding="utf-8")


def extract_python_commands(script_text: str) -> set[str]:
    return set(PYTHON_COMMAND_RE.findall(script_text))


def extract_py_compile_scripts(validate_text: str) -> set[str]:
    scripts: set[str] = set()
    in_block = False
    for line in validate_text.splitlines():
        if line.startswith("python3 -m py_compile"):
            in_block = True
            continue
        if not in_block:
            continue
        value = line.strip().rstrip("\\").strip()
        if not value:
            break
        if value.startswith("demo/") and value.endswith(".py"):
            scripts.add(value)
    return scripts


def extract_json_tool_targets(validate_text: str, pattern: re.Pattern[str]) -> set[str]:
    return set(pattern.findall(validate_text))


def extract_release_readiness_arguments(source_text: str) -> set[str]:
    return set(RELEASE_ARGUMENT_RE.findall(source_text))


def extract_shell_arguments(script_text: str) -> set[str]:
    return set(SHELL_ARGUMENT_RE.findall(script_text))


def expected_demo_scripts(repo_root: Path, policy: dict[str, Any]) -> set[str]:
    excluded = set(policy.get("excluded_demo_scripts", []))
    return {
        path.relative_to(repo_root).as_posix()
        for path in sorted((repo_root / "demo").glob("*.py"))
        if path.relative_to(repo_root).as_posix() not in excluded
    }


def expected_config_json(repo_root: Path) -> set[str]:
    return {
        path.relative_to(repo_root).as_posix()
        for path in sorted((repo_root / "config").glob("*.json"))
    }


def expected_evidence_json(repo_root: Path, release_readiness_text: str) -> set[str]:
    committed = {
        path.relative_to(repo_root).as_posix()
        for path in sorted((repo_root / "docs/evidence").glob("*.json"))
    }
    required = {
        f"docs/evidence/{name}"
        for name in re.findall(r'"([A-Za-z0-9-]+\.json)"', release_readiness_text)
    }
    return committed | required


def missing_items(expected: set[str], observed: set[str]) -> list[str]:
    return sorted(expected - observed)


def replace_in_py_compile_block(validate_text: str, target: str) -> str:
    lines = validate_text.splitlines()
    in_block = False
    for index, line in enumerate(lines):
        if line.startswith("python3 -m py_compile"):
            in_block = True
            continue
        if not in_block:
            continue
        if not line.strip():
            break
        if target in line:
            lines[index] = line.replace(target, "demo/not_compiled.py")
            break
    return "\n".join(lines) + "\n"


def replace_python_command(validate_text: str, target: str) -> str:
    lines = validate_text.splitlines()
    for index, line in enumerate(lines):
        if re.match(rf"^\s*python3\s+{re.escape(target)}\b", line):
            lines[index] = line.replace(target, "demo/not_validated.py", 1)
            break
    return "\n".join(lines) + "\n"


def replace_json_tool_target(validate_text: str, target: str) -> str:
    lines = validate_text.splitlines()
    for index, line in enumerate(lines):
        if "python3 -m json.tool" in line and target in line:
            lines[index] = line.replace(target, f"missing/{Path(target).name}", 1)
            break
    return "\n".join(lines) + "\n"


def apply_fixture(inputs: dict[str, str], fixture: dict[str, Any]) -> dict[str, str]:
    mutated = copy.deepcopy(inputs)
    target = str(fixture.get("target", ""))
    mutation = fixture.get("mutation")
    if mutation == "remove_py_compile_script":
        mutated["validate"] = replace_in_py_compile_block(mutated["validate"], target)
        return mutated
    if mutation == "remove_validate_script":
        mutated["validate"] = replace_python_command(mutated["validate"], target)
        return mutated
    if mutation in {"remove_config_json_tool", "remove_committed_json_tool"}:
        mutated["validate"] = replace_json_tool_target(mutated["validate"], target)
        return mutated
    if mutation == "remove_required_command":
        mutated["validate"] = mutated["validate"].replace(target, f"missing/{Path(target).name}", 1)
        return mutated
    if mutation == "remove_release_arg":
        mutated["validate"] = mutated["validate"].replace(target, "--missing-release-argument", 1)
        return mutated
    raise ValueError(f"unsupported fixture mutation: {mutation}")


def evaluate_inputs(repo_root: Path, policy: dict[str, Any], inputs: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    generation_scripts = extract_python_commands(inputs["generate"])
    direct_validation_scripts = extract_python_commands(inputs["validate"])
    py_compile_scripts = extract_py_compile_scripts(inputs["validate"])
    config_json_targets = extract_json_tool_targets(inputs["validate"], CONFIG_JSON_RE)
    evidence_json_targets = extract_json_tool_targets(inputs["validate"], EVIDENCE_JSON_RE)
    release_args = extract_release_readiness_arguments(inputs["release_readiness"])
    validate_args = extract_shell_arguments(inputs["validate"])
    expected_py_compile = expected_demo_scripts(repo_root, policy)
    expected_configs = expected_config_json(repo_root)
    expected_evidence = expected_evidence_json(repo_root, inputs["release_readiness"])
    allowed_generate_only = set(policy.get("allowed_generate_only_scripts", []))
    required_direct_validation = generation_scripts - allowed_generate_only
    missing_required_commands = [
        command
        for command in policy.get("required_validate_commands", [])
        if str(command) not in inputs["validate"]
    ]
    checks = [
        check(
            "py_compile_contract",
            not missing_items(expected_py_compile, py_compile_scripts)
            and len(py_compile_scripts) >= int(policy.get("minimum_py_compile_script_count", 0)),
            {
                "missing_scripts": missing_items(expected_py_compile, py_compile_scripts),
                "observed_count": len(py_compile_scripts),
                "expected_count": len(expected_py_compile),
                "minimum": policy.get("minimum_py_compile_script_count"),
            },
        ),
        check(
            "generation_validation_contract",
            not missing_items(required_direct_validation, direct_validation_scripts)
            and len(generation_scripts) >= int(policy.get("minimum_generation_script_count", 0))
            and len(direct_validation_scripts) >= int(policy.get("minimum_direct_validation_script_count", 0)),
            {
                "missing_direct_validation_scripts": missing_items(required_direct_validation, direct_validation_scripts),
                "generation_script_count": len(generation_scripts),
                "direct_validation_script_count": len(direct_validation_scripts),
                "allowed_generate_only_scripts": sorted(allowed_generate_only),
            },
        ),
        check(
            "policy_json_contract",
            not missing_items(expected_configs, config_json_targets)
            and len(config_json_targets) >= int(policy.get("minimum_policy_json_count", 0)),
            {
                "missing_policy_json": missing_items(expected_configs, config_json_targets),
                "observed_count": len(config_json_targets),
                "expected_count": len(expected_configs),
                "minimum": policy.get("minimum_policy_json_count"),
            },
        ),
        check(
            "committed_json_contract",
            not missing_items(expected_evidence, evidence_json_targets)
            and len(evidence_json_targets) >= int(policy.get("minimum_committed_json_count", 0)),
            {
                "missing_committed_json": missing_items(expected_evidence, evidence_json_targets),
                "observed_count": len(evidence_json_targets),
                "expected_count": len(expected_evidence),
                "minimum": policy.get("minimum_committed_json_count"),
            },
        ),
        check(
            "release_readiness_argument_contract",
            not missing_items(release_args, validate_args)
            and len(release_args) >= int(policy.get("minimum_release_readiness_argument_count", 0)),
            {
                "missing_arguments": missing_items(release_args, validate_args),
                "release_argument_count": len(release_args),
                "validate_argument_count": len(validate_args),
                "minimum": policy.get("minimum_release_readiness_argument_count"),
            },
        ),
        check(
            "required_command_contract",
            not missing_required_commands
            and len(policy.get("required_validate_commands", [])) >= int(policy.get("minimum_required_command_count", 0)),
            {
                "missing_commands": missing_required_commands,
                "required_commands": policy.get("required_validate_commands", []),
            },
        ),
    ]
    metrics = {
        "py_compile_script_count": len(py_compile_scripts),
        "generation_script_count": len(generation_scripts),
        "direct_validation_script_count": len(direct_validation_scripts),
        "policy_json_count": len(config_json_targets),
        "committed_json_count": len(evidence_json_targets),
        "release_argument_count": len(release_args),
        "validate_argument_count": len(validate_args),
    }
    return checks, metrics


def evaluate_fixtures(repo_root: Path, policy: dict[str, Any], inputs: dict[str, str]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(inputs, fixture)
        checks, _ = evaluate_inputs(repo_root, policy, mutated)
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
    generate_script: Path,
    validate_script: Path,
    release_readiness_source: Path,
) -> dict[str, Any]:
    inputs = {
        "generate": shell_script(repo_root, str(generate_script)),
        "validate": shell_script(repo_root, str(validate_script)),
        "release_readiness": shell_script(repo_root, str(release_readiness_source)),
    }
    checks, metrics = evaluate_inputs(repo_root, policy, inputs)
    fixtures = evaluate_fixtures(repo_root, policy, inputs)
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
    (output_dir / "validation-contract-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Validation Contract Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit treats the validation scripts as release-critical evidence.",
        "It proves that generated evidence scripts, Python compile coverage,",
        "policy JSON validation, committed evidence JSON validation, and",
        "release-readiness arguments stay synchronized.",
        "",
        "## Summary",
        "",
        f"- Py-compiled demo scripts: `{report['py_compile_script_count']}`",
        f"- Generation scripts: `{report['generation_script_count']}`",
        f"- Direct validation scripts: `{report['direct_validation_script_count']}`",
        f"- Policy JSON files validated: `{report['policy_json_count']}`",
        f"- Committed evidence JSON files validated: `{report['committed_json_count']}`",
        f"- Release-readiness arguments: `{report['release_argument_count']}`",
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
    (output_dir / "validation-contract-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/validation-contract-policy.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--generate-script", default="scripts/generate-evidence.sh")
    parser.add_argument("--validate-script", default="scripts/validate.sh")
    parser.add_argument("--release-readiness-source", default="demo/release_readiness.py")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    report = build_report(
        repo_root,
        load_json(repo_root / args.policy),
        generate_script=Path(args.generate_script),
        validate_script=Path(args.validate_script),
        release_readiness_source=Path(args.release_readiness_source),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'validation-contract-audit.json'}")
    print(f"wrote {output_dir / 'validation-contract-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
