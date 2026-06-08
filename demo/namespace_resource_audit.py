#!/usr/bin/env python3
"""Audit namespace ResourceQuota and LimitRange guardrails."""

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


def parse_cpu_millicores(value: Any) -> int:
    text = str(value)
    if text.endswith("m"):
        return int(text[:-1])
    return int(float(text) * 1000)


def parse_memory_mib(value: Any) -> int:
    text = str(value)
    match = re.fullmatch(r"([0-9.]+)(Ki|Mi|Gi|Ti)?", text)
    if not match:
        raise ValueError(f"unsupported memory quantity: {text}")
    number = float(match.group(1))
    suffix = match.group(2) or "Mi"
    scale = {"Ki": 1 / 1024, "Mi": 1, "Gi": 1024, "Ti": 1024 * 1024}[suffix]
    return int(number * scale)


def parse_count(value: Any) -> int:
    return int(str(value))


def quantity_value(key: str, value: Any) -> int:
    if key.endswith(".cpu"):
        return parse_cpu_millicores(value)
    if key.endswith(".memory") or key == "requests.storage":
        return parse_memory_mib(value)
    return parse_count(value)


def deployment_pod_spec(deployment: dict[str, Any]) -> dict[str, Any]:
    return deployment.get("spec", {}).get("template", {}).get("spec", {})


def deployment_replicas(deployment: dict[str, Any]) -> int:
    return int(deployment.get("spec", {}).get("replicas", 1))


def namespace_usage(docs: list[dict[str, Any]], namespace_name: str) -> dict[str, int]:
    usage = {
        "pods": 0,
        "requests.cpu": 0,
        "requests.memory": 0,
        "limits.cpu": 0,
        "limits.memory": 0,
        "persistentvolumeclaims": 0,
        "services": 0,
        "configmaps": 0,
        "secrets": 0,
    }
    for doc in docs:
        if namespace(doc) != namespace_name:
            continue
        kind = str(doc.get("kind", ""))
        if kind == "Deployment":
            replicas = deployment_replicas(doc)
            usage["pods"] += replicas
            for container in deployment_pod_spec(doc).get("containers", []):
                resources = container.get("resources", {})
                requests = resources.get("requests", {})
                limits = resources.get("limits", {})
                usage["requests.cpu"] += parse_cpu_millicores(requests.get("cpu", "0")) * replicas
                usage["requests.memory"] += parse_memory_mib(requests.get("memory", "0Mi")) * replicas
                usage["limits.cpu"] += parse_cpu_millicores(limits.get("cpu", "0")) * replicas
                usage["limits.memory"] += parse_memory_mib(limits.get("memory", "0Mi")) * replicas
        elif kind == "PersistentVolumeClaim":
            usage["persistentvolumeclaims"] += 1
            storage = doc.get("spec", {}).get("resources", {}).get("requests", {}).get("storage", "0Mi")
            usage["requests.storage"] = usage.get("requests.storage", 0) + parse_memory_mib(storage)
        elif kind == "Service":
            usage["services"] += 1
        elif kind == "ConfigMap":
            usage["configmaps"] += 1
        elif kind == "Secret":
            usage["secrets"] += 1
    return usage


def limit_entry(limit_range: dict[str, Any]) -> dict[str, Any]:
    for item in limit_range.get("spec", {}).get("limits", []):
        if item.get("type") == "Container":
            return item
    return {}


def get_limit_field(limit_range: dict[str, Any], field: str) -> Any:
    section, key = field.split(".", 1)
    value = limit_entry(limit_range).get(section, {})
    return value.get(key) if isinstance(value, dict) else None


def set_limit_field(limit_range: dict[str, Any], field: str, value: Any) -> None:
    section, key = field.split(".", 1)
    limit_entry(limit_range).setdefault(section, {})[key] = value


def remove_limit_field(limit_range: dict[str, Any], field: str) -> None:
    section, key = field.split(".", 1)
    value = limit_entry(limit_range).get(section, {})
    if isinstance(value, dict):
        value.pop(key, None)


def sane_limit_bounds(limit_range: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    for resource in ("cpu", "memory"):
        values = {
            "min": get_limit_field(limit_range, f"min.{resource}"),
            "defaultRequest": get_limit_field(limit_range, f"defaultRequest.{resource}"),
            "default": get_limit_field(limit_range, f"default.{resource}"),
            "max": get_limit_field(limit_range, f"max.{resource}"),
        }
        if any(value is None for value in values.values()):
            continue
        parser = parse_cpu_millicores if resource == "cpu" else parse_memory_mib
        ordered = [parser(values[key]) for key in ("min", "defaultRequest", "default", "max")]
        if ordered != sorted(ordered):
            gaps.append({"resource": resource, "values": values})
    return gaps


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    index = index_documents(docs)
    required_labels = list(policy.get("required_labels", []))
    namespace_configs = dict(policy.get("namespaces", {}))
    headroom_ratio = float(policy.get("quota_headroom_ratio", 1.0))
    quota_gaps = []
    coverage_gaps = []
    limit_gaps = []
    defaulting_gaps = []
    bounds_gaps = []
    label_gaps = []
    summaries = []

    for namespace_name, config in namespace_configs.items():
        ns = index.get(("Namespace", "default", namespace_name), {})
        quota = index.get(("ResourceQuota", namespace_name, config["resource_quota"]), {})
        limit_range = index.get(("LimitRange", namespace_name, config["limit_range"]), {})
        labels = metadata(ns).get("labels", {})
        missing_labels = [label for label in required_labels if label not in labels]
        if missing_labels:
            label_gaps.append({"namespace": namespace_name, "missing_labels": missing_labels})

        hard = quota.get("spec", {}).get("hard", {}) if quota else {}
        missing_quota_keys = [key for key in config.get("required_quota_keys", []) if key not in hard]
        if not quota or missing_quota_keys:
            quota_gaps.append({"namespace": namespace_name, "missing_quota_keys": missing_quota_keys})

        usage = namespace_usage(docs, namespace_name)
        for key, used in usage.items():
            if key not in hard:
                continue
            required = used * headroom_ratio
            observed = quantity_value(key, hard[key])
            if observed < required:
                coverage_gaps.append(
                    {
                        "namespace": namespace_name,
                        "resource": key,
                        "used": used,
                        "required_with_headroom": required,
                        "quota": observed,
                    }
                )

        missing_limit_fields = [
            field for field in config.get("required_limit_fields", []) if get_limit_field(limit_range, field) is None
        ]
        if not limit_range:
            limit_gaps.append({"namespace": namespace_name, "missing": True})
        if missing_limit_fields:
            defaulting_gaps.append({"namespace": namespace_name, "missing_fields": missing_limit_fields})
        for gap in sane_limit_bounds(limit_range):
            bounds_gaps.append({"namespace": namespace_name, **gap})
        summaries.append(
            {
                "namespace": namespace_name,
                "role": config.get("role"),
                "resource_quota": name(quota) if quota else None,
                "limit_range": name(limit_range) if limit_range else None,
                "usage": usage,
                "hard": hard,
            }
        )

    checks = [
        check(
            "namespace_inventory",
            len(namespace_configs) >= int(policy.get("minimum_namespace_count", 0)),
            "Policy covers the expected telemetry and workload namespaces.",
            {"namespace_count": len(namespace_configs), "namespaces": sorted(namespace_configs)},
        ),
        check(
            "namespace_governance_labels",
            not label_gaps,
            "Namespaces carry ownership labels used by admission and cost/governance selection.",
            {"gaps": label_gaps},
        ),
        check(
            "namespace_resource_quota",
            not quota_gaps,
            "Every namespace has ResourceQuota with required compute, memory, object, and storage keys.",
            {"gaps": quota_gaps},
        ),
        check(
            "quota_covers_workloads",
            not coverage_gaps,
            "ResourceQuota hard limits cover current Deployment resource requests and limits with configured headroom.",
            {"headroom_ratio": headroom_ratio, "gaps": coverage_gaps},
        ),
        check(
            "namespace_limit_range",
            not limit_gaps,
            "Every namespace has a container LimitRange.",
            {"gaps": limit_gaps},
        ),
        check(
            "container_defaulting",
            not defaulting_gaps,
            "LimitRanges define default requests, defaults, minimums, and maximums for CPU and memory.",
            {"gaps": defaulting_gaps},
        ),
        check(
            "limit_range_sane_bounds",
            not bounds_gaps,
            "LimitRange min/defaultRequest/default/max values are ordered for CPU and memory.",
            {"gaps": bounds_gaps},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "namespace_count": len(namespace_configs),
        "check_count": len(checks),
        "failed_count": len(failed),
        "namespaces": summaries,
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
    namespace_name = str(fixture["namespace"])
    config = policy["namespaces"][namespace_name]
    mutation = fixture["mutation"]
    if mutation == "remove_resource_quota":
        return remove_doc(mutated, "ResourceQuota", namespace_name, str(config["resource_quota"]))
    if mutation == "remove_limit_range":
        return remove_doc(mutated, "LimitRange", namespace_name, str(config["limit_range"]))
    if mutation == "set_quota":
        quota = find_doc(mutated, "ResourceQuota", namespace_name, str(config["resource_quota"]))
        quota.setdefault("spec", {}).setdefault("hard", {})[str(fixture["key"])] = str(fixture["value"])
    elif mutation == "remove_quota_key":
        quota = find_doc(mutated, "ResourceQuota", namespace_name, str(config["resource_quota"]))
        quota.setdefault("spec", {}).setdefault("hard", {}).pop(str(fixture["key"]), None)
    elif mutation == "remove_limit_field":
        limit_range = find_doc(mutated, "LimitRange", namespace_name, str(config["limit_range"]))
        remove_limit_field(limit_range, str(fixture["field"]))
    elif mutation == "set_limit_field":
        limit_range = find_doc(mutated, "LimitRange", namespace_name, str(config["limit_range"]))
        set_limit_field(limit_range, str(fixture["field"]), str(fixture["value"]))
    elif mutation == "remove_namespace_label":
        ns = find_doc(mutated, "Namespace", "default", namespace_name)
        metadata(ns).setdefault("labels", {}).pop(str(fixture["label"]), None)
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
        "Negative fixtures prove quota, limit range, coverage, bounds, and label drift is detected.",
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
        "namespace_count": audit["namespace_count"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "namespaces": audit["namespaces"],
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "namespace-resource-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Namespace Resource Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks namespace-level ResourceQuota and LimitRange controls",
        "for the telemetry plane and sample AI workload namespace. It verifies",
        "that quotas exist, cover current Deployment resource use with headroom,",
        "and include container defaults and sane CPU/memory bounds.",
        "",
        "## Summary",
        "",
        f"- Namespaces: `{report['namespace_count']}`",
        f"- Checks: `{report['check_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Namespaces",
        "",
        "| Namespace | Role | ResourceQuota | LimitRange | Pods used | CPU request m | Memory request Mi |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for item in report["namespaces"]:
        usage = item["usage"]
        lines.append(
            "| `{namespace}` | `{role}` | `{quota}` | `{limit}` | {pods} | {cpu} | {memory} |".format(
                namespace=item["namespace"],
                role=item["role"],
                quota=item["resource_quota"],
                limit=item["limit_range"],
                pods=usage.get("pods", 0),
                cpu=usage.get("requests.cpu", 0),
                memory=usage.get("requests.memory", 0),
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
    (output_dir / "namespace-resource-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/namespace-resource-policy.json")
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
    print(f"wrote {output_dir / 'namespace-resource-audit.json'}")
    print(f"wrote {output_dir / 'namespace-resource-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
