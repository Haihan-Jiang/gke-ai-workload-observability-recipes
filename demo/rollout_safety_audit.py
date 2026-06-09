#!/usr/bin/env python3
"""Audit Kubernetes Deployment rollout safety controls."""

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


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("ruby is required to parse Kubernetes YAML manifests for the audit")
    script = "require 'yaml'; require 'json'; puts JSON.generate(YAML.load_stream(STDIN.read))"
    result = subprocess.run(
        [ruby, "-e", script],
        input=path.read_text(encoding="utf-8"),
        text=True,
        check=True,
        capture_output=True,
    )
    docs = json.loads(result.stdout)
    return [doc for doc in docs if isinstance(doc, dict)]


def load_manifest_set(paths: list[Path]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in paths:
        docs.extend(load_yaml_documents(path))
    return docs


def metadata(doc: dict[str, Any]) -> dict[str, Any]:
    value = doc.get("metadata", {})
    return value if isinstance(value, dict) else {}


def namespace(doc: dict[str, Any]) -> str:
    return str(metadata(doc).get("namespace", "default"))


def name(doc: dict[str, Any]) -> str:
    return str(metadata(doc).get("name", ""))


def index_documents(docs: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {(str(doc.get("kind", "")), namespace(doc), name(doc)): doc for doc in docs}


def check(name: str, ok: bool, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": PASS if ok else FAIL, "reason": reason, "evidence": evidence}


def workload_key(workload: dict[str, Any]) -> str:
    return f"{workload['namespace']}/{workload['name']}"


def pod_spec(workload_doc: dict[str, Any]) -> dict[str, Any]:
    return workload_doc.get("spec", {}).get("template", {}).get("spec", {})


def deployment_strategy(workload_doc: dict[str, Any]) -> dict[str, Any]:
    value = workload_doc.get("spec", {}).get("strategy", {})
    return value if isinstance(value, dict) else {}


def rolling_update(workload_doc: dict[str, Any]) -> dict[str, Any]:
    value = deployment_strategy(workload_doc).get("rollingUpdate", {})
    return value if isinstance(value, dict) else {}


def int_or_percent_matches(observed: Any, expected: Any) -> bool:
    return str(observed) == str(expected)


def mounted_pvc(workload_doc: dict[str, Any], claim_name: str) -> bool:
    for volume in pod_spec(workload_doc).get("volumes", []):
        claim = volume.get("persistentVolumeClaim", {}) if isinstance(volume, dict) else {}
        if claim.get("claimName") == claim_name:
            return True
    return False


def pdb_min_available(pdb: dict[str, Any]) -> int | None:
    value = pdb.get("spec", {}).get("minAvailable")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def deployment_replicas(workload_doc: dict[str, Any]) -> int:
    return int(workload_doc.get("spec", {}).get("replicas", 1))


def rolling_update_gaps(workload: dict[str, Any], workload_doc: dict[str, Any]) -> list[dict[str, Any]]:
    if workload.get("mode") != "rolling_ha":
        return []
    strategy = deployment_strategy(workload_doc)
    if strategy.get("type") != "RollingUpdate":
        return [{"workload": workload_key(workload), "reason": "strategy_not_rolling_update", "strategy": strategy}]
    rolling = rolling_update(workload_doc)
    gaps = []
    if not int_or_percent_matches(rolling.get("maxUnavailable"), workload["max_unavailable"]):
        gaps.append(
            {
                "workload": workload_key(workload),
                "reason": "max_unavailable_mismatch",
                "observed": rolling.get("maxUnavailable"),
                "expected": workload["max_unavailable"],
            }
        )
    if not int_or_percent_matches(rolling.get("maxSurge"), workload["max_surge"]):
        gaps.append(
            {
                "workload": workload_key(workload),
                "reason": "max_surge_mismatch",
                "observed": rolling.get("maxSurge"),
                "expected": workload["max_surge"],
            }
        )
    return gaps


def singleton_gaps(workload: dict[str, Any], workload_doc: dict[str, Any]) -> list[dict[str, Any]]:
    if workload.get("mode") != "singleton_recreate":
        return []
    gaps = []
    strategy = deployment_strategy(workload_doc)
    if strategy.get("type") != "Recreate":
        gaps.append({"workload": workload_key(workload), "reason": "singleton_must_use_recreate", "strategy": strategy})
    if workload.get("requires_pvc_queue") and not mounted_pvc(workload_doc, workload["pvc"]):
        gaps.append({"workload": workload_key(workload), "reason": "missing_queue_pvc", "pvc": workload["pvc"]})
    return gaps


def timing_gaps(workload: dict[str, Any], workload_doc: dict[str, Any]) -> list[dict[str, Any]]:
    spec = workload_doc.get("spec", {})
    gaps = []
    min_ready = int(spec.get("minReadySeconds", 0))
    progress_deadline = int(spec.get("progressDeadlineSeconds", 0))
    if min_ready < int(workload["min_ready_seconds"]):
        gaps.append(
            {
                "workload": workload_key(workload),
                "field": "minReadySeconds",
                "observed": min_ready,
                "minimum": workload["min_ready_seconds"],
            }
        )
    if progress_deadline < int(workload["min_progress_deadline_seconds"]):
        gaps.append(
            {
                "workload": workload_key(workload),
                "field": "progressDeadlineSeconds",
                "observed": progress_deadline,
                "minimum": workload["min_progress_deadline_seconds"],
            }
        )
    return gaps


def termination_gaps(workload: dict[str, Any], workload_doc: dict[str, Any]) -> list[dict[str, Any]]:
    observed = pod_spec(workload_doc).get("terminationGracePeriodSeconds")
    if not isinstance(observed, int) or observed < int(workload["min_termination_grace_seconds"]):
        return [
            {
                "workload": workload_key(workload),
                "observed": observed,
                "minimum": workload["min_termination_grace_seconds"],
            }
        ]
    return []


def pdb_alignment_gaps(workload: dict[str, Any], workload_doc: dict[str, Any], pdb: dict[str, Any]) -> list[dict[str, Any]]:
    if not pdb:
        return [{"workload": workload_key(workload), "reason": "missing_pdb"}]
    replicas = deployment_replicas(workload_doc)
    min_available = pdb_min_available(pdb)
    if workload.get("mode") == "rolling_ha" and not (min_available is not None and 0 < min_available < replicas):
        return [{"workload": workload_key(workload), "reason": "rolling_pdb_must_allow_surge", "min_available": min_available}]
    if workload.get("mode") == "singleton_recreate" and min_available != replicas:
        return [{"workload": workload_key(workload), "reason": "singleton_pdb_must_guard_current_pod", "min_available": min_available}]
    return []


def label_gaps(workload: dict[str, Any], workload_doc: dict[str, Any], pdb: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    for kind, doc in ((workload.get("kind", "Deployment"), workload_doc), ("PodDisruptionBudget", pdb)):
        labels = metadata(doc).get("labels", {}) if doc else {}
        missing = [label for label in policy.get("required_labels", []) if label not in labels]
        if missing:
            gaps.append({"workload": workload_key(workload), "kind": kind, "missing": missing})
    return gaps


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    index = index_documents(docs)
    rolling_strategy_gaps = []
    rolling_availability_gaps = []
    singleton_strategy_gaps = []
    singleton_queue_gaps = []
    rollout_timing_gaps = []
    termination_window_gaps = []
    pdb_gaps = []
    labels_missing = []
    summaries = []

    for workload in policy.get("workloads", []):
        workload_doc = index.get((workload.get("kind", "Deployment"), workload["namespace"], workload["name"]), {})
        pdb = index.get(("PodDisruptionBudget", workload["namespace"], workload["pdb"]), {})
        rolling_gaps = rolling_update_gaps(workload, workload_doc)
        if rolling_gaps and any(item["reason"] == "strategy_not_rolling_update" for item in rolling_gaps):
            rolling_strategy_gaps.extend(rolling_gaps)
        else:
            rolling_availability_gaps.extend(rolling_gaps)
        for gap in singleton_gaps(workload, workload_doc):
            if gap["reason"] == "missing_queue_pvc":
                singleton_queue_gaps.append(gap)
            else:
                singleton_strategy_gaps.append(gap)
        timing = timing_gaps(workload, workload_doc)
        termination = termination_gaps(workload, workload_doc)
        rollout_timing_gaps.extend(timing)
        termination_window_gaps.extend(termination)
        pdb_gaps.extend(pdb_alignment_gaps(workload, workload_doc, pdb))
        labels_missing.extend(label_gaps(workload, workload_doc, pdb, policy))
        summaries.append(
            {
                "workload": workload_key(workload),
                "mode": workload["mode"],
                "strategy": deployment_strategy(workload_doc).get("type"),
                "timing_guarded": not timing,
                "termination_window_guarded": not termination,
                "min_ready_seconds": workload_doc.get("spec", {}).get("minReadySeconds"),
                "progress_deadline_seconds": workload_doc.get("spec", {}).get("progressDeadlineSeconds"),
                "termination_grace_seconds": pod_spec(workload_doc).get("terminationGracePeriodSeconds"),
            }
        )

    checks = [
        check(
            "rolling_update_strategy",
            not rolling_strategy_gaps,
            "HA inference workloads use RollingUpdate instead of disruptive replacement.",
            {"gaps": rolling_strategy_gaps},
        ),
        check(
            "rolling_update_availability",
            not rolling_availability_gaps,
            "HA inference rollouts keep maxUnavailable at zero and reserve surge capacity.",
            {"gaps": rolling_availability_gaps},
        ),
        check(
            "singleton_recreate_strategy",
            not singleton_strategy_gaps,
            "Singleton collector rollouts use Recreate to avoid RWO queue PVC multi-attach drift.",
            {"gaps": singleton_strategy_gaps},
        ),
        check(
            "singleton_queue_alignment",
            not singleton_queue_gaps,
            "Singleton collector rollout policy remains aligned with PVC-backed durable queue storage.",
            {"gaps": singleton_queue_gaps},
        ),
        check(
            "rollout_timing",
            not rollout_timing_gaps,
            "Deployments define minReadySeconds and progressDeadlineSeconds so rollout failures are observable.",
            {"gaps": rollout_timing_gaps},
        ),
        check(
            "termination_drain_window",
            not termination_window_gaps,
            "Pods define enough termination grace for request drain and collector export shutdown.",
            {"gaps": termination_window_gaps},
        ),
        check(
            "pdb_rollout_alignment",
            not pdb_gaps,
            "PDBs remain compatible with each workload rollout mode.",
            {"gaps": pdb_gaps},
        ),
        check(
            "rollout_label_governance",
            not labels_missing,
            "Rollout-relevant manifests carry owner labels used by review and policy tooling.",
            {"gaps": labels_missing},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "workload_count": len(policy.get("workloads", [])),
        "rolling_update_count": sum(1 for item in summaries if item["strategy"] == "RollingUpdate"),
        "recreate_count": sum(1 for item in summaries if item["strategy"] == "Recreate"),
        "timing_guard_count": sum(1 for item in summaries if item["timing_guarded"]),
        "termination_window_count": sum(1 for item in summaries if item["termination_window_guarded"]),
        "check_count": len(checks),
        "failed_count": len(failed),
        "workloads": summaries,
        "checks": checks,
    }


def find_doc(docs: list[dict[str, Any]], kind: str, doc_namespace: str, doc_name: str) -> dict[str, Any]:
    for doc in docs:
        if doc.get("kind") == kind and namespace(doc) == doc_namespace and name(doc) == doc_name:
            return doc
    raise ValueError(f"missing {kind}/{doc_namespace}/{doc_name}")


def find_workload(policy: dict[str, Any], workload_name: str) -> dict[str, Any]:
    for workload in policy.get("workloads", []):
        if workload["name"] == workload_name:
            return workload
    raise ValueError(f"missing workload policy: {workload_name}")


def pod_volumes(workload_doc: dict[str, Any]) -> list[dict[str, Any]]:
    volumes = pod_spec(workload_doc).setdefault("volumes", [])
    return [item for item in volumes if isinstance(item, dict)]


def mutate_fixture(docs: list[dict[str, Any]], policy: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    workload = find_workload(policy, str(fixture["workload"]))
    workload_doc = find_doc(mutated, workload.get("kind", "Deployment"), workload["namespace"], workload["name"])
    mutation = fixture["mutation"]
    if mutation == "set_strategy_type":
        strategy = workload_doc.setdefault("spec", {}).setdefault("strategy", {})
        strategy["type"] = str(fixture["strategy"])
        if strategy["type"] == "Recreate":
            strategy.pop("rollingUpdate", None)
    elif mutation == "set_rolling_value":
        workload_doc.setdefault("spec", {}).setdefault("strategy", {}).setdefault("rollingUpdate", {})[
            str(fixture["field"])
        ] = fixture["value"]
    elif mutation == "remove_rolling_value":
        workload_doc.setdefault("spec", {}).setdefault("strategy", {}).setdefault("rollingUpdate", {}).pop(
            str(fixture["field"]),
            None,
        )
    elif mutation == "set_deployment_field":
        workload_doc.setdefault("spec", {})[str(fixture["field"])] = fixture["value"]
    elif mutation == "remove_pod_spec_field":
        pod_spec(workload_doc).pop(str(fixture["field"]), None)
    elif mutation == "set_pod_spec_field":
        pod_spec(workload_doc)[str(fixture["field"])] = fixture["value"]
    elif mutation == "set_pdb_field":
        pdb = find_doc(mutated, "PodDisruptionBudget", workload["namespace"], workload["pdb"])
        pdb.setdefault("spec", {})[str(fixture["field"])] = fixture["value"]
    elif mutation == "remove_pvc_volume":
        claim_name = str(fixture["pvc"])
        pod_spec(workload_doc)["volumes"] = [
            item for item in pod_volumes(workload_doc) if item.get("persistentVolumeClaim", {}).get("claimName") != claim_name
        ]
    elif mutation == "remove_owner_label":
        kind = str(fixture["kind"])
        target = workload_doc if kind == workload.get("kind", "Deployment") else find_doc(
            mutated,
            kind,
            workload["namespace"],
            workload["pdb"],
        )
        metadata(target).setdefault("labels", {}).pop(str(fixture["label"]), None)
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(docs: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = mutate_fixture(docs, policy, fixture)
        report = evaluate_documents(mutated, policy)
        expected_failed_check = fixture["expected_failed_check"]
        failed_checks = [item["name"] for item in report["checks"] if item["status"] != PASS]
        results.append(
            {
                "name": fixture["name"],
                "mutation": fixture["mutation"],
                "expected_failed_check": expected_failed_check,
                "failed_checks": failed_checks,
                "detected": expected_failed_check in failed_checks,
            }
        )
    return results


def build_report(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    audit = evaluate_documents(docs, policy)
    fixture_results = evaluate_fixtures(docs, policy)
    detected_fixture_count = sum(1 for item in fixture_results if item["detected"])
    undetected = [item["name"] for item in fixture_results if not item["detected"]]
    negative_fixture_check = check(
        "negative_fixture_coverage",
        not undetected and detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
        "Negative fixtures prove rollout strategy, timing, termination, PDB, and label drift is detected.",
        {"fixture_count": len(fixture_results), "detected_fixture_count": detected_fixture_count, "undetected": undetected},
    )
    checks = audit["checks"] + [negative_fixture_check]
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "workload_count": audit["workload_count"],
        "rolling_update_count": audit["rolling_update_count"],
        "recreate_count": audit["recreate_count"],
        "timing_guard_count": audit["timing_guard_count"],
        "termination_window_count": audit["termination_window_count"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "workloads": audit["workloads"],
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rollout-safety-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Rollout Safety Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks Deployment rollout strategy, availability windows,",
        "termination drain settings, PDB alignment, and singleton collector",
        "queue-PVC rollout behavior before the manifests are treated as",
        "release evidence.",
        "",
        "## Summary",
        "",
        f"- Workloads: `{report['workload_count']}`",
        f"- RollingUpdate workloads: `{report['rolling_update_count']}`",
        f"- Recreate workloads: `{report['recreate_count']}`",
        f"- Rollout timing guards: `{report['timing_guard_count']}`",
        f"- Termination windows: `{report['termination_window_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Workloads",
        "",
        "| Workload | Mode | Strategy | Min ready | Progress deadline | Termination grace |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for item in report["workloads"]:
        lines.append(
            "| `{workload}` | `{mode}` | `{strategy}` | {min_ready} | {deadline} | {termination} |".format(
                workload=item["workload"],
                mode=item["mode"],
                strategy=item["strategy"],
                min_ready=item["min_ready_seconds"],
                deadline=item["progress_deadline_seconds"],
                termination=item["termination_grace_seconds"],
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['status'] == PASS else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Detected |", "| --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(f"| `{item['name']}` | {'yes' if item['detected'] else 'no'} |")
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rollout-safety-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/rollout-safety-policy.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    policy = load_json(Path(args.policy))
    docs = load_manifest_set([repo_root / path for path in policy.get("target_manifests", [])])
    report = build_report(docs, policy)
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'rollout-safety-audit.json'}")
    print(f"wrote {output_dir / 'rollout-safety-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
