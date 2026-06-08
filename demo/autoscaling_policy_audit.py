#!/usr/bin/env python3
"""Audit HorizontalPodAutoscaler policy for the sample inference workload."""

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


def pod_spec(deployment: dict[str, Any]) -> dict[str, Any]:
    return deployment.get("spec", {}).get("template", {}).get("spec", {})


def find_container(deployment: dict[str, Any], container_name: str) -> dict[str, Any]:
    for container in pod_spec(deployment).get("containers", []):
        if container.get("name") == container_name:
            return container
    return {}


def resource_metrics(hpa: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics = {}
    for metric in hpa.get("spec", {}).get("metrics", []):
        if metric.get("type") != "Resource":
            continue
        resource = metric.get("resource", {})
        resource_name = str(resource.get("name", ""))
        if resource_name:
            metrics[resource_name] = resource.get("target", {})
    return metrics


def behavior_policy_count(hpa: dict[str, Any]) -> int:
    behavior = hpa.get("spec", {}).get("behavior", {})
    return sum(len(behavior.get(section, {}).get("policies", [])) for section in ("scaleUp", "scaleDown"))


def scale_behavior_ok(hpa: dict[str, Any], target: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    behavior = hpa.get("spec", {}).get("behavior", {})
    scale_up = behavior.get("scaleUp", {})
    scale_down = behavior.get("scaleDown", {})
    up_policies = scale_up.get("policies", [])
    down_policies = scale_down.get("policies", [])
    up_pods = [int(item.get("value", 0)) for item in up_policies if item.get("type") == "Pods"]
    up_percent = [int(item.get("value", 0)) for item in up_policies if item.get("type") == "Percent"]
    evidence = {
        "scale_up_stabilization_seconds": scale_up.get("stabilizationWindowSeconds"),
        "scale_down_stabilization_seconds": scale_down.get("stabilizationWindowSeconds"),
        "scale_up_policies": up_policies,
        "scale_down_policies": down_policies,
    }
    ok = (
        int(scale_up.get("stabilizationWindowSeconds", 999999)) <= int(target["max_scale_up_stabilization_seconds"])
        and max(up_pods or [0]) >= int(target["min_scale_up_pods_per_minute"])
        and max(up_percent or [0]) >= int(target["min_scale_up_percent_per_minute"])
        and int(scale_down.get("stabilizationWindowSeconds", 0)) >= int(target["min_scale_down_stabilization_seconds"])
        and len(down_policies) > 0
    )
    return ok, evidence


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    target = policy["target"]
    index = index_documents(docs)
    hpa = index.get(("HorizontalPodAutoscaler", target["namespace"], target["hpa"]), {})
    deployment = index.get(("Deployment", target["namespace"], target["deployment"]), {})
    container = find_container(deployment, target["container"]) if deployment else {}
    metrics = resource_metrics(hpa)
    required_metrics = set(target.get("required_resource_metrics", []))
    observed_metrics = set(metrics)
    metric_target_gaps = []
    request_gaps = []

    for resource in sorted(required_metrics & observed_metrics):
        metric_target = metrics[resource]
        utilization = int(metric_target.get("averageUtilization", 0))
        if metric_target.get("type") != "Utilization" or not (
            int(target["min_target_utilization"]) <= utilization <= int(target["max_target_utilization"])
        ):
            metric_target_gaps.append({"resource": resource, "target": metric_target})
    requests = container.get("resources", {}).get("requests", {})
    for resource in sorted(required_metrics):
        if resource not in requests:
            request_gaps.append({"resource": resource})

    scale_target = hpa.get("spec", {}).get("scaleTargetRef", {})
    min_replicas = int(hpa.get("spec", {}).get("minReplicas", 0))
    max_replicas = int(hpa.get("spec", {}).get("maxReplicas", 0))
    scale_ok, scale_evidence = scale_behavior_ok(hpa, target) if hpa else (False, {})
    labels = metadata(hpa).get("labels", {}) if hpa else {}
    missing_labels = [label for label in policy.get("required_labels", []) if label not in labels]

    checks = [
        check(
            "hpa_coverage",
            bool(hpa),
            "The sample inference workload has a HorizontalPodAutoscaler.",
            {"hpa": name(hpa) if hpa else None},
        ),
        check(
            "hpa_target_ref",
            bool(hpa)
            and scale_target.get("apiVersion") == target["api_version"]
            and scale_target.get("kind") == target["kind"]
            and scale_target.get("name") == target["deployment"],
            "The HPA targets the intended Deployment.",
            {"scale_target_ref": scale_target},
        ),
        check(
            "replica_bounds",
            min_replicas >= int(target["min_replicas"])
            and max_replicas >= int(target["minimum_burst_replicas"])
            and max_replicas <= int(target["max_allowed_replicas"])
            and max_replicas > min_replicas,
            "HPA min/max replicas preserve baseline availability and leave room for burst recovery without exceeding namespace policy.",
            {"min_replicas": min_replicas, "max_replicas": max_replicas},
        ),
        check(
            "metric_coverage",
            required_metrics.issubset(observed_metrics),
            "HPA covers CPU and memory pressure instead of relying on a single signal.",
            {"required_metrics": sorted(required_metrics), "observed_metrics": sorted(observed_metrics)},
        ),
        check(
            "metric_targets",
            not metric_target_gaps and required_metrics.issubset(observed_metrics),
            "HPA metric targets use utilization thresholds inside the policy band.",
            {"gaps": metric_target_gaps},
        ),
        check(
            "metric_request_alignment",
            not request_gaps,
            "HPA resource metrics have matching container requests in the Deployment.",
            {"gaps": request_gaps, "requests": requests},
        ),
        check(
            "scale_behavior",
            scale_ok,
            "HPA behavior allows fast scale-up and dampened scale-down.",
            scale_evidence,
        ),
        check(
            "autoscaling_label_governance",
            not missing_labels,
            "HPA carries owner labels used by review and policy tooling.",
            {"missing_labels": missing_labels, "labels": labels},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "hpa_count": 1 if hpa else 0,
        "metric_count": len(metrics),
        "behavior_policy_count": behavior_policy_count(hpa) if hpa else 0,
        "check_count": len(checks),
        "failed_count": len(failed),
        "target": {
            "namespace": target["namespace"],
            "deployment": target["deployment"],
            "hpa": name(hpa) if hpa else None,
            "min_replicas": min_replicas,
            "max_replicas": max_replicas,
            "metrics": sorted(metrics),
        },
        "checks": checks,
    }


def mutate_fixture(docs: list[dict[str, Any]], policy: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    target = policy["target"]
    mutation = fixture["mutation"]
    if mutation == "remove_hpa":
        return remove_doc(mutated, "HorizontalPodAutoscaler", target["namespace"], target["hpa"])
    hpa = find_doc(mutated, "HorizontalPodAutoscaler", target["namespace"], target["hpa"])
    deployment = find_doc(mutated, "Deployment", target["namespace"], target["deployment"])
    if mutation == "set_scale_target_name":
        hpa.setdefault("spec", {}).setdefault("scaleTargetRef", {})["name"] = str(fixture["value"])
    elif mutation == "set_min_replicas":
        hpa.setdefault("spec", {})["minReplicas"] = int(fixture["value"])
    elif mutation == "set_max_replicas":
        hpa.setdefault("spec", {})["maxReplicas"] = int(fixture["value"])
    elif mutation == "remove_metric":
        resource = str(fixture["resource"])
        hpa.setdefault("spec", {})["metrics"] = [
            item
            for item in hpa.get("spec", {}).get("metrics", [])
            if item.get("resource", {}).get("name") != resource
        ]
    elif mutation == "set_metric_target":
        for metric in hpa.get("spec", {}).get("metrics", []):
            if metric.get("resource", {}).get("name") == fixture["resource"]:
                metric.setdefault("resource", {}).setdefault("target", {})["averageUtilization"] = int(fixture["value"])
    elif mutation == "remove_scale_down_behavior":
        hpa.setdefault("spec", {}).setdefault("behavior", {}).pop("scaleDown", None)
    elif mutation == "remove_container_request":
        container = find_container(deployment, target["container"])
        container.setdefault("resources", {}).setdefault("requests", {}).pop(str(fixture["resource"]), None)
    elif mutation == "remove_owner_label":
        metadata(hpa).setdefault("labels", {}).pop(str(fixture["label"]), None)
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
        "Negative fixtures prove HPA coverage, target, bounds, metrics, behavior, requests, and labels are enforced.",
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
        "hpa_count": audit["hpa_count"],
        "metric_count": audit["metric_count"],
        "behavior_policy_count": audit["behavior_policy_count"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "target": audit["target"],
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "autoscaling-policy-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    target = report["target"]
    lines = [
        "# Autoscaling Policy Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that the sample inference workload has a real",
        "HorizontalPodAutoscaler, not only an offline HPA lag model. It verifies",
        "the HPA target, replica bounds, CPU/memory metrics, metric-to-request",
        "alignment, scale behavior, owner labels, and negative fixtures.",
        "",
        "## Summary",
        "",
        f"- HPA count: `{report['hpa_count']}`",
        f"- Metrics: `{report['metric_count']}`",
        f"- Behavior policies: `{report['behavior_policy_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Target",
        "",
        "| Namespace | Deployment | HPA | Min replicas | Max replicas | Metrics |",
        "| --- | --- | --- | ---: | ---: | --- |",
        "| `{namespace}` | `{deployment}` | `{hpa}` | {min_replicas} | {max_replicas} | {metrics} |".format(
            namespace=target["namespace"],
            deployment=target["deployment"],
            hpa=target["hpa"],
            min_replicas=target["min_replicas"],
            max_replicas=target["max_replicas"],
            metrics=", ".join(f"`{metric}`" for metric in target["metrics"]),
        ),
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['status'] == PASS else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Detected |", "| --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(f"| `{item['name']}` | {'yes' if item['detected'] else 'no'} |")
    lines.append("")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "autoscaling-policy-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/autoscaling-policy.json")
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
    print(f"wrote {output_dir / 'autoscaling-policy-audit.json'}")
    print(f"wrote {output_dir / 'autoscaling-policy-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
