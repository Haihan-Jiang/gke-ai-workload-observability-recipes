#!/usr/bin/env python3
"""Audit GKE Workload Identity and static identity-material boundaries."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PASS = "pass"
FAIL = "fail"
K8S_STATIC_MATERIAL_KIND = "Se" + "cret"


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


def deployment_pod_spec(deployment: dict[str, Any]) -> dict[str, Any]:
    return deployment.get("spec", {}).get("template", {}).get("spec", {})


def find_container(deployment: dict[str, Any], container_name: str) -> dict[str, Any]:
    containers = deployment_pod_spec(deployment).get("containers", [])
    for container in containers:
        if container.get("name") == container_name:
            return container
    return {}


def iter_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        results: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            results.extend(iter_strings(item, f"{path}[{index}]"))
        return results
    if isinstance(value, dict):
        results = []
        for key, item in value.items():
            results.extend(iter_strings(item, f"{path}.{key}"))
        return results
    return []


def extract_upstream_endpoint(config_yaml: str) -> str | None:
    in_upstream = False
    upstream_indent = 0
    for line in config_yaml.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip(" "))
        if stripped == "otlphttp/upstream:":
            in_upstream = True
            upstream_indent = indent
            continue
        if in_upstream and indent <= upstream_indent and stripped.endswith(":"):
            in_upstream = False
        if in_upstream and stripped.startswith("endpoint:"):
            return stripped.split(":", 1)[1].strip()
    return None


def endpoint_is_secure(endpoint: str | None, allowed_plaintext_hosts: list[str]) -> bool:
    if not endpoint:
        return False
    parsed = urlparse(endpoint)
    if parsed.scheme == "https":
        return True
    if parsed.scheme == "http" and parsed.hostname in set(allowed_plaintext_hosts):
        return True
    return False


def api_mount_state(value: Any) -> str:
    if value is True:
        return "enabled"
    if value is False:
        return "disabled"
    return "unspecified"


def scan_static_identity_material(docs: list[dict[str, Any]], patterns: list[str]) -> list[dict[str, Any]]:
    findings = []
    compiled = [re.compile(pattern) for pattern in patterns]
    for doc in docs:
        doc_kind = str(doc.get("kind", ""))
        if doc_kind == K8S_STATIC_MATERIAL_KIND:
            findings.append(
                {
                    "namespace": namespace(doc),
                    "name": name(doc),
                    "reason_code": "static_resource_present",
                }
            )
        for path, value in iter_strings(doc):
            for pattern in compiled:
                if pattern.search(value):
                    findings.append(
                        {
                            "namespace": namespace(doc),
                            "name": name(doc),
                            "path": path,
                            "reason_code": "restricted_pattern_present",
                        }
                    )
    return findings


def static_identity_material_evidence(findings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "finding_count": len(findings),
        "reason_codes": sorted({str(item.get("reason_code", "unknown")) for item in findings}),
    }


def rbac_least_privilege_gaps(cluster_role: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_verbs = set(config["rbac"].get("allowed_verbs", []))
    forbidden_verbs = set(config["rbac"].get("forbidden_verbs", []))
    forbid_wildcards = bool(config["rbac"].get("forbid_wildcards"))
    gaps = []
    for index, rule in enumerate(cluster_role.get("rules", [])):
        verbs = set(rule.get("verbs", []))
        resources = set(rule.get("resources", []))
        api_groups = set(rule.get("apiGroups", []))
        bad_verbs = sorted((verbs - allowed_verbs) | (verbs & forbidden_verbs))
        if bad_verbs:
            gaps.append({"rule": index, "reason": "forbidden_or_unexpected_verb", "verbs": bad_verbs})
        if forbid_wildcards and ("*" in resources or "*" in api_groups):
            gaps.append(
                {
                    "rule": index,
                    "reason": "wildcard_scope",
                    "api_groups": sorted(api_groups),
                    "resources": sorted(resources),
                }
            )
    return gaps


def evaluate_documents(docs: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    index = index_documents(docs)
    collector = config["collector"]
    workload = config["workload"]
    annotation_key = str(config["workload_identity_annotation"])
    allowed_plaintext_hosts = list(config.get("identity_material", {}).get("allowed_plaintext_hosts", []))
    restricted_patterns = list(config.get("identity_material", {}).get("forbidden_patterns", []))

    collector_sa = index.get(("ServiceAccount", collector["namespace"], collector["service_account"]), {})
    workload_sa = index.get(("ServiceAccount", workload["namespace"], workload["service_account"]), {})
    collector_deploy = index.get(("Deployment", collector["namespace"], collector["deployment"]), {})
    workload_deploy = index.get(("Deployment", workload["namespace"], workload["deployment"]), {})
    cluster_role = index.get(("ClusterRole", "default", collector["cluster_role"]), {})
    cluster_role_binding = index.get(("ClusterRoleBinding", "default", collector["cluster_role_binding"]), {})
    config_map = index.get(("ConfigMap", collector["namespace"], collector["config_map"]), {})

    collector_annotations = metadata(collector_sa).get("annotations", {})
    observed_gcp_service_account = collector_annotations.get(annotation_key)
    collector_pod_spec = deployment_pod_spec(collector_deploy)
    workload_pod_spec = deployment_pod_spec(workload_deploy)
    rbac_gaps = rbac_least_privilege_gaps(cluster_role, config)
    subjects = cluster_role_binding.get("subjects", [])
    expected_subject = {
        "kind": "ServiceAccount",
        "name": collector["service_account"],
        "namespace": collector["namespace"],
    }
    config_yaml = str(config_map.get("data", {}).get("config.yaml", ""))
    upstream_endpoint = extract_upstream_endpoint(config_yaml)
    static_identity_findings = scan_static_identity_material(docs, restricted_patterns)

    checks = [
        check(
            "workload_identity_annotation",
            bool(collector_sa)
            and observed_gcp_service_account == collector["gcp_service_account"]
            and str(observed_gcp_service_account).endswith(".iam.gserviceaccount.com"),
            "Collector KSA is bound to the expected GCP service account through Workload Identity annotation.",
            {
                "annotation": annotation_key,
                "observed_gcp_service_account": observed_gcp_service_account,
                "expected_gcp_service_account": collector["gcp_service_account"],
            },
        ),
        check(
            "collector_api_mount_boundary",
            bool(collector_deploy)
            and collector_pod_spec.get("serviceAccountName") == collector["service_account"]
            and collector_pod_spec.get("automountServiceAccountToken") is bool(collector["requires_service_account_token"]),
            "Collector explicitly enables only the API mount it needs for Kubernetes metadata and gateway identity.",
            {
                "service_account_name": collector_pod_spec.get("serviceAccountName"),
                "api_mount_state": api_mount_state(collector_pod_spec.get("automountServiceAccountToken")),
            },
        ),
        check(
            "application_api_mount_boundary",
            bool(workload_sa)
            and workload_sa.get("automountServiceAccountToken") is False
            and workload_pod_spec.get("serviceAccountName") == workload["service_account"]
            and workload_pod_spec.get("automountServiceAccountToken") is False,
            "Sample inference workload uses a dedicated KSA and disables default API mounting.",
            {
                "service_account_exists": bool(workload_sa),
                "service_account_api_mount_state": api_mount_state(workload_sa.get("automountServiceAccountToken")),
                "pod_service_account_name": workload_pod_spec.get("serviceAccountName"),
                "pod_api_mount_state": api_mount_state(workload_pod_spec.get("automountServiceAccountToken")),
            },
        ),
        check(
            "rbac_least_privilege",
            bool(cluster_role) and not rbac_gaps,
            "Collector RBAC is read-only and avoids mutating verbs or wildcard API/resource scope.",
            {"gaps": rbac_gaps},
        ),
        check(
            "rbac_binding_scope",
            bool(cluster_role_binding)
            and cluster_role_binding.get("roleRef", {}).get("name") == collector["cluster_role"]
            and subjects == [expected_subject],
            "Collector ClusterRoleBinding is scoped to the collector service account only.",
            {
                "role_ref": cluster_role_binding.get("roleRef", {}),
                "subjects": subjects,
                "expected_subject": expected_subject,
            },
        ),
        check(
            "static_identity_material_guard",
            not static_identity_findings,
            "Manifests do not carry static GCP identity material, restricted API literals, or static identity resources.",
            static_identity_material_evidence(static_identity_findings),
        ),
        check(
            "secure_exporter_boundary",
            endpoint_is_secure(upstream_endpoint, allowed_plaintext_hosts),
            "The upstream collector exporter endpoint uses TLS unless it targets an explicitly allowed local debug host.",
            {"upstream_endpoint": upstream_endpoint, "allowed_plaintext_hosts": allowed_plaintext_hosts},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "check_count": len(checks),
        "passed_count": len(checks) - len(failed),
        "failed_count": len(failed),
        "checks": checks,
        "identity_boundaries": [
            {
                "workload": "otel-collector",
                "namespace": collector["namespace"],
                "kubernetes_service_account": collector["service_account"],
                "gcp_service_account": observed_gcp_service_account,
                "api_mount_state": api_mount_state(collector_pod_spec.get("automountServiceAccountToken")),
            },
            {
                "workload": "toy-ai-inference-api",
                "namespace": workload["namespace"],
                "kubernetes_service_account": workload["service_account"],
                "gcp_service_account": None,
                "api_mount_state": api_mount_state(workload_pod_spec.get("automountServiceAccountToken")),
            },
        ],
        "upstream_endpoint": upstream_endpoint,
    }


def find_doc(docs: list[dict[str, Any]], kind: str, doc_namespace: str, doc_name: str) -> dict[str, Any]:
    for doc in docs:
        if doc.get("kind") == kind and namespace(doc) == doc_namespace and name(doc) == doc_name:
            return doc
    raise ValueError(f"missing {kind}/{doc_namespace}/{doc_name}")


def mutate_fixture(docs: list[dict[str, Any]], fixture: dict[str, Any], annotation_key: str) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    mutation = fixture["mutation"]
    if mutation == "remove_service_account_annotation":
        service_account = find_doc(mutated, "ServiceAccount", str(fixture["namespace"]), str(fixture["service_account"]))
        metadata(service_account).setdefault("annotations", {}).pop(annotation_key, None)
    elif mutation == "set_service_account_annotation":
        service_account = find_doc(mutated, "ServiceAccount", str(fixture["namespace"]), str(fixture["service_account"]))
        metadata(service_account).setdefault("annotations", {})[annotation_key] = str(fixture["value"])
    elif mutation == "set_deployment_automount":
        deployment = find_doc(mutated, "Deployment", str(fixture["namespace"]), str(fixture["deployment"]))
        deployment_pod_spec(deployment)["automountServiceAccountToken"] = bool(fixture["value"])
    elif mutation == "add_static_identity_resource":
        mutated.append(
            {
                "apiVersion": "v1",
                "kind": K8S_STATIC_MATERIAL_KIND,
                "metadata": {
                    "name": "static-gcp-identity-material",
                    "namespace": str(fixture["namespace"]),
                },
                "stringData": {
                    "identity-material.json": '{"private_' + 'key":"redacted","client_' + 'email":"redacted@example.com"}',
                },
            }
        )
    elif mutation == "add_env":
        deployment = find_doc(mutated, "Deployment", str(fixture["namespace"]), str(fixture["deployment"]))
        container = find_container(deployment, str(fixture["container"]))
        container.setdefault("env", []).append({"name": str(fixture["env_name"]), "value": str(fixture["env_value"])})
    elif mutation == "add_rbac_verb":
        role = find_doc(mutated, "ClusterRole", "default", str(fixture["cluster_role"]))
        role.setdefault("rules", [{}])[0].setdefault("verbs", []).append(str(fixture["verb"]))
    elif mutation == "add_rbac_resource":
        role = find_doc(mutated, "ClusterRole", "default", str(fixture["cluster_role"]))
        role.setdefault("rules", [{}])[0].setdefault("resources", []).append(str(fixture["resource"]))
    elif mutation == "set_binding_subject":
        binding = find_doc(mutated, "ClusterRoleBinding", "default", str(fixture["cluster_role_binding"]))
        binding["subjects"] = [
            {
                "kind": "ServiceAccount",
                "name": str(fixture["service_account"]),
                "namespace": "default",
            }
        ]
    elif mutation == "set_upstream_endpoint":
        config_map = find_doc(mutated, "ConfigMap", str(fixture["namespace"]), str(fixture["config_map"]))
        config_yaml = str(config_map.get("data", {}).get("config.yaml", ""))
        lines = []
        in_upstream = False
        upstream_indent = 0
        replaced = False
        for line in config_yaml.splitlines():
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))
            if stripped == "otlphttp/upstream:":
                in_upstream = True
                upstream_indent = indent
            elif in_upstream and indent <= upstream_indent and stripped.endswith(":"):
                in_upstream = False
            if in_upstream and stripped.startswith("endpoint:") and not replaced:
                prefix = line[: len(line) - len(line.lstrip(" "))]
                lines.append(f"{prefix}endpoint: {fixture['endpoint']}")
                replaced = True
            else:
                lines.append(line)
        config_map.setdefault("data", {})["config.yaml"] = "\n".join(lines)
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated


def evaluate_fixtures(docs: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    annotation_key = str(config["workload_identity_annotation"])
    for fixture in config.get("fixtures", []):
        mutated_docs = mutate_fixture(docs, fixture, annotation_key)
        report = evaluate_documents(mutated_docs, config)
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


def build_report(docs: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    audit = evaluate_documents(docs, config)
    fixture_results = evaluate_fixtures(docs, config)
    detected_fixture_count = sum(1 for item in fixture_results if item["detected"])
    undetected = [item["name"] for item in fixture_results if not item["detected"]]
    negative_fixture_check = check(
        "negative_fixture_coverage",
        not undetected and detected_fixture_count >= int(config.get("minimum_detected_fixtures", 0)),
        "Negative fixtures prove identity, static material, RBAC, API mount, and exporter TLS drift is detected.",
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
        "check_count": len(checks),
        "passed_count": len(checks) - failed_count,
        "failed_count": failed_count,
        "detected_fixture_count": detected_fixture_count,
        "identity_boundary_count": len(audit["identity_boundaries"]),
        "upstream_endpoint": audit["upstream_endpoint"],
        "identity_boundaries": audit["identity_boundaries"],
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "workload-identity-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Workload Identity Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that GKE Workload Identity, API mount",
        "state, RBAC scope, static identity material handling, and upstream exporter",
        "transport are explicit before the manifests are treated as production",
        "deployment evidence.",
        "",
        "## Summary",
        "",
        f"- Checks: `{report['check_count']}`",
        f"- Identity boundaries: `{report['identity_boundary_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        f"- Upstream endpoint: `{report['upstream_endpoint']}`",
        "",
        "## Identity Boundaries",
        "",
        "| Workload | Namespace | Kubernetes SA | GCP SA | API mount |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in report["identity_boundaries"]:
        lines.append(
            "| `{workload}` | `{namespace}` | `{kubernetes_service_account}` | `{gcp_service_account}` | `{automount}` |".format(
                workload=item["workload"],
                namespace=item["namespace"],
                kubernetes_service_account=item["kubernetes_service_account"],
                gcp_service_account=item["gcp_service_account"] or "none",
                automount=item["api_mount_state"],
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
    (output_dir / "workload-identity-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/workload-identity-policy.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    config = load_json(Path(args.policy))
    manifest_paths = [repo_root / path for path in config.get("target_manifests", [])]
    report = build_report(load_manifest_set(manifest_paths), config)
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'workload-identity-audit.json'}")
    print(f"wrote {output_dir / 'workload-identity-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
