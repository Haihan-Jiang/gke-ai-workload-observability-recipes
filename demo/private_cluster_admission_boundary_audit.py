#!/usr/bin/env python3
"""Audit private GKE admission boundaries for webhook/firewall drift."""

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
        raise RuntimeError("ruby is required to parse Kubernetes YAML manifests for the private cluster audit")
    script = "require 'yaml'; require 'json'; puts JSON.generate(YAML.load_stream(STDIN.read))"
    result = subprocess.run(
        [ruby, "-e", script],
        input=path.read_text(encoding="utf-8"),
        text=True,
        check=True,
        capture_output=True,
    )
    docs = json.loads(result.stdout)
    output = []
    for doc in docs:
        if isinstance(doc, dict):
            doc["_source_path"] = str(path)
            output.append(doc)
    return output


def load_manifest_set(repo_root: Path, paths: list[str]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in paths:
        docs.extend(load_yaml_documents(repo_root / path))
    return docs


def metadata(doc: dict[str, Any]) -> dict[str, Any]:
    value = doc.get("metadata", {})
    return value if isinstance(value, dict) else {}


def labels(doc: dict[str, Any]) -> dict[str, str]:
    value = metadata(doc).get("labels", {})
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def name(doc: dict[str, Any]) -> str:
    return str(metadata(doc).get("name", ""))


def namespace(doc: dict[str, Any]) -> str:
    return str(metadata(doc).get("namespace", "default"))


def resource_key(doc: dict[str, Any]) -> str:
    ns = namespace(doc)
    prefix = "" if ns == "default" else f"{ns}/"
    return f"{doc.get('kind', '')}/{prefix}{name(doc)}"


def check(name: str, ok: bool, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": PASS if ok else FAIL, "reason": reason, "evidence": evidence}


def service_ports(doc: dict[str, Any]) -> list[int]:
    ports = []
    for item in doc.get("spec", {}).get("ports", []):
        if not isinstance(item, dict):
            continue
        value = item.get("port")
        if isinstance(value, int):
            ports.append(value)
    return ports


def searchable_metadata(doc: dict[str, Any]) -> str:
    label_text = " ".join(f"{key}={value}" for key, value in labels(doc).items())
    return f"{name(doc)} {label_text}".lower()


def pattern_matches(doc: dict[str, Any], patterns: list[str]) -> list[str]:
    haystack = searchable_metadata(doc)
    return [pattern for pattern in patterns if str(pattern).lower() in haystack]


def client_config_locations(value: Any, path: str = "") -> list[str]:
    locations = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            if key == "clientConfig":
                locations.append(next_path)
            locations.extend(client_config_locations(item, next_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            locations.extend(client_config_locations(item, f"{path}[{index}]"))
    return locations


def evaluate_documents(
    docs: list[dict[str, Any]],
    policy: dict[str, Any],
    kind_smoke_text: str,
    doc_texts: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    native_kinds = set(str(item) for item in policy.get("native_admission_kinds", []))
    forbidden_webhook_kinds = set(str(item) for item in policy.get("forbidden_webhook_kinds", []))
    service_patterns = [str(item) for item in policy.get("webhook_service_name_patterns", [])]
    workload_patterns = [str(item) for item in policy.get("operator_workload_name_patterns", [])]
    forbidden_ports = set(int(item) for item in policy.get("forbidden_webhook_ports", []))

    native_admission_resources = [doc for doc in docs if doc.get("kind") in native_kinds]
    webhook_configurations = [doc for doc in docs if doc.get("kind") in forbidden_webhook_kinds]
    native_client_configs = [
        {"resource": resource_key(doc), "locations": client_config_locations(doc)}
        for doc in native_admission_resources
        if client_config_locations(doc)
    ]
    webhook_services = []
    for doc in docs:
        if doc.get("kind") != "Service":
            continue
        matches = pattern_matches(doc, service_patterns)
        if matches:
            webhook_services.append(
                {
                    "resource": resource_key(doc),
                    "matched_patterns": matches,
                    "ports": service_ports(doc),
                    "forbidden_port_hits": sorted(set(service_ports(doc)) & forbidden_ports),
                }
            )

    operator_workloads = []
    for doc in docs:
        if doc.get("kind") not in {"Deployment", "Service"}:
            continue
        matches = pattern_matches(doc, workload_patterns)
        if matches:
            operator_workloads.append({"resource": resource_key(doc), "matched_patterns": matches})

    optional_boundaries = []
    for item in policy.get("optional_operator_crds", []):
        kind = str(item["kind"])
        api_group = str(item["api_group"])
        skip_text = str(item["skip_text"])
        present = any(doc.get("kind") == kind for doc in docs)
        probe_present = f"kubectl api-resources --api-group={api_group}" in kind_smoke_text
        skip_present = skip_text in kind_smoke_text
        optional_boundaries.append(
            {
                "kind": kind,
                "api_group": api_group,
                "manifest_present": present,
                "api_resource_probe_present": probe_present,
                "skip_text_present": skip_present,
                "complete": present and probe_present and skip_present,
            }
        )

    doc_markers = []
    for marker in policy.get("private_cluster_doc_markers", []):
        path = str(marker["path"])
        text = str(marker["text"])
        doc_markers.append({"path": path, "text": text, "present": text in doc_texts.get(path, "")})

    complete_optional_boundaries = [item for item in optional_boundaries if item["complete"]]
    present_doc_markers = [item for item in doc_markers if item["present"]]
    checks = [
        check(
            "document_inventory",
            len(docs) >= int(policy.get("minimum_document_count", 0)),
            "Configured Kubernetes and admission manifests are parseable and present.",
            {"document_count": len(docs), "minimum_document_count": policy.get("minimum_document_count")},
        ),
        check(
            "native_admission_boundary",
            len(native_admission_resources) >= int(policy.get("minimum_native_admission_resource_count", 0))
            and not webhook_configurations
            and not native_client_configs,
            "Admission guardrails use native admissionregistration.k8s.io resources and avoid external webhook clientConfig dependencies.",
            {
                "native_admission_resource_count": len(native_admission_resources),
                "webhook_configuration_count": len(webhook_configurations),
                "native_client_configs": native_client_configs,
                "webhook_configurations": [resource_key(doc) for doc in webhook_configurations],
            },
        ),
        check(
            "webhook_service_boundary",
            not webhook_services and not operator_workloads,
            "Manifests avoid webhook/operator Service dependencies that private clusters would need firewall reachability for.",
            {"webhook_services": webhook_services, "operator_workloads": operator_workloads},
        ),
        check(
            "optional_operator_boundary",
            len(complete_optional_boundaries) >= int(policy.get("minimum_optional_operator_boundary_count", 0)),
            "Optional operator-backed CRDs stay behind kind smoke API-resource probes and explicit skip paths.",
            {"optional_boundaries": optional_boundaries},
        ),
        check(
            "private_cluster_docs",
            len(present_doc_markers) >= int(policy.get("minimum_private_cluster_doc_count", 0)),
            "README production guidance states the private-cluster admission boundary and no-webhook dependency.",
            {"doc_markers": doc_markers},
        ),
    ]
    metrics = {
        "document_count": len(docs),
        "native_admission_resource_count": len(native_admission_resources),
        "webhook_configuration_count": len(webhook_configurations),
        "webhook_service_count": len(webhook_services),
        "optional_operator_boundary_count": len(complete_optional_boundaries),
        "private_cluster_doc_count": len(present_doc_markers),
        "admission_resources": [resource_key(doc) for doc in native_admission_resources],
        "webhook_configurations": [resource_key(doc) for doc in webhook_configurations],
        "webhook_services": webhook_services,
        "operator_workloads": operator_workloads,
        "optional_boundaries": optional_boundaries,
        "doc_markers": doc_markers,
    }
    return checks, metrics


def webhook_configuration(kind: str) -> dict[str, Any]:
    return {
        "apiVersion": "admissionregistration.k8s.io/v1",
        "kind": kind,
        "metadata": {
            "name": "external-inference-admission-webhook",
            "labels": {"app.kubernetes.io/name": "external-inference-admission-webhook"},
        },
        "webhooks": [
            {
                "name": "inference-webhook.example.com",
                "clientConfig": {"service": {"namespace": "admission", "name": "inference-webhook"}},
                "rules": [],
                "admissionReviewVersions": ["v1"],
                "sideEffects": "None",
            }
        ],
    }


def webhook_service() -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": "inference-admission-webhook",
            "namespace": "admission",
            "labels": {"app.kubernetes.io/name": "inference-admission-webhook"},
        },
        "spec": {"ports": [{"name": "https", "port": 443, "targetPort": 9443}]},
    }


def apply_fixture(
    docs: list[dict[str, Any]],
    kind_smoke_text: str,
    doc_texts: dict[str, str],
    fixture: dict[str, Any],
) -> tuple[list[dict[str, Any]], str, dict[str, str]]:
    mutated_docs = copy.deepcopy(docs)
    mutated_script = str(kind_smoke_text)
    mutated_texts = dict(doc_texts)
    mutation = fixture.get("mutation")
    if mutation == "add_validating_webhook_configuration":
        mutated_docs.append(webhook_configuration("ValidatingWebhookConfiguration"))
    elif mutation == "add_mutating_webhook_configuration":
        mutated_docs.append(webhook_configuration("MutatingWebhookConfiguration"))
    elif mutation == "add_webhook_service":
        mutated_docs.append(webhook_service())
    elif mutation == "add_admission_client_config":
        for doc in mutated_docs:
            if doc.get("kind") == "ValidatingAdmissionPolicy":
                validations = doc.setdefault("spec", {}).setdefault("validations", [])
                if validations and isinstance(validations[0], dict):
                    validations[0]["clientConfig"] = {"url": "https://external-webhook.example.com/validate"}
                break
    elif mutation == "remove_kind_smoke_text":
        mutated_script = mutated_script.replace(str(fixture.get("text", "")), "")
    elif mutation == "remove_doc_text":
        path = str(fixture.get("path", ""))
        mutated_texts[path] = mutated_texts.get(path, "").replace(str(fixture.get("text", "")), "")
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated_docs, mutated_script, mutated_texts


def evaluate_fixtures(
    docs: list[dict[str, Any]],
    policy: dict[str, Any],
    kind_smoke_text: str,
    doc_texts: dict[str, str],
) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_docs, mutated_script, mutated_texts = apply_fixture(docs, kind_smoke_text, doc_texts, fixture)
        checks, _ = evaluate_documents(mutated_docs, policy, mutated_script, mutated_texts)
        failed_checks = [item["name"] for item in checks if item["status"] != PASS]
        expected = str(fixture.get("expected_failed_check"))
        results.append(
            {
                "name": fixture.get("name"),
                "mutation": fixture.get("mutation"),
                "expected_failed_check": expected,
                "failed_checks": failed_checks,
                "detected": expected in failed_checks,
            }
        )
    return results


def build_report(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    docs = load_manifest_set(repo_root, list(policy["target_manifests"]))
    kind_smoke_text = (repo_root / str(policy["kind_smoke_script"])).read_text(encoding="utf-8")
    doc_paths = sorted({str(marker["path"]) for marker in policy.get("private_cluster_doc_markers", [])})
    doc_texts = {path: (repo_root / path).read_text(encoding="utf-8") for path in doc_paths}
    checks, metrics = evaluate_documents(docs, policy, kind_smoke_text, doc_texts)
    fixtures = evaluate_fixtures(docs, policy, kind_smoke_text, doc_texts)
    detected_fixture_count = sum(1 for item in fixtures if item["detected"])
    checks.append(
        check(
            "negative_fixture_coverage",
            detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
            "Negative fixtures prove webhook configuration, webhook service, optional operator, and documentation drift are detected.",
            {
                "detected_fixture_count": detected_fixture_count,
                "minimum_detected_fixtures": policy.get("minimum_detected_fixtures"),
                "fixtures": fixtures,
            },
        )
    )
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "document_count": metrics["document_count"],
        "native_admission_resource_count": metrics["native_admission_resource_count"],
        "webhook_configuration_count": metrics["webhook_configuration_count"],
        "webhook_service_count": metrics["webhook_service_count"],
        "optional_operator_boundary_count": metrics["optional_operator_boundary_count"],
        "private_cluster_doc_count": metrics["private_cluster_doc_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "admission_resources": metrics["admission_resources"],
        "webhook_configurations": metrics["webhook_configurations"],
        "webhook_services": metrics["webhook_services"],
        "operator_workloads": metrics["operator_workloads"],
        "optional_boundaries": metrics["optional_boundaries"],
        "doc_markers": metrics["doc_markers"],
        "checks": checks,
        "fixture_results": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "private-cluster-admission-boundary-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Private Cluster Admission Boundary Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit verifies that private GKE clusters can use the lab's",
        "admission controls without an external admission webhook firewall",
        "dependency. It also keeps optional operator-backed CRDs behind",
        "kind-smoke API-resource probes and skip paths.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Documents | {report['document_count']} |",
        f"| Native admission resources | {report['native_admission_resource_count']} |",
        f"| Webhook configurations | {report['webhook_configuration_count']} |",
        f"| Webhook services | {report['webhook_service_count']} |",
        f"| Optional operator boundaries | {report['optional_operator_boundary_count']} |",
        f"| Private cluster doc markers | {report['private_cluster_doc_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {item['status'].upper()} |")
    lines.extend(["", "## Native Admission Resources", "", "| Resource |", "| --- |"])
    for item in report["admission_resources"]:
        lines.append(f"| `{item}` |")
    lines.extend(["", "## Optional Operator Boundaries", "", "| Kind | API group | Probe | Skip path |", "| --- | --- | --- | --- |"])
    for item in report["optional_boundaries"]:
        lines.append(
            f"| `{item['kind']}` | `{item['api_group']}` | {'yes' if item['api_resource_probe_present'] else 'no'} | {'yes' if item['skip_text_present'] else 'no'} |"
        )
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Expected Failed Check | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item['expected_failed_check']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    (output_dir / "private-cluster-admission-boundary-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/private-cluster-admission-boundary-policy.json")
    parser.add_argument("--output-dir", default="out/private-cluster-admission-boundary-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'private-cluster-admission-boundary-audit.json'}")
    print(f"wrote {output_dir / 'private-cluster-admission-boundary-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
