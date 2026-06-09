#!/usr/bin/env python3
"""Audit dependency update governance for release evidence."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("ruby is required to parse Dependabot YAML")
    script = "require 'yaml'; require 'json'; puts JSON.generate(YAML.load_file(ARGV[0]))"
    result = subprocess.run(
        [ruby, "-e", script, str(path)],
        text=True,
        check=True,
        capture_output=True,
    )
    loaded = json.loads(result.stdout)
    return loaded if isinstance(loaded, dict) else {}


def read_docs(repo_root: Path, paths: list[str]) -> dict[str, str]:
    return {
        path: (repo_root / path).read_text(encoding="utf-8")
        for path in paths
        if (repo_root / path).is_file()
    }


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def updates_for(config: dict[str, Any]) -> list[dict[str, Any]]:
    updates = config.get("updates", [])
    return [item for item in updates if isinstance(item, dict)] if isinstance(updates, list) else []


def update_key(update: dict[str, Any]) -> tuple[str, str]:
    return (
        str(update.get("package-ecosystem", "")),
        str(update.get("directory", "")),
    )


def schedule_interval(update: dict[str, Any]) -> str:
    schedule = update.get("schedule", {})
    if not isinstance(schedule, dict):
        return ""
    return str(schedule.get("interval", ""))


def labels_for(update: dict[str, Any]) -> list[str]:
    labels = update.get("labels", [])
    return [str(item) for item in labels] if isinstance(labels, list) else []


def commit_prefix(update: dict[str, Any]) -> str:
    commit_message = update.get("commit-message", {})
    if not isinstance(commit_message, dict):
        return ""
    return str(commit_message.get("prefix", ""))


def evaluate_inputs(
    *,
    config_exists: bool,
    config: dict[str, Any],
    docs: dict[str, str],
    release_source: str,
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    updates = updates_for(config)
    update_map = {update_key(item): item for item in updates}
    required = list(policy.get("required_ecosystems", []))
    required_keys = [
        (str(item["package_ecosystem"]), str(item["directory"]))
        for item in required
    ]
    missing_required = [
        {"package_ecosystem": ecosystem, "directory": directory}
        for ecosystem, directory in required_keys
        if (ecosystem, directory) not in update_map
    ]
    allowed_intervals = set(policy.get("allowed_schedule_intervals", []))
    schedule_gaps = []
    weekly_schedule_count = 0
    for ecosystem, directory in required_keys:
        update = update_map.get((ecosystem, directory))
        if not update:
            continue
        interval = schedule_interval(update)
        if interval == "weekly":
            weekly_schedule_count += 1
        expected = next(
            item for item in required
            if str(item["package_ecosystem"]) == ecosystem and str(item["directory"]) == directory
        )
        if interval != str(expected.get("schedule_interval", "")) or interval not in allowed_intervals:
            schedule_gaps.append(
                {
                    "package_ecosystem": ecosystem,
                    "directory": directory,
                    "observed_interval": interval,
                    "expected_interval": expected.get("schedule_interval"),
                }
            )

    label_gaps = []
    pr_limit_gaps = []
    prefix_gaps = []
    required_labels = set(policy.get("required_labels", []))
    max_open_prs = int(policy.get("maximum_open_pull_requests", 0))
    expected_prefix = str(policy.get("required_commit_prefix", ""))
    label_count = 0
    for update in updates:
        labels = labels_for(update)
        label_count += len(set(labels))
        missing_labels = sorted(required_labels.difference(labels))
        if missing_labels:
            label_gaps.append({"update": update_key(update), "missing_labels": missing_labels})
        limit = update.get("open-pull-requests-limit")
        if not isinstance(limit, int) or limit <= 0 or limit > max_open_prs:
            pr_limit_gaps.append({"update": update_key(update), "observed_limit": limit})
        prefix = commit_prefix(update)
        if prefix != expected_prefix:
            prefix_gaps.append({"update": update_key(update), "observed_prefix": prefix})

    combined_docs = "\n".join(docs.values())
    required_terms = list(policy.get("required_validation_terms", []))
    missing_validation_terms = [term for term in required_terms if term not in combined_docs]
    validation_term_count = len(required_terms) - len(missing_validation_terms)

    required_controls = list(policy.get("required_release_controls", []))
    missing_release_controls = [control for control in required_controls if control not in release_source]
    release_control_count = len(required_controls) - len(missing_release_controls)

    ecosystem_count = len({item["package-ecosystem"] for item in updates if "package-ecosystem" in item})
    metrics = {
        "config_file_count": 1 if config_exists else 0,
        "update_count": len(updates),
        "ecosystem_count": ecosystem_count,
        "weekly_schedule_count": weekly_schedule_count,
        "label_count": label_count,
        "validation_term_count": validation_term_count,
        "release_control_count": release_control_count,
    }
    checks = [
        check(
            "config_file_contract",
            config_exists and int(config.get("version", 0)) == 2,
            {"config_exists": config_exists, "version": config.get("version")},
        ),
        check(
            "ecosystem_contract",
            not missing_required
            and len(updates) >= int(policy.get("minimum_update_count", 0))
            and ecosystem_count >= int(policy.get("minimum_ecosystem_count", 0)),
            {
                "update_count": len(updates),
                "ecosystem_count": ecosystem_count,
                "missing_required": missing_required,
            },
        ),
        check(
            "schedule_contract",
            not schedule_gaps
            and weekly_schedule_count >= int(policy.get("minimum_weekly_schedule_count", 0)),
            {"weekly_schedule_count": weekly_schedule_count, "schedule_gaps": schedule_gaps},
        ),
        check(
            "review_boundary_contract",
            not label_gaps and not pr_limit_gaps and not prefix_gaps,
            {
                "label_gaps": label_gaps,
                "pr_limit_gaps": pr_limit_gaps,
                "prefix_gaps": prefix_gaps,
                "maximum_open_pull_requests": max_open_prs,
            },
        ),
        check(
            "validation_linkage",
            validation_term_count >= int(policy.get("minimum_validation_term_count", 0)),
            {
                "validation_term_count": validation_term_count,
                "minimum_validation_term_count": policy.get("minimum_validation_term_count"),
                "missing_terms": missing_validation_terms,
            },
        ),
        check(
            "release_control_linkage",
            release_control_count >= int(policy.get("minimum_release_control_count", 0)),
            {
                "release_control_count": release_control_count,
                "minimum_release_control_count": policy.get("minimum_release_control_count"),
                "missing_release_controls": missing_release_controls,
            },
        ),
    ]
    return checks, metrics


def apply_fixture(
    *,
    config_exists: bool,
    config: dict[str, Any],
    docs: dict[str, str],
    release_source: str,
    fixture: dict[str, Any],
) -> tuple[bool, dict[str, Any], dict[str, str], str]:
    mutated_exists = config_exists
    mutated_config = copy.deepcopy(config)
    mutated_docs = copy.deepcopy(docs)
    mutated_release_source = release_source
    mutation = fixture["mutation"]
    if mutation == "remove_config":
        mutated_exists = False
        mutated_config = {}
    elif mutation == "remove_update":
        ecosystem = fixture["ecosystem"]
        mutated_config["updates"] = [
            update
            for update in updates_for(mutated_config)
            if update.get("package-ecosystem") != ecosystem
        ]
    elif mutation == "set_schedule_interval":
        ecosystem = fixture["ecosystem"]
        for update in updates_for(mutated_config):
            if update.get("package-ecosystem") == ecosystem:
                update.setdefault("schedule", {})["interval"] = fixture["value"]
    elif mutation == "set_open_pull_requests_limit":
        ecosystem = fixture["ecosystem"]
        for update in updates_for(mutated_config):
            if update.get("package-ecosystem") == ecosystem:
                update["open-pull-requests-limit"] = fixture["value"]
    elif mutation == "remove_label":
        ecosystem = fixture["ecosystem"]
        label = fixture["label"]
        for update in updates_for(mutated_config):
            if update.get("package-ecosystem") == ecosystem:
                update["labels"] = [item for item in labels_for(update) if item != label]
    elif mutation == "remove_documentation_term":
        term = fixture["term"]
        mutated_docs = {path: text.replace(term, "") for path, text in mutated_docs.items()}
    elif mutation == "remove_release_control":
        mutated_release_source = mutated_release_source.replace(str(fixture["control"]), "")
    else:
        raise ValueError(f"unknown fixture mutation: {mutation}")
    return mutated_exists, mutated_config, mutated_docs, mutated_release_source


def evaluate_fixtures(
    *,
    config_exists: bool,
    config: dict[str, Any],
    docs: dict[str, str],
    release_source: str,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_exists, mutated_config, mutated_docs, mutated_release_source = apply_fixture(
            config_exists=config_exists,
            config=config,
            docs=docs,
            release_source=release_source,
            fixture=fixture,
        )
        checks, _ = evaluate_inputs(
            config_exists=mutated_exists,
            config=mutated_config,
            docs=mutated_docs,
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
    config_path = repo_root / str(policy["config_path"])
    config_exists = config_path.is_file()
    config = load_yaml(config_path) if config_exists else {}
    docs = read_docs(repo_root, list(policy.get("documentation_paths", [])))
    release_source = (repo_root / release_readiness_source).read_text(encoding="utf-8")
    checks, metrics = evaluate_inputs(
        config_exists=config_exists,
        config=config,
        docs=docs,
        release_source=release_source,
        policy=policy,
    )
    fixtures = evaluate_fixtures(
        config_exists=config_exists,
        config=config,
        docs=docs,
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
        **metrics,
        "updates": updates_for(config),
        "checks": checks,
        "fixtures": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "dependency-update-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Dependency Update Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that dependency update automation, review limits,",
        "validation documentation, and release-control linkage stay in sync",
        "before dependency-maintenance claims are trusted.",
        "",
        "## Summary",
        "",
        f"- Updates configured: `{report['update_count']}`",
        f"- Ecosystems covered: `{report['ecosystem_count']}`",
        f"- Weekly schedules: `{report['weekly_schedule_count']}`",
        f"- Labels configured: `{report['label_count']}`",
        f"- Validation terms: `{report['validation_term_count']}`",
        f"- Release controls linked: `{report['release_control_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Updates",
        "",
        "| Ecosystem | Directory | Interval | Open PR limit |",
        "| --- | --- | --- | ---: |",
    ]
    for update in report["updates"]:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` |".format(
                update.get("package-ecosystem", ""),
                update.get("directory", ""),
                schedule_interval(update),
                update.get("open-pull-requests-limit", ""),
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    (output_dir / "dependency-update-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/dependency-update-policy.json")
    parser.add_argument("--release-readiness-source", default="demo/release_readiness.py")
    parser.add_argument("--output-dir", default="out/dependency-update-audit")
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
