#!/usr/bin/env python3
"""Audit Pod Security Admission labels and restricted-profile compatibility."""

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


def pod_spec(deployment: dict[str, Any]) -> dict[str, Any]:
    return deployment.get("spec", {}).get("template", {}).get("spec", {})


def pod_security(deployment: dict[str, Any]) -> dict[str, Any]:
    value = pod_spec(deployment).get("securityContext", {})
    return value if isinstance(value, dict) else {}


def containers(deployment: dict[str, Any]) -> list[dict[str, Any]]:
    value = pod_spec(deployment).get("containers", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def find_container(deployment: dict[str, Any], container_name: str) -> dict[str, Any]:
    for container in containers(deployment):
        if container.get("name") == container_name:
            return container
    return {}


def container_security(container: dict[str, Any]) -> dict[str, Any]:
    value = container.get("securityContext", {})
    return value if isinstance(value, dict) else {}


def workload_key(workload: dict[str, Any]) -> str:
    return f"{workload['namespace']}/{workload['deployment']}"


def namespace_label_gaps(ns: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    labels = metadata(ns).get("labels", {}) if ns else {}
    gaps = []
    for label, expected in policy["required_namespace_labels"].items():
        if labels.get(label) != expected:
            gaps.append({"label": label, "observed": labels.get(label), "expected": expected})
    return gaps


def owner_label_gaps(ns: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    labels = metadata(ns).get("labels", {}) if ns else {}
    return [label for label in policy.get("required_owner_labels", []) if label not in labels]


def pod_security_gaps(workload: dict[str, Any], deployment: dict[str, Any]) -> list[dict[str, Any]]:
    spec = pod_spec(deployment)
    security = pod_security(deployment)
    seccomp = security.get("seccompProfile", {})
    gaps = []
    if security.get("runAsNonRoot") is not True:
        gaps.append({"workload": workload_key(workload), "field": "runAsNonRoot", "observed": security.get("runAsNonRoot")})
    if seccomp.get("type") != "RuntimeDefault":
        gaps.append({"workload": workload_key(workload), "field": "seccompProfile.type", "observed": seccomp.get("type")})
    for field in ("hostNetwork", "hostPID", "hostIPC"):
        if spec.get(field) is True:
            gaps.append({"workload": workload_key(workload), "field": field, "observed": True})
    return gaps


def container_security_gaps(workload: dict[str, Any], deployment: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    for container in containers(deployment):
        security = container_security(container)
        capabilities = security.get("capabilities", {})
        added = [str(item) for item in capabilities.get("add", [])] if isinstance(capabilities.get("add", []), list) else []
        dropped = [str(item) for item in capabilities.get("drop", [])] if isinstance(capabilities.get("drop", []), list) else []
        if security.get("privileged") is True:
            gaps.append({"workload": workload_key(workload), "container": container.get("name"), "field": "privileged"})
        if security.get("allowPrivilegeEscalation") is not False:
            gaps.append(
                {
                    "workload": workload_key(workload),
                    "container": container.get("name"),
                    "field": "allowPrivilegeEscalation",
                    "observed": security.get("allowPrivilegeEscalation"),
                }
            )
        if "ALL" not in dropped:
            gaps.append({"workload": workload_key(workload), "container": container.get("name"), "field": "capabilities.drop"})
        if added:
            gaps.append(
                {"workload": workload_key(workload), "container": container.get("name"), "field": "capabilities.add", "added": added}
            )
    return gaps


def volume_gaps(workload: dict[str, Any], deployment: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    for volume in pod_spec(deployment).get("volumes", []):
        if isinstance(volume, dict) and "hostPath" in volume:
            gaps.append({"workload": workload_key(workload), "volume": volume.get("name"), "type": "hostPath"})
    return gaps


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    index = index_documents(docs)
    namespace_gaps = []
    owner_gaps = []
    pod_gaps = []
    container_gaps = []
    volume_gaps_found = []
    summaries = []

    for workload in policy.get("workloads", []):
        ns = index.get(("Namespace", "default", workload["namespace"]), {})
        deployment = index.get(("Deployment", workload["namespace"], workload["deployment"]), {})
        psa_gaps = namespace_label_gaps(ns, policy)
        if psa_gaps:
            namespace_gaps.append({"namespace": workload["namespace"], "gaps": psa_gaps})
        missing_owner = owner_label_gaps(ns, policy)
        if missing_owner:
            owner_gaps.append({"namespace": workload["namespace"], "missing": missing_owner})
        current_pod_gaps = pod_security_gaps(workload, deployment)
        current_container_gaps = container_security_gaps(workload, deployment)
        current_volume_gaps = volume_gaps(workload, deployment)
        pod_gaps.extend(current_pod_gaps)
        container_gaps.extend(current_container_gaps)
        volume_gaps_found.extend(current_volume_gaps)
        summaries.append(
            {
                "workload": workload_key(workload),
                "namespace": workload["namespace"],
                "psa_restricted": not psa_gaps,
                "pod_restricted": not current_pod_gaps,
                "container_restricted": not current_container_gaps,
                "volume_restricted": not current_volume_gaps,
            }
        )

    checks = [
        check(
            "namespace_psa_labels",
            not namespace_gaps,
            "Namespaces enforce, audit, and warn with the restricted Pod Security Admission profile.",
            {"gaps": namespace_gaps},
        ),
        check(
            "namespace_label_governance",
            not owner_gaps,
            "Namespaces keep owner and role labels alongside Pod Security Admission labels.",
            {"gaps": owner_gaps},
        ),
        check(
            "restricted_pod_security",
            not pod_gaps,
            "Pod templates set non-root execution, RuntimeDefault seccomp, and avoid host namespace access.",
            {"gaps": pod_gaps},
        ),
        check(
            "restricted_container_security",
            not container_gaps,
            "Containers avoid privileged mode, privilege escalation, added capabilities, and missing capability drops.",
            {"gaps": container_gaps},
        ),
        check(
            "restricted_volume_types",
            not volume_gaps_found,
            "Pod templates avoid hostPath volumes that violate the restricted profile.",
            {"gaps": volume_gaps_found},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "namespace_count": len({item["namespace"] for item in summaries}),
        "workload_count": len(summaries),
        "restricted_namespace_count": sum(1 for item in summaries if item["psa_restricted"]),
        "restricted_workload_count": sum(
            1
            for item in summaries
            if item["pod_restricted"] and item["container_restricted"] and item["volume_restricted"]
        ),
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


def mutate_fixture(docs: list[dict[str, Any]], policy: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    mutation = fixture["mutation"]
    if mutation in {"remove_namespace_label", "set_namespace_label"}:
        ns = find_doc(mutated, "Namespace", "default", str(fixture["namespace"]))
        labels = metadata(ns).setdefault("labels", {})
        if mutation == "remove_namespace_label":
            labels.pop(str(fixture["label"]), None)
        else:
            labels[str(fixture["label"])] = fixture["value"]
        return mutated

    deployment = find_doc(mutated, "Deployment", str(fixture["namespace"]), str(fixture["deployment"]))
    if mutation == "set_container_security_field":
        container = find_container(deployment, str(fixture["container"]))
        container.setdefault("securityContext", {})[str(fixture["field"])] = fixture["value"]
    elif mutation == "add_container_capability":
        container = find_container(deployment, str(fixture["container"]))
        container.setdefault("securityContext", {}).setdefault("capabilities", {}).setdefault("add", []).append(
            str(fixture["capability"])
        )
    elif mutation == "set_pod_spec_field":
        pod_spec(deployment)[str(fixture["field"])] = fixture["value"]
    elif mutation == "add_host_path_volume":
        pod_spec(deployment).setdefault("volumes", []).append(
            {"name": "host-root", "hostPath": {"path": "/", "type": "Directory"}}
        )
    elif mutation == "remove_pod_security_field":
        pod_security(deployment).pop(str(fixture["field"]), None)
    elif mutation == "set_pod_security_field":
        pod_security(deployment)[str(fixture["field"])] = fixture["value"]
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
        "Negative fixtures prove Pod Security Admission and restricted workload drift is detected.",
        {"fixture_count": len(fixture_results), "detected_fixture_count": detected_fixture_count, "undetected": undetected},
    )
    checks = audit["checks"] + [negative_fixture_check]
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "namespace_count": audit["namespace_count"],
        "workload_count": audit["workload_count"],
        "restricted_namespace_count": audit["restricted_namespace_count"],
        "restricted_workload_count": audit["restricted_workload_count"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "workloads": audit["workloads"],
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pod-security-admission-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Pod Security Admission Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit verifies that namespaces enforce the Kubernetes restricted",
        "Pod Security Admission profile and that collector/workload pod templates",
        "remain compatible with that profile.",
        "",
        "## Summary",
        "",
        f"- Namespaces: `{report['namespace_count']}`",
        f"- Workloads: `{report['workload_count']}`",
        f"- Restricted namespaces: `{report['restricted_namespace_count']}`",
        f"- Restricted workloads: `{report['restricted_workload_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Workloads",
        "",
        "| Workload | PSA labels | Pod security | Container security | Volumes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["workloads"]:
        lines.append(
            "| `{workload}` | {psa} | {pod} | {container} | {volumes} |".format(
                workload=item["workload"],
                psa="PASS" if item["psa_restricted"] else "FAIL",
                pod="PASS" if item["pod_restricted"] else "FAIL",
                container="PASS" if item["container_restricted"] else "FAIL",
                volumes="PASS" if item["volume_restricted"] else "FAIL",
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
    (output_dir / "pod-security-admission-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/pod-security-admission-policy.json")
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
    print(f"wrote {output_dir / 'pod-security-admission-audit.json'}")
    print(f"wrote {output_dir / 'pod-security-admission-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
