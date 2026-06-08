#!/usr/bin/env python3
"""Audit Kubernetes scheduling placement intent for AI inference workloads."""

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


def preferred_expressions(workload_doc: dict[str, Any]) -> list[dict[str, Any]]:
    affinity = pod_spec(workload_doc).get("affinity", {})
    preferred = affinity.get("nodeAffinity", {}).get("preferredDuringSchedulingIgnoredDuringExecution", [])
    expressions: list[dict[str, Any]] = []
    if not isinstance(preferred, list):
        return expressions
    for item in preferred:
        preference = item.get("preference", {}) if isinstance(item, dict) else {}
        for expression in preference.get("matchExpressions", []):
            if isinstance(expression, dict):
                expressions.append(expression)
    return expressions


def has_preferred_expression(workload_doc: dict[str, Any], expected: dict[str, Any]) -> bool:
    expected_values = set(str(item) for item in expected.get("values", []))
    for expression in preferred_expressions(workload_doc):
        if expression.get("key") != expected.get("key") or expression.get("operator") != "In":
            continue
        values = set(str(item) for item in expression.get("values", []))
        if expected_values.issubset(values):
            return True
    return False


def toleration_matches(observed: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(observed.get(key) == value for key, value in expected.items())


def has_toleration(workload_doc: dict[str, Any], expected: dict[str, Any]) -> bool:
    tolerations = pod_spec(workload_doc).get("tolerations", [])
    return any(isinstance(item, dict) and toleration_matches(item, expected) for item in tolerations)


def priority_class_ok(doc: dict[str, Any], workload: dict[str, Any]) -> dict[str, Any] | None:
    if not doc:
        return {"priority_class": workload["priority_class"], "reason": "missing"}
    value = int(doc.get("value", 0))
    if value < int(workload["minimum_priority_value"]):
        return {
            "priority_class": workload["priority_class"],
            "reason": "priority_value_too_low",
            "value": value,
            "minimum": workload["minimum_priority_value"],
        }
    if doc.get("preemptionPolicy") != "Never":
        return {
            "priority_class": workload["priority_class"],
            "reason": "preemption_must_be_never",
            "preemption_policy": doc.get("preemptionPolicy"),
        }
    if doc.get("globalDefault") is not False:
        return {
            "priority_class": workload["priority_class"],
            "reason": "must_not_be_global_default",
            "global_default": doc.get("globalDefault"),
        }
    return None


def portable_scheduling_gap(workload: dict[str, Any], workload_doc: dict[str, Any]) -> dict[str, Any] | None:
    spec = pod_spec(workload_doc)
    node_affinity = spec.get("affinity", {}).get("nodeAffinity", {})
    if spec.get("nodeSelector"):
        return {"workload": workload_key(workload), "reason": "hard_node_selector", "node_selector": spec.get("nodeSelector")}
    if node_affinity.get("requiredDuringSchedulingIgnoredDuringExecution"):
        return {"workload": workload_key(workload), "reason": "hard_node_affinity"}
    return None


def toleration_gaps(workload: dict[str, Any], workload_doc: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    tolerations = [item for item in pod_spec(workload_doc).get("tolerations", []) if isinstance(item, dict)]
    allowed_effects = set(policy.get("allowed_toleration_effects", []))
    for expected in workload.get("required_tolerations", []):
        if not has_toleration(workload_doc, expected):
            gaps.append({"workload": workload_key(workload), "reason": "missing_required_toleration", "expected": expected})
    for item in tolerations:
        if item.get("operator") != "Equal":
            gaps.append({"workload": workload_key(workload), "reason": "wildcard_toleration", "toleration": item})
        if item.get("effect") not in allowed_effects:
            gaps.append({"workload": workload_key(workload), "reason": "unexpected_effect", "toleration": item})
    return gaps


def label_gaps(workload: dict[str, Any], workload_doc: dict[str, Any], priority_class: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    for kind, doc in ((workload.get("kind", "Deployment"), workload_doc), ("PriorityClass", priority_class)):
        labels = metadata(doc).get("labels", {}) if doc else {}
        missing = [label for label in policy.get("required_labels", []) if label not in labels]
        if missing:
            gaps.append({"workload": workload_key(workload), "kind": kind, "missing": missing})
    return gaps


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    index = index_documents(docs)
    workloads = list(policy.get("workloads", []))
    priority_gaps = []
    binding_gaps = []
    affinity_gaps = []
    portability_gaps = []
    toleration_gaps_found = []
    labels_missing = []
    summaries = []

    for workload in workloads:
        workload_doc = index.get((workload.get("kind", "Deployment"), workload["namespace"], workload["name"]), {})
        priority_class = index.get(("PriorityClass", "default", workload["priority_class"]), {})
        priority_gap = priority_class_ok(priority_class, workload)
        if priority_gap:
            priority_gaps.append(priority_gap)
        if not workload_doc or pod_spec(workload_doc).get("priorityClassName") != workload["priority_class"]:
            binding_gaps.append(
                {
                    "workload": workload_key(workload),
                    "expected": workload["priority_class"],
                    "observed": pod_spec(workload_doc).get("priorityClassName") if workload_doc else None,
                }
            )
        missing_affinity = [
            expected for expected in workload.get("required_affinity", []) if not has_preferred_expression(workload_doc, expected)
        ]
        if missing_affinity:
            affinity_gaps.append({"workload": workload_key(workload), "missing": missing_affinity})
        portability_gap = portable_scheduling_gap(workload, workload_doc)
        if portability_gap:
            portability_gaps.append(portability_gap)
        toleration_gaps_found.extend(toleration_gaps(workload, workload_doc, policy))
        labels_missing.extend(label_gaps(workload, workload_doc, priority_class, policy))
        summaries.append(
            {
                "workload": workload_key(workload),
                "priority_class": pod_spec(workload_doc).get("priorityClassName") if workload_doc else None,
                "preferred_affinity_keys": [item.get("key") for item in preferred_expressions(workload_doc)],
                "toleration_keys": [item.get("key") for item in pod_spec(workload_doc).get("tolerations", []) if isinstance(item, dict)],
            }
        )

    checks = [
        check(
            "priority_class_definitions",
            not priority_gaps,
            "PriorityClasses exist, are non-global, use non-preempting policy, and meet minimum values.",
            {"gaps": priority_gaps},
        ),
        check(
            "workload_priority_binding",
            not binding_gaps,
            "Collector and inference Deployments bind to their expected PriorityClasses.",
            {"gaps": binding_gaps},
        ),
        check(
            "preferred_node_affinity",
            not affinity_gaps,
            "Workloads declare preferred GKE node-pool and workload-purpose placement without hard scheduling locks.",
            {"gaps": affinity_gaps},
        ),
        check(
            "portable_scheduling_preferences",
            not portability_gaps,
            "Scheduling intent uses portable soft preferences, not hard nodeSelector or required node affinity.",
            {"gaps": portability_gaps},
        ),
        check(
            "bounded_tolerations",
            not toleration_gaps_found,
            "Tolerations are explicit Equal matches with expected NoSchedule effects.",
            {"gaps": toleration_gaps_found},
        ),
        check(
            "scheduling_label_governance",
            not labels_missing,
            "Scheduling-relevant manifests carry owner labels used by review and policy tooling.",
            {"gaps": labels_missing},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "workload_count": len(workloads),
        "priority_class_count": sum(1 for doc in docs if doc.get("kind") == "PriorityClass"),
        "preferred_affinity_count": sum(len(item["preferred_affinity_keys"]) for item in summaries),
        "toleration_count": sum(len(item["toleration_keys"]) for item in summaries),
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


def remove_doc(docs: list[dict[str, Any]], kind: str, doc_namespace: str, doc_name: str) -> list[dict[str, Any]]:
    return [
        doc for doc in docs if not (doc.get("kind") == kind and namespace(doc) == doc_namespace and name(doc) == doc_name)
    ]


def find_workload(policy: dict[str, Any], workload_name: str) -> dict[str, Any]:
    for workload in policy.get("workloads", []):
        if workload["name"] == workload_name:
            return workload
    raise ValueError(f"missing workload policy: {workload_name}")


def remove_affinity_expression(workload_doc: dict[str, Any], key: str) -> None:
    preferred = (
        pod_spec(workload_doc)
        .setdefault("affinity", {})
        .setdefault("nodeAffinity", {})
        .setdefault("preferredDuringSchedulingIgnoredDuringExecution", [])
    )
    for item in preferred:
        preference = item.get("preference", {})
        preference["matchExpressions"] = [
            expression for expression in preference.get("matchExpressions", []) if expression.get("key") != key
        ]


def mutate_fixture(docs: list[dict[str, Any]], policy: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    mutation = fixture["mutation"]
    if mutation == "remove_priority_class":
        return remove_doc(mutated, "PriorityClass", "default", str(fixture["priority_class"]))
    if mutation in {"set_priority_value", "set_preemption_policy", "remove_priority_class_label"}:
        doc = find_doc(mutated, "PriorityClass", "default", str(fixture["priority_class"]))
        if mutation == "set_priority_value":
            doc["value"] = int(fixture["value"])
        elif mutation == "set_preemption_policy":
            doc["preemptionPolicy"] = str(fixture["preemption_policy"])
        else:
            metadata(doc).setdefault("labels", {}).pop(str(fixture["label"]), None)
        return mutated

    workload = find_workload(policy, str(fixture["workload"]))
    workload_doc = find_doc(mutated, workload.get("kind", "Deployment"), workload["namespace"], workload["name"])
    spec = pod_spec(workload_doc)
    if mutation == "remove_workload_priority":
        spec.pop("priorityClassName", None)
    elif mutation == "set_workload_priority":
        spec["priorityClassName"] = str(fixture["priority_class"])
    elif mutation == "remove_affinity_expression":
        remove_affinity_expression(workload_doc, str(fixture["key"]))
    elif mutation == "add_node_selector":
        spec.setdefault("nodeSelector", {})[str(fixture["key"])] = str(fixture["value"])
    elif mutation == "remove_toleration":
        spec["tolerations"] = [
            item for item in spec.get("tolerations", []) if item.get("key") != str(fixture["key"])
        ]
    elif mutation == "set_toleration_operator":
        for item in spec.get("tolerations", []):
            if item.get("key") == str(fixture["key"]):
                item["operator"] = str(fixture["operator"])
                item.pop("value", None)
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
        "Negative fixtures prove priority, affinity, toleration, and portability drift is detected.",
        {"fixture_count": len(fixture_results), "detected_fixture_count": detected_fixture_count, "undetected": undetected},
    )
    checks = audit["checks"] + [negative_fixture_check]
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "workload_count": audit["workload_count"],
        "priority_class_count": audit["priority_class_count"],
        "preferred_affinity_count": audit["preferred_affinity_count"],
        "toleration_count": audit["toleration_count"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "workloads": audit["workloads"],
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scheduling-placement-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Scheduling Placement Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that the collector and sample inference workload",
        "declare reviewable scheduling intent through non-preempting",
        "PriorityClasses, soft node affinity, and bounded tolerations without",
        "hard node selectors that would break portable local smoke tests.",
        "",
        "## Summary",
        "",
        f"- Workloads: `{report['workload_count']}`",
        f"- PriorityClasses: `{report['priority_class_count']}`",
        f"- Preferred affinity expressions: `{report['preferred_affinity_count']}`",
        f"- Tolerations: `{report['toleration_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Workloads",
        "",
        "| Workload | PriorityClass | Affinity keys | Toleration keys |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["workloads"]:
        affinity = ", ".join(f"`{key}`" for key in item["preferred_affinity_keys"]) or "-"
        tolerations = ", ".join(f"`{key}`" for key in item["toleration_keys"]) or "-"
        lines.append(f"| `{item['workload']}` | `{item['priority_class']}` | {affinity} | {tolerations} |")
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['status'] == PASS else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Detected |", "| --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(f"| `{item['name']}` | {'yes' if item['detected'] else 'no'} |")
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scheduling-placement-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/scheduling-placement-policy.json")
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
    print(f"wrote {output_dir / 'scheduling-placement-audit.json'}")
    print(f"wrote {output_dir / 'scheduling-placement-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
