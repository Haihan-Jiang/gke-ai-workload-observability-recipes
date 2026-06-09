#!/usr/bin/env python3
"""Audit GitHub Actions workflow governance for release evidence."""

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
    # Ruby's YAML 1.1 parser treats an unquoted top-level `on` key as boolean true.
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


def validate_job(workflow: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    job_name = next(iter(policy.get("jobs", {"validate": {}})), "validate")
    job = jobs_for(workflow).get(job_name, {})
    return job if isinstance(job, dict) else {}


def steps_for(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps", [])
    return [step for step in steps if isinstance(step, dict)] if isinstance(steps, list) else []


def split_action_ref(uses: str) -> tuple[str, str]:
    if "@" not in uses:
        return uses, ""
    name, ref = uses.rsplit("@", 1)
    return name, ref


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


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def evaluate_workflow(
    workflow: dict[str, Any],
    policy: dict[str, Any],
    *,
    workflow_exists: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required_jobs = policy.get("jobs", {})
    job_name = next(iter(required_jobs), "validate")
    job_policy = required_jobs.get(job_name, {})
    triggers = workflow_on(workflow)
    jobs = jobs_for(workflow)
    job = validate_job(workflow, policy)
    permissions = workflow.get("permissions")
    permissions_map = permissions if isinstance(permissions, dict) else {}
    concurrency = workflow.get("concurrency", {})
    concurrency_map = concurrency if isinstance(concurrency, dict) else {}
    actions = collect_actions(workflow)
    actions_by_name = {item["action"]: item for item in actions}

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
            required_branches = list(trigger_policy.get("branches", []))
            missing = sorted(branch for branch in required_branches if branch not in branches)
            if missing:
                required_trigger_gaps.append(
                    {"trigger": trigger_name, "missing_branches": missing}
                )
    forbidden_triggers = sorted(
        trigger for trigger in policy.get("forbidden_triggers", []) if trigger in triggers
    )

    required_permissions = policy.get("required_permissions", {})
    permission_gaps = [
        {"permission": key, "expected": value, "observed": permissions_map.get(key)}
        for key, value in required_permissions.items()
        if permissions_map.get(key) != value
    ]
    permission_writes = [
        {"permission": key, "value": value}
        for key, value in permissions_map.items()
        if isinstance(value, str) and value.endswith("write")
    ]
    forbidden_permission_values = set(policy.get("forbidden_permission_values", []))
    forbidden_permission_value = (
        isinstance(permissions, str) and permissions in forbidden_permission_values
    )

    group = str(concurrency_map.get("group", ""))
    concurrency_fragments = list(policy.get("required_concurrency_group_fragments", []))
    missing_concurrency_fragments = [
        fragment for fragment in concurrency_fragments if fragment not in group
    ]
    cancel_expected = bool(policy.get("require_cancel_in_progress", False))
    cancel_observed = concurrency_map.get("cancel-in-progress")

    action_gaps = []
    hardened_action_count = 0
    forbidden_refs = set(policy.get("forbidden_action_refs", []))
    for action_name, action_policy in policy.get("required_actions", {}).items():
        action = actions_by_name.get(action_name)
        if not action:
            action_gaps.append({"action": action_name, "reason": "missing"})
            continue
        minimum_major = int(action_policy.get("minimum_major", 0))
        major = action.get("major")
        ref = str(action.get("ref", ""))
        if ref in forbidden_refs:
            action_gaps.append({"action": action_name, "ref": ref, "reason": "forbidden_ref"})
            continue
        if major is None and not action.get("sha_pinned"):
            action_gaps.append({"action": action_name, "ref": ref, "reason": "floating_ref"})
            continue
        if major is not None and major < minimum_major:
            action_gaps.append(
                {
                    "action": action_name,
                    "ref": ref,
                    "minimum_major": minimum_major,
                    "observed_major": major,
                }
            )
            continue
        hardened_action_count += 1

    timeout = job.get("timeout-minutes")
    max_timeout = int(job_policy.get("timeout_minutes_max", 0))
    timeout_ok = isinstance(timeout, int) and 0 < timeout <= max_timeout
    runs_on_ok = job.get("runs-on") == job_policy.get("runs_on")
    continue_on_error = bool(job.get("continue-on-error")) or any(
        bool(step.get("continue-on-error")) for step in steps_for(job)
    )

    python_version = None
    validation_command_found = False
    validation_command = job_policy.get("validation_command")
    for step in steps_for(job):
        if str(step.get("uses", "")).startswith("actions/setup-python@"):
            setup = step.get("with", {})
            if isinstance(setup, dict):
                python_version = setup.get("python-version")
        if step.get("run") == validation_command:
            validation_command_found = True
    serialized_job = json.dumps(job, sort_keys=True)
    secrets_referenced = "secrets." in serialized_job

    checks = [
        check(
            "workflow_inventory",
            workflow_exists
            and workflow.get("name") == policy.get("required_workflow_name")
            and job_name in jobs,
            {
                "workflow_exists": workflow_exists,
                "workflow_name": workflow.get("name"),
                "required_job": job_name,
                "job_names": sorted(jobs),
            },
        ),
        check(
            "trigger_surface",
            not required_trigger_gaps and not forbidden_triggers,
            {
                "triggers": sorted(triggers),
                "required_trigger_gaps": required_trigger_gaps,
                "forbidden_triggers": forbidden_triggers,
            },
        ),
        check(
            "least_privilege_permissions",
            isinstance(permissions, dict)
            and not permission_gaps
            and not permission_writes
            and not forbidden_permission_value,
            {
                "permissions": permissions,
                "required_permissions": required_permissions,
                "permission_gaps": permission_gaps,
                "write_permissions": permission_writes,
            },
        ),
        check(
            "concurrency_cancellation",
            isinstance(concurrency, dict)
            and not missing_concurrency_fragments
            and (cancel_observed is True if cancel_expected else True),
            {
                "concurrency": concurrency,
                "missing_group_fragments": missing_concurrency_fragments,
                "cancel_in_progress": cancel_observed,
            },
        ),
        check(
            "action_runtime_hygiene",
            not action_gaps,
            {
                "actions": actions,
                "required_actions": policy.get("required_actions", {}),
                "action_gaps": action_gaps,
            },
        ),
        check(
            "job_execution_bounds",
            bool(job) and runs_on_ok and timeout_ok and not continue_on_error,
            {
                "runs_on": job.get("runs-on"),
                "expected_runs_on": job_policy.get("runs_on"),
                "timeout_minutes": timeout,
                "timeout_minutes_max": max_timeout,
                "continue_on_error": continue_on_error,
            },
        ),
        check(
            "validation_contract",
            python_version == job_policy.get("python_version")
            and validation_command_found
            and not secrets_referenced,
            {
                "python_version": python_version,
                "expected_python_version": job_policy.get("python_version"),
                "validation_command": validation_command,
                "validation_command_found": validation_command_found,
                "secrets_referenced": secrets_referenced,
            },
        ),
    ]
    metrics = {
        "workflow_count": 1 if workflow_exists else 0,
        "job_count": len(jobs),
        "action_count": len(actions),
        "hardened_action_count": hardened_action_count,
        "permission_count": len(permissions_map),
    }
    return checks, metrics


def apply_fixture(workflow: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(workflow)
    mutation = fixture.get("mutation")
    if mutation == "remove_permissions":
        mutated.pop("permissions", None)
    elif mutation == "set_permissions_write_all":
        mutated["permissions"] = "write-all"
    elif mutation == "set_action_ref":
        action_name = fixture.get("action")
        new_ref = fixture.get("ref")
        for job in jobs_for(mutated).values():
            if not isinstance(job, dict):
                continue
            for step in steps_for(job):
                uses = step.get("uses")
                if isinstance(uses, str) and uses.startswith(f"{action_name}@"):
                    step["uses"] = f"{action_name}@{new_ref}"
    elif mutation == "remove_concurrency":
        mutated.pop("concurrency", None)
    elif mutation == "remove_job_timeout":
        job_name = fixture.get("job", "validate")
        job = jobs_for(mutated).get(job_name, {})
        if isinstance(job, dict):
            job.pop("timeout-minutes", None)
    elif mutation == "set_run_command":
        job_name = fixture.get("job", "validate")
        job = jobs_for(mutated).get(job_name, {})
        if isinstance(job, dict):
            for step in steps_for(job):
                if step.get("run") == fixture.get("from"):
                    step["run"] = fixture.get("to")
    elif mutation == "add_trigger":
        triggers = workflow_on(mutated)
        triggers[str(fixture.get("trigger"))] = {}
    return mutated


def evaluate_fixtures(workflow: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(workflow, fixture)
        checks, _ = evaluate_workflow(mutated, policy, workflow_exists=True)
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
    workflow_path = repo_root / str(policy["workflow_path"])
    workflow_exists = workflow_path.exists()
    workflow = load_workflow(workflow_path) if workflow_exists else {}
    checks, metrics = evaluate_workflow(workflow, policy, workflow_exists=workflow_exists)
    fixtures = evaluate_fixtures(workflow, policy) if workflow_exists else []
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
        "workflow_path": str(policy["workflow_path"]),
        "workflow_name": workflow.get("name"),
        "workflow_count": metrics["workflow_count"],
        "job_count": metrics["job_count"],
        "action_count": metrics["action_count"],
        "hardened_action_count": metrics["hardened_action_count"],
        "permission_count": metrics["permission_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "checks": checks,
        "fixtures": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    # Audit evidence stores workflow control booleans and fixture names, not runtime secret values.
    # codeql[py/clear-text-storage-sensitive-data]
    (output_dir / "ci-governance-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# CI Governance Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks the GitHub Actions workflow before treating CI as",
        "release-readiness evidence. It requires least-privilege repository",
        "permissions, bounded execution, concurrency cancellation, maintained",
        "Node-runtime action versions, and a stable validation command.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Workflows | {report['workflow_count']} |",
        f"| Jobs | {report['job_count']} |",
        f"| Actions | {report['action_count']} |",
        f"| Hardened actions | {report['hardened_action_count']} |",
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
    # Audit evidence stores workflow control booleans and fixture names, not runtime secret values.
    # codeql[py/clear-text-storage-sensitive-data]
    (output_dir / "ci-governance-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/ci-governance-policy.json")
    parser.add_argument("--output-dir", default="out/ci-governance-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'ci-governance-audit.json'}")
    print(f"wrote {output_dir / 'ci-governance-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
