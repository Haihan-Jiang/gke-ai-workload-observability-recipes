#!/usr/bin/env python3
"""Audit availability topology and disruption-budget controls."""

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
    return {
        "name": name,
        "status": PASS if ok else FAIL,
        "reason": reason,
        "evidence": evidence,
    }


def workload_key(workload: dict[str, Any]) -> str:
    return f"{workload['namespace']}/{workload['name']}"


def find_workload(policy: dict[str, Any], workload_name: str) -> dict[str, Any]:
    for workload in policy.get("workloads", []):
        if workload["name"] == workload_name:
            return workload
    raise ValueError(f"missing workload config: {workload_name}")


def pod_template(workload_doc: dict[str, Any]) -> dict[str, Any]:
    return workload_doc.get("spec", {}).get("template", {})


def pod_spec(workload_doc: dict[str, Any]) -> dict[str, Any]:
    return pod_template(workload_doc).get("spec", {})


def pod_labels(workload_doc: dict[str, Any]) -> dict[str, Any]:
    labels = pod_template(workload_doc).get("metadata", {}).get("labels", {})
    return labels if isinstance(labels, dict) else {}


def deployment_replicas(workload_doc: dict[str, Any]) -> int:
    return int(workload_doc.get("spec", {}).get("replicas", 1))


def selector_labels(doc: dict[str, Any]) -> dict[str, Any]:
    labels = doc.get("spec", {}).get("selector", {}).get("matchLabels", {})
    return labels if isinstance(labels, dict) else {}


def pdb_min_available(pdb: dict[str, Any]) -> int | None:
    value = pdb.get("spec", {}).get("minAvailable")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def topology_spread_constraints(workload_doc: dict[str, Any]) -> list[dict[str, Any]]:
    constraints = pod_spec(workload_doc).get("topologySpreadConstraints", [])
    return [item for item in constraints if isinstance(item, dict)]


def subset_of(expected: dict[str, Any], observed: dict[str, Any]) -> bool:
    return all(observed.get(key) == value for key, value in expected.items())


def check_pdb(workload: dict[str, Any], workload_doc: dict[str, Any], pdb: dict[str, Any]) -> dict[str, Any] | None:
    if not pdb:
        return {"workload": workload_key(workload), "reason": "missing_pdb"}
    replicas = deployment_replicas(workload_doc)
    min_available = pdb_min_available(pdb)
    selector = selector_labels(pdb)
    expected_selector = dict(workload.get("selector", {}))
    mode = workload.get("availability_mode")
    if min_available is None:
        return {"workload": workload_key(workload), "reason": "invalid_min_available"}
    if not subset_of(selector, pod_labels(workload_doc)) or not subset_of(expected_selector, selector):
        return {"workload": workload_key(workload), "reason": "selector_mismatch", "selector": selector}
    if mode == "multi_replica" and not (0 < min_available < replicas):
        return {
            "workload": workload_key(workload),
            "reason": "multi_replica_pdb_must_allow_one_voluntary_disruption",
            "replicas": replicas,
            "min_available": min_available,
        }
    if mode == "guarded_singleton" and min_available != replicas:
        return {
            "workload": workload_key(workload),
            "reason": "guarded_singleton_pdb_must_block_voluntary_disruption",
            "replicas": replicas,
            "min_available": min_available,
        }
    return None


def topology_keys(workload_doc: dict[str, Any]) -> list[str]:
    return [str(item.get("topologyKey", "")) for item in topology_spread_constraints(workload_doc)]


def topology_gaps(workload: dict[str, Any], workload_doc: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    if not workload.get("requires_topology_spread", False):
        return []
    required_keys = set(policy.get("required_topology_keys", []))
    allowed_modes = set(policy.get("allowed_when_unsatisfiable", []))
    observed_keys = set(topology_keys(workload_doc))
    gaps: list[dict[str, Any]] = []
    missing = sorted(required_keys - observed_keys)
    if missing:
        gaps.append({"workload": workload_key(workload), "reason": "missing_topology_keys", "missing": missing})
    for constraint in topology_spread_constraints(workload_doc):
        mode = constraint.get("whenUnsatisfiable")
        max_skew = int(constraint.get("maxSkew", 99))
        if mode not in allowed_modes or max_skew > 1:
            gaps.append(
                {
                    "workload": workload_key(workload),
                    "reason": "unsafe_constraint",
                    "topology_key": constraint.get("topologyKey"),
                    "when_unsatisfiable": mode,
                    "max_skew": max_skew,
                }
            )
    return gaps


def spread_selector_gaps(workload: dict[str, Any], workload_doc: dict[str, Any]) -> list[dict[str, Any]]:
    labels = pod_labels(workload_doc)
    expected_selector = dict(workload.get("selector", {}))
    gaps: list[dict[str, Any]] = []
    for constraint in topology_spread_constraints(workload_doc):
        selector = constraint.get("labelSelector", {}).get("matchLabels", {})
        if not isinstance(selector, dict):
            gaps.append({"workload": workload_key(workload), "reason": "missing_spread_selector"})
            continue
        if not subset_of(selector, labels) or not subset_of(expected_selector, selector):
            gaps.append(
                {
                    "workload": workload_key(workload),
                    "topology_key": constraint.get("topologyKey"),
                    "selector": selector,
                    "pod_labels": labels,
                }
            )
    return gaps


def label_gaps(workload: dict[str, Any], workload_doc: dict[str, Any], pdb: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    required = list(policy.get("required_labels", []))
    for kind, doc in ((workload.get("kind", "Deployment"), workload_doc), ("PodDisruptionBudget", pdb)):
        labels = metadata(doc).get("labels", {}) if doc else {}
        missing = [label for label in required if label not in labels]
        if missing:
            gaps.append({"workload": workload_key(workload), "kind": kind, "missing": missing})
    return gaps


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    index = index_documents(docs)
    workloads = list(policy.get("workloads", []))
    replica_gaps = []
    pdb_gaps = []
    topology_gaps_found = []
    selector_gaps = []
    labels_missing = []
    summaries = []
    pdb_count = 0
    topology_spread_count = 0

    for workload in workloads:
        workload_doc = index.get((workload.get("kind", "Deployment"), workload["namespace"], workload["name"]), {})
        pdb = index.get(("PodDisruptionBudget", workload["namespace"], workload["pdb"]), {})
        replicas = deployment_replicas(workload_doc) if workload_doc else 0
        min_replicas = int(workload.get("min_replicas", 1))
        if not workload_doc or replicas < min_replicas:
            replica_gaps.append(
                {
                    "workload": workload_key(workload),
                    "replicas": replicas,
                    "minimum": min_replicas,
                }
            )

        if pdb:
            pdb_count += 1
        pdb_gap = check_pdb(workload, workload_doc, pdb)
        if pdb_gap:
            pdb_gaps.append(pdb_gap)

        constraints = topology_spread_constraints(workload_doc)
        topology_spread_count += len(constraints)
        topology_gaps_found.extend(topology_gaps(workload, workload_doc, policy))
        selector_gaps.extend(spread_selector_gaps(workload, workload_doc))
        labels_missing.extend(label_gaps(workload, workload_doc, pdb, policy))
        summaries.append(
            {
                "workload": workload_key(workload),
                "kind": workload.get("kind", "Deployment"),
                "availability_mode": workload.get("availability_mode"),
                "replicas": replicas,
                "pdb": name(pdb) if pdb else None,
                "pdb_min_available": pdb_min_available(pdb) if pdb else None,
                "topology_keys": topology_keys(workload_doc),
            }
        )

    checks = [
        check(
            "workload_inventory",
            len(workloads) >= int(policy.get("minimum_workload_count", 0)),
            "Policy covers the collector and sample inference workload availability boundaries.",
            {"workload_count": len(workloads), "workloads": [workload_key(item) for item in workloads]},
        ),
        check(
            "replica_policy",
            not replica_gaps,
            "Each workload meets its configured replica floor.",
            {"gaps": replica_gaps},
        ),
        check(
            "pdb_coverage",
            not pdb_gaps,
            "Each workload has a PDB whose selector matches pods and whose minAvailable matches its availability mode.",
            {"gaps": pdb_gaps},
        ),
        check(
            "topology_spread_coverage",
            not topology_gaps_found,
            "Multi-replica inference workloads declare the required zone and node topology spread constraints.",
            {"gaps": topology_gaps_found},
        ),
        check(
            "spread_selector_matches_pod_labels",
            not selector_gaps,
            "Topology spread selectors match the pods they are meant to distribute.",
            {"gaps": selector_gaps},
        ),
        check(
            "availability_label_governance",
            not labels_missing,
            "Workloads and PDBs carry owner labels used by review and policy tooling.",
            {"gaps": labels_missing},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "workload_count": len(workloads),
        "pdb_count": pdb_count,
        "topology_spread_count": topology_spread_count,
        "guarded_singleton_count": sum(1 for item in workloads if item.get("availability_mode") == "guarded_singleton"),
        "multi_replica_count": sum(1 for item in workloads if item.get("availability_mode") == "multi_replica"),
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
        doc
        for doc in docs
        if not (doc.get("kind") == kind and namespace(doc) == doc_namespace and name(doc) == doc_name)
    ]


def mutate_fixture(docs: list[dict[str, Any]], policy: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    workload = find_workload(policy, str(fixture["workload"]))
    workload_doc = find_doc(mutated, workload.get("kind", "Deployment"), workload["namespace"], workload["name"])
    mutation = fixture["mutation"]
    if mutation == "set_replicas":
        workload_doc.setdefault("spec", {})["replicas"] = int(fixture["value"])
    elif mutation == "remove_pdb":
        return remove_doc(mutated, "PodDisruptionBudget", workload["namespace"], workload["pdb"])
    elif mutation == "set_pdb_min_available":
        pdb = find_doc(mutated, "PodDisruptionBudget", workload["namespace"], workload["pdb"])
        pdb.setdefault("spec", {})["minAvailable"] = int(fixture["value"])
    elif mutation == "remove_topology_key":
        key = str(fixture["topology_key"])
        pod_spec(workload_doc)["topologySpreadConstraints"] = [
            item for item in topology_spread_constraints(workload_doc) if item.get("topologyKey") != key
        ]
    elif mutation == "replace_topology_key":
        old_key = str(fixture["old_topology_key"])
        for constraint in topology_spread_constraints(workload_doc):
            if constraint.get("topologyKey") == old_key:
                constraint["topologyKey"] = str(fixture["new_topology_key"])
                break
    elif mutation == "set_spread_selector_label":
        for constraint in topology_spread_constraints(workload_doc):
            labels = constraint.setdefault("labelSelector", {}).setdefault("matchLabels", {})
            labels[str(fixture["label"])] = str(fixture["value"])
    elif mutation == "remove_owner_label":
        doc = find_doc(mutated, str(fixture["kind"]), workload["namespace"], workload["pdb"])
        metadata(doc).setdefault("labels", {}).pop(str(fixture["label"]), None)
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
        "Negative fixtures prove replica, PDB, topology, selector, and label drift is detected.",
        {
            "fixture_count": len(fixture_results),
            "detected_fixture_count": detected_fixture_count,
            "undetected": undetected,
        },
    )
    checks = audit["checks"] + [negative_fixture_check]
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "workload_count": audit["workload_count"],
        "pdb_count": audit["pdb_count"],
        "topology_spread_count": audit["topology_spread_count"],
        "guarded_singleton_count": audit["guarded_singleton_count"],
        "multi_replica_count": audit["multi_replica_count"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "workloads": audit["workloads"],
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "availability-topology-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Availability Topology Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks whether the GKE recipe has explicit availability",
        "and voluntary-disruption boundaries. It verifies replica floors,",
        "PodDisruptionBudget coverage, topology spread constraints for the",
        "multi-replica inference workload, selector alignment, and owner labels.",
        "",
        "## Summary",
        "",
        f"- Workloads: `{report['workload_count']}`",
        f"- PodDisruptionBudgets: `{report['pdb_count']}`",
        f"- Topology spread constraints: `{report['topology_spread_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Workloads",
        "",
        "| Workload | Mode | Replicas | PDB | minAvailable | Topology keys |",
        "| --- | --- | ---: | --- | ---: | --- |",
    ]
    for item in report["workloads"]:
        keys = ", ".join(f"`{key}`" for key in item["topology_keys"]) or "-"
        lines.append(
            "| `{workload}` | `{mode}` | {replicas} | `{pdb}` | {min_available} | {keys} |".format(
                workload=item["workload"],
                mode=item["availability_mode"],
                replicas=item["replicas"],
                pdb=item["pdb"],
                min_available=item["pdb_min_available"],
                keys=keys,
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
    (output_dir / "availability-topology-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/availability-topology-policy.json")
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
    print(f"wrote {output_dir / 'availability-topology-audit.json'}")
    print(f"wrote {output_dir / 'availability-topology-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
