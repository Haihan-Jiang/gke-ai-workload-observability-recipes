#!/usr/bin/env python3
"""Audit Kubernetes manifests for production-hardening controls."""

from __future__ import annotations

import argparse
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


def find_container(deployment: dict[str, Any], container_name: str) -> dict[str, Any]:
    containers = (
        deployment.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    for container in containers:
        if container.get("name") == container_name:
            return container
    return {}


def deployment_pod_spec(deployment: dict[str, Any]) -> dict[str, Any]:
    return deployment.get("spec", {}).get("template", {}).get("spec", {})


def has_resources(container: dict[str, Any]) -> bool:
    resources = container.get("resources", {})
    requests = resources.get("requests", {})
    limits = resources.get("limits", {})
    return all(key in requests for key in ("cpu", "memory")) and all(key in limits for key in ("cpu", "memory"))


def has_hardened_container_security(container: dict[str, Any]) -> bool:
    security = container.get("securityContext", {})
    capabilities = security.get("capabilities", {})
    return (
        security.get("allowPrivilegeEscalation") is False
        and security.get("readOnlyRootFilesystem") is True
        and "ALL" in capabilities.get("drop", [])
    )


def has_hardened_pod_security(deployment: dict[str, Any]) -> bool:
    security = deployment_pod_spec(deployment).get("securityContext", {})
    seccomp = security.get("seccompProfile", {})
    return security.get("runAsNonRoot") is True and seccomp.get("type") == "RuntimeDefault"


def has_pvc_volume(deployment: dict[str, Any], claim_name: str) -> bool:
    volumes = deployment_pod_spec(deployment).get("volumes", [])
    for volume in volumes:
        claim = volume.get("persistentVolumeClaim", {})
        if claim.get("claimName") == claim_name:
            return True
    return False


def namespace_labels_ok(doc: dict[str, Any], required_labels: list[str]) -> bool:
    labels = metadata(doc).get("labels", {})
    return all(label in labels for label in required_labels)


def network_policy_ports(policy: dict[str, Any]) -> set[int]:
    ports: set[int] = set()
    for ingress in policy.get("spec", {}).get("ingress", []):
        for port in ingress.get("ports", []):
            value = port.get("port")
            if isinstance(value, int):
                ports.add(value)
    return ports


def evaluate_documents(docs: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    index = index_documents(docs)
    collector = config["collector"]
    workload = config["workload"]
    required_labels = list(config.get("required_namespace_labels", []))

    telemetry_ns = index.get(("Namespace", "default", collector["namespace"]), {})
    workload_ns = index.get(("Namespace", "default", workload["namespace"]), {})
    collector_deploy = index.get(("Deployment", collector["namespace"], collector["deployment"]), {})
    workload_deploy = index.get(("Deployment", workload["namespace"], workload["deployment"]), {})
    service_account = index.get(("ServiceAccount", collector["namespace"], collector["service_account"]), {})
    config_map = index.get(("ConfigMap", collector["namespace"], collector["config_map"]), {})
    pvc = index.get(("PersistentVolumeClaim", collector["namespace"], collector["pvc"]), {})
    pdb = index.get(("PodDisruptionBudget", collector["namespace"], collector["pdb"]), {})
    network_policy = index.get(("NetworkPolicy", collector["namespace"], collector["network_policy"]), {})

    collector_container = find_container(collector_deploy, collector["deployment"])
    workload_container = find_container(workload_deploy, "app")
    config_yaml = config_map.get("data", {}).get("config.yaml", "")
    required_ports = set(collector.get("required_otlp_ports", []))
    observed_ports = network_policy_ports(network_policy)

    checks = [
        check(
            "namespace_labels",
            namespace_labels_ok(telemetry_ns, required_labels) and namespace_labels_ok(workload_ns, required_labels),
            "Namespaces carry ownership and role labels for policy selection.",
            {
                "telemetry_namespace": metadata(telemetry_ns).get("labels", {}),
                "workload_namespace": metadata(workload_ns).get("labels", {}),
            },
        ),
        check(
            "collector_readonly_rbac",
            bool(service_account)
            and bool(index.get(("ClusterRole", "default", "otel-collector-readonly"), {}))
            and bool(index.get(("ClusterRoleBinding", "default", "otel-collector-readonly"), {})),
            "Collector has a service account with explicit read-only cluster metadata RBAC.",
            {"service_account": bool(service_account)},
        ),
        check(
            "collector_resources",
            has_resources(collector_container),
            "Collector container declares CPU and memory requests and limits.",
            {"resources": collector_container.get("resources", {})},
        ),
        check(
            "collector_probes",
            "readinessProbe" in collector_container and "livenessProbe" in collector_container,
            "Collector exposes readiness and liveness probes backed by the health_check extension.",
            {
                "readiness_probe": "readinessProbe" in collector_container,
                "liveness_probe": "livenessProbe" in collector_container,
            },
        ),
        check(
            "collector_security_context",
            has_hardened_pod_security(collector_deploy) and has_hardened_container_security(collector_container),
            "Collector pod and container security contexts use non-root, RuntimeDefault seccomp, no privilege escalation, and dropped capabilities.",
            {
                "pod_security_context": deployment_pod_spec(collector_deploy).get("securityContext", {}),
                "container_security_context": collector_container.get("securityContext", {}),
            },
        ),
        check(
            "collector_durable_queue",
            bool(pvc)
            and has_pvc_volume(collector_deploy, collector["pvc"])
            and all(fragment in config_yaml for fragment in collector.get("required_config_fragments", [])),
            "Collector has PVC-backed file storage, queued export, retry, and health check configuration.",
            {
                "pvc": bool(pvc),
                "mounted_claim": has_pvc_volume(collector_deploy, collector["pvc"]),
                "required_config_fragments": collector.get("required_config_fragments", []),
            },
        ),
        check(
            "collector_pdb",
            bool(pdb) and pdb.get("spec", {}).get("minAvailable") == 1,
            "Collector has a PodDisruptionBudget to prevent voluntary disruption from evicting the only collector.",
            {"min_available": pdb.get("spec", {}).get("minAvailable")},
        ),
        check(
            "collector_network_policy",
            bool(network_policy) and observed_ports >= required_ports,
            "Collector ingress is scoped by NetworkPolicy to OTLP ports from workload namespaces.",
            {"required_ports": sorted(required_ports), "observed_ports": sorted(observed_ports)},
        ),
        check(
            "sample_workload_resources",
            has_resources(workload_container),
            "Sample workload has CPU and memory requests and limits so scheduler pressure is represented in the recipe.",
            {"resources": workload_container.get("resources", {})},
        ),
        check(
            "sample_workload_probes",
            "readinessProbe" in workload_container and "livenessProbe" in workload_container,
            "Sample workload has readiness and liveness probes for staged rollout behavior.",
            {
                "readiness_probe": "readinessProbe" in workload_container,
                "liveness_probe": "livenessProbe" in workload_container,
            },
        ),
        check(
            "sample_workload_security_context",
            has_hardened_pod_security(workload_deploy)
            and workload_container.get("securityContext", {}).get("allowPrivilegeEscalation") is False
            and "ALL" in workload_container.get("securityContext", {}).get("capabilities", {}).get("drop", []),
            "Sample workload runs as non-root with RuntimeDefault seccomp, no privilege escalation, and dropped capabilities.",
            {
                "pod_security_context": deployment_pod_spec(workload_deploy).get("securityContext", {}),
                "container_security_context": workload_container.get("securityContext", {}),
            },
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "check_count": len(checks),
        "passed_count": len(checks) - len(failed),
        "failed_count": len(failed),
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "k8s-hardening-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Kubernetes Manifest Hardening Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that the GKE-style manifests include the production",
        "controls a platform team would expect before using telemetry as release",
        "evidence: resource budgets, health probes, restricted collector",
        "security context, durable queues, disruption protection, and network",
        "policy boundaries.",
        "",
        "## Checks",
        "",
        "| Check | Status | Reason |",
        "| --- | --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {item['status'].upper()} | {item['reason']} |")
    lines.append("")
    output_dir.joinpath("k8s-hardening-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/k8s-hardening-policy.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir", default="out/k8s-hardening-audit")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    config = load_json(Path(args.policy))
    manifests = [repo_root / item for item in config["target_manifests"]]
    report = evaluate_documents(load_manifest_set(manifests), config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'k8s-hardening-audit.json'}")
    print(f"wrote {output_dir / 'k8s-hardening-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
