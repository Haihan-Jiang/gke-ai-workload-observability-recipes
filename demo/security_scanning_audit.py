#!/usr/bin/env python3
"""Audit CodeQL security scanning workflow governance for release evidence."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
SEMVER_REF_RE = re.compile(r"^v(?P<major>[0-9]+)(?:\\.[0-9]+){0,2}$")
SHA_REF_RE = re.compile(r"^[0-9a-f]{40}$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_workflow(path: Path) -> dict[str, Any]:
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("ruby is required to parse GitHub Actions workflow YAML")
    script = "require 'yaml'; require 'json'; puts JSON.generate(YAML.load_file(ARGV[0]))"
    result = subprocess.run(
        [ruby, "-e", script, str(path)],
        text=True,
        check=True,
        capture_output=True,
    )
    loaded = json.loads(result.stdout)
    return loaded if isinstance(loaded, dict) else {}


def workflow_on(workflow: dict[str, Any]) -> dict[str, Any]:
    raw = workflow.get("on", workflow.get("true", {}))
    if isinstance(raw, str):
        return {raw: {}}
    if isinstance(raw, list):
        return {str(item): {} for item in raw}
    if isinstance(raw, dict):
        return raw
    return {}


def jobs_for(workflow: dict[str, Any]) -> dict[str, Any]:
    jobs = workflow.get("jobs", {})
    return jobs if isinstance(jobs, dict) else {}


def steps_for(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps", [])
    return [step for step in steps if isinstance(step, dict)] if isinstance(steps, list) else []


def split_action_ref(uses: str) -> tuple[str, str]:
    if "@" not in uses:
        return uses, ""
    return uses.rsplit("@", 1)


def action_major(ref: str) -> int | None:
    match = SEMVER_REF_RE.match(ref)
    if not match:
        return None
    return int(match.group("major"))


def collect_actions(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for job_name, job in jobs_for(workflow).items():
        if not isinstance(job, dict):
            continue
        for step in steps_for(job):
            uses = step.get("uses")
            if not isinstance(uses, str):
                continue
            action, ref = split_action_ref(uses)
            actions.append(
                {
                    "job": job_name,
                    "uses": uses,
                    "action": action,
                    "ref": ref,
                    "major": action_major(ref),
                    "sha_pinned": bool(SHA_REF_RE.match(ref)),
                }
            )
    return actions


def matrix_languages(job: dict[str, Any]) -> list[str]:
    strategy = job.get("strategy", {})
    if not isinstance(strategy, dict):
        return []
    matrix = strategy.get("matrix", {})
    if not isinstance(matrix, dict):
        return []
    languages = matrix.get("language", [])
    return [str(item) for item in languages] if isinstance(languages, list) else []


def codeql_queries(job: dict[str, Any]) -> list[str]:
    for step in steps_for(job):
        if step.get("uses") == "github/codeql-action/init@v4":
            with_block = step.get("with", {})
            if isinstance(with_block, dict):
                raw = str(with_block.get("queries", ""))
                return [item.strip() for item in raw.split(",") if item.strip()]
    return []


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def evaluate_workflow(
    *,
    workflow_exists: bool,
    workflow: dict[str, Any],
    release_source: str,
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    triggers = workflow_on(workflow)
    jobs = jobs_for(workflow)
    job_name = str(policy.get("job", {}).get("name", "analyze"))
    job = jobs.get(job_name, {}) if isinstance(jobs.get(job_name, {}), dict) else {}
    permissions = workflow.get("permissions")
    permissions_map = permissions if isinstance(permissions, dict) else {}
    concurrency = workflow.get("concurrency", {})
    concurrency_map = concurrency if isinstance(concurrency, dict) else {}
    actions = collect_actions(workflow)
    actions_by_name = {item["action"]: item for item in actions}
    languages = matrix_languages(job)
    queries = codeql_queries(job)

    required_trigger_gaps = []
    for trigger_name, trigger_policy in policy.get("required_triggers", {}).items():
        trigger_config = triggers.get(trigger_name)
        if trigger_config is None and trigger_name not in triggers:
            required_trigger_gaps.append({"trigger": trigger_name, "reason": "missing"})
            continue
        if trigger_name == "push":
            branches = []
            if isinstance(trigger_config, dict):
                branches = list(trigger_config.get("branches", []))
            missing = sorted(
                branch for branch in trigger_policy.get("branches", []) if branch not in branches
            )
            if missing:
                required_trigger_gaps.append({"trigger": trigger_name, "missing_branches": missing})
    forbidden_triggers = sorted(
        trigger for trigger in policy.get("forbidden_triggers", []) if trigger in triggers
    )

    required_permissions = policy.get("required_permissions", {})
    permission_gaps = [
        {"permission": key, "expected": value, "observed": permissions_map.get(key)}
        for key, value in required_permissions.items()
        if permissions_map.get(key) != value
    ]
    allowed_write_permissions = set(policy.get("allowed_write_permissions", []))
    unexpected_writes = [
        {"permission": key, "value": value}
        for key, value in permissions_map.items()
        if isinstance(value, str) and value.endswith("write") and key not in allowed_write_permissions
    ]

    group = str(concurrency_map.get("group", ""))
    missing_concurrency_fragments = [
        fragment for fragment in policy.get("required_concurrency_group_fragments", [])
        if fragment not in group
    ]

    action_gaps = []
    forbidden_refs = set(policy.get("forbidden_action_refs", []))
    codeql_action_count = 0
    for action_name, action_policy in policy.get("required_actions", {}).items():
        action = actions_by_name.get(action_name)
        if not action:
            action_gaps.append({"action": action_name, "reason": "missing"})
            continue
        ref = str(action.get("ref", ""))
        major = action.get("major")
        if ref in forbidden_refs:
            action_gaps.append({"action": action_name, "reason": "forbidden_ref", "ref": ref})
            continue
        if major is None and not action.get("sha_pinned"):
            action_gaps.append({"action": action_name, "reason": "floating_ref", "ref": ref})
            continue
        if major is not None and major < int(action_policy.get("minimum_major", 0)):
            action_gaps.append(
                {
                    "action": action_name,
                    "ref": ref,
                    "observed_major": major,
                    "minimum_major": action_policy.get("minimum_major"),
                }
            )
            continue
        if action_name.startswith("github/codeql-action/"):
            codeql_action_count += 1

    job_policy = policy.get("job", {})
    timeout = job.get("timeout-minutes")
    strategy = job.get("strategy", {})
    fail_fast = strategy.get("fail-fast") if isinstance(strategy, dict) else None
    required_language = str(job_policy.get("matrix_language", ""))
    required_queries = list(policy.get("required_query_suites", []))
    missing_queries = [query for query in required_queries if query not in queries]
    required_controls = list(policy.get("required_release_controls", []))
    missing_controls = [control for control in required_controls if control not in release_source]
    release_control_count = len(required_controls) - len(missing_controls)

    checks = [
        check(
            "workflow_inventory",
            workflow_exists
            and workflow.get("name") == policy.get("required_workflow_name")
            and job_name in jobs,
            {
                "workflow_exists": workflow_exists,
                "workflow_name": workflow.get("name"),
                "job_names": sorted(jobs),
            },
        ),
        check(
            "trigger_contract",
            not required_trigger_gaps and not forbidden_triggers,
            {
                "triggers": sorted(triggers),
                "required_trigger_gaps": required_trigger_gaps,
                "forbidden_triggers": forbidden_triggers,
            },
        ),
        check(
            "permission_contract",
            isinstance(permissions, dict) and not permission_gaps and not unexpected_writes,
            {
                "permissions": permissions,
                "permission_gaps": permission_gaps,
                "unexpected_writes": unexpected_writes,
            },
        ),
        check(
            "concurrency_contract",
            isinstance(concurrency, dict)
            and not missing_concurrency_fragments
            and concurrency_map.get("cancel-in-progress") is True,
            {
                "group": group,
                "missing_fragments": missing_concurrency_fragments,
                "cancel_in_progress": concurrency_map.get("cancel-in-progress"),
            },
        ),
        check(
            "job_contract",
            job.get("runs-on") == job_policy.get("runs_on")
            and isinstance(timeout, int)
            and 0 < timeout <= int(job_policy.get("timeout_minutes_max", 0))
            and required_language in languages
            and fail_fast is False,
            {
                "runs_on": job.get("runs-on"),
                "timeout_minutes": timeout,
                "languages": languages,
                "fail_fast": fail_fast,
            },
        ),
        check(
            "codeql_action_contract",
            not action_gaps
            and codeql_action_count >= int(policy.get("minimum_codeql_action_count", 0)),
            {"actions": actions, "action_gaps": action_gaps, "codeql_action_count": codeql_action_count},
        ),
        check(
            "query_suite_contract",
            not missing_queries
            and len(queries) >= int(policy.get("minimum_query_suite_count", 0)),
            {"queries": queries, "missing_queries": missing_queries},
        ),
        check(
            "release_control_linkage",
            release_control_count >= int(policy.get("minimum_release_control_count", 0)),
            {"release_control_count": release_control_count, "missing_controls": missing_controls},
        ),
    ]
    metrics = {
        "workflow_count": 1 if workflow_exists else 0,
        "job_count": len(jobs),
        "language_count": len(set(languages)),
        "query_suite_count": len(set(queries)),
        "codeql_action_count": codeql_action_count,
        "release_control_count": release_control_count,
    }
    return checks, metrics


def apply_fixture(
    *,
    workflow_exists: bool,
    workflow: dict[str, Any],
    release_source: str,
    fixture: dict[str, Any],
) -> tuple[bool, dict[str, Any], str]:
    mutated_exists = workflow_exists
    mutated = copy.deepcopy(workflow)
    mutated_release_source = release_source
    mutation = fixture["mutation"]
    if mutation == "remove_workflow":
        mutated_exists = False
        mutated = {}
    elif mutation == "remove_trigger":
        workflow_on(mutated).pop(str(fixture["trigger"]), None)
    elif mutation == "add_trigger":
        workflow_on(mutated)[str(fixture["trigger"])] = {}
    elif mutation == "remove_permission":
        permissions = mutated.get("permissions", {})
        if isinstance(permissions, dict):
            permissions.pop(str(fixture["permission"]), None)
    elif mutation == "remove_concurrency":
        mutated.pop("concurrency", None)
    elif mutation == "set_matrix_language":
        job = jobs_for(mutated).get("analyze", {})
        if isinstance(job, dict):
            job.setdefault("strategy", {}).setdefault("matrix", {})["language"] = [fixture["value"]]
    elif mutation == "set_action_ref":
        action = str(fixture["action"])
        ref = str(fixture["ref"])
        for job in jobs_for(mutated).values():
            if not isinstance(job, dict):
                continue
            for step in steps_for(job):
                uses = step.get("uses")
                if isinstance(uses, str) and split_action_ref(uses)[0] == action:
                    step["uses"] = f"{action}@{ref}"
    elif mutation == "remove_query_suite":
        query = str(fixture["query"])
        for step in steps_for(jobs_for(mutated).get("analyze", {})):
            if step.get("uses") == "github/codeql-action/init@v4":
                with_block = step.get("with", {})
                if isinstance(with_block, dict):
                    suites = [item for item in codeql_queries({"steps": [step]}) if item != query]
                    with_block["queries"] = ",".join(suites)
    elif mutation == "remove_release_control":
        mutated_release_source = mutated_release_source.replace(str(fixture["control"]), "")
    else:
        raise ValueError(f"unknown fixture mutation: {mutation}")
    return mutated_exists, mutated, mutated_release_source


def evaluate_fixtures(
    *,
    workflow_exists: bool,
    workflow: dict[str, Any],
    release_source: str,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_exists, mutated, mutated_release_source = apply_fixture(
            workflow_exists=workflow_exists,
            workflow=workflow,
            release_source=release_source,
            fixture=fixture,
        )
        checks, _ = evaluate_workflow(
            workflow_exists=mutated_exists,
            workflow=mutated,
            release_source=mutated_release_source,
            policy=policy,
        )
        by_name = {item["name"]: item["ok"] for item in checks}
        expected = str(fixture["expected_failed_check"])
        results.append(
            {
                "name": fixture["name"],
                "expected_failed_check": expected,
                "detected": by_name.get(expected) is False,
            }
        )
    return results


def build_report(
    repo_root: Path,
    policy: dict[str, Any],
    *,
    release_readiness_source: Path,
) -> dict[str, Any]:
    workflow_path = repo_root / str(policy["workflow_path"])
    workflow_exists = workflow_path.is_file()
    workflow = load_workflow(workflow_path) if workflow_exists else {}
    release_source = (repo_root / release_readiness_source).read_text(encoding="utf-8")
    checks, metrics = evaluate_workflow(
        workflow_exists=workflow_exists,
        workflow=workflow,
        release_source=release_source,
        policy=policy,
    )
    fixtures = evaluate_fixtures(
        workflow_exists=workflow_exists,
        workflow=workflow,
        release_source=release_source,
        policy=policy,
    )
    detected_fixture_count = sum(1 for item in fixtures if item["detected"])
    checks.append(
        check(
            "negative_fixture_coverage",
            detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
            {"detected_fixture_count": detected_fixture_count},
        )
    )
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "failed_count": failed_count,
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "workflow_path": str(policy["workflow_path"]),
        "workflow_name": workflow.get("name"),
        **metrics,
        "checks": checks,
        "fixtures": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "security-scanning-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Security Scanning Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that CodeQL static analysis is configured with safe",
        "triggers, least privilege, Python language coverage, security query",
        "suites, and release-control linkage before security-scanning claims",
        "are trusted.",
        "",
        "## Summary",
        "",
        f"- Workflows: `{report['workflow_count']}`",
        f"- Jobs: `{report['job_count']}`",
        f"- Languages: `{report['language_count']}`",
        f"- CodeQL actions: `{report['codeql_action_count']}`",
        f"- Query suites: `{report['query_suite_count']}`",
        f"- Release controls linked: `{report['release_control_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    (output_dir / "security-scanning-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/security-scanning-policy.json")
    parser.add_argument("--release-readiness-source", default="demo/release_readiness.py")
    parser.add_argument("--output-dir", default="out/security-scanning-audit")
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
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())

