#!/usr/bin/env python3
"""Audit Kubernetes admission policy coverage and simulated decisions."""

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
ALLOW = "allow"
DENY = "deny"
DIGEST_RE = re.compile(r"@sha256:[0-9a-f]{64}$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("ruby is required to parse Kubernetes YAML manifests for the admission policy audit")
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


def load_manifest_set(repo_root: Path, paths: list[str]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in paths:
        docs.extend(load_yaml_documents(repo_root / path))
    return docs


def metadata(doc: dict[str, Any]) -> dict[str, Any]:
    value = doc.get("metadata", {})
    return value if isinstance(value, dict) else {}


def deployment_name(doc: dict[str, Any]) -> str:
    return str(metadata(doc).get("name", ""))


def deployment_namespace(doc: dict[str, Any]) -> str:
    return str(metadata(doc).get("namespace", "default"))


def pod_template(doc: dict[str, Any]) -> dict[str, Any]:
    return doc.get("spec", {}).get("template", {})


def pod_spec(doc: dict[str, Any]) -> dict[str, Any]:
    return pod_template(doc).get("spec", {})


def containers(doc: dict[str, Any]) -> list[dict[str, Any]]:
    values = pod_spec(doc).get("containers", [])
    return values if isinstance(values, list) else []


def labels_for(doc: dict[str, Any]) -> dict[str, Any]:
    labels = metadata(doc).get("labels", {})
    return labels if isinstance(labels, dict) else {}


def annotations_for(doc: dict[str, Any]) -> dict[str, Any]:
    annotations = pod_template(doc).get("metadata", {}).get("annotations", {})
    return annotations if isinstance(annotations, dict) else {}


def image_registry(image: str) -> str:
    without_digest = image.split("@", 1)[0]
    if "/" not in without_digest:
        return "docker.io"
    first = without_digest.split("/", 1)[0]
    if "." in first or ":" in first or first == "localhost":
        return first
    return "docker.io"


def image_tag(image: str) -> str:
    without_digest = image.split("@", 1)[0]
    last = without_digest.rsplit("/", 1)[-1]
    if ":" not in last:
        return "latest"
    return last.rsplit(":", 1)[-1]


def control(name: str, ok: bool, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "status": PASS if ok else FAIL,
        "reason": reason,
        "evidence": evidence,
    }


def has_digest_pinned_images(doc: dict[str, Any]) -> bool:
    return all(DIGEST_RE.search(str(container.get("image", ""))) for container in containers(doc))


def has_allowed_registry(doc: dict[str, Any], policy: dict[str, Any]) -> bool:
    allowed_registries = set(policy.get("allowed_registries", []))
    forbidden_tags = set(policy.get("forbidden_tags", []))
    for container in containers(doc):
        image = str(container.get("image", ""))
        if image_registry(image) not in allowed_registries:
            return False
        if image_tag(image) in forbidden_tags:
            return False
    return True


def has_restricted_pod_security(doc: dict[str, Any]) -> bool:
    security = pod_spec(doc).get("securityContext", {})
    seccomp = security.get("seccompProfile", {})
    return security.get("runAsNonRoot") is True and seccomp.get("type") == "RuntimeDefault"


def has_restricted_container_security(doc: dict[str, Any]) -> bool:
    for container in containers(doc):
        security = container.get("securityContext", {})
        capabilities = security.get("capabilities", {})
        if security.get("privileged") is True:
            return False
        if security.get("allowPrivilegeEscalation") is not False:
            return False
        if "ALL" not in capabilities.get("drop", []):
            return False
    return True


def has_resource_budgets(doc: dict[str, Any]) -> bool:
    for container in containers(doc):
        resources = container.get("resources", {})
        requests = resources.get("requests", {})
        limits = resources.get("limits", {})
        if not all(key in requests for key in ("cpu", "memory")):
            return False
        if not all(key in limits for key in ("cpu", "memory")):
            return False
    return True


def has_health_probes(doc: dict[str, Any]) -> bool:
    return all("readinessProbe" in container and "livenessProbe" in container for container in containers(doc))


def has_required_instrumentation(doc: dict[str, Any], policy: dict[str, Any]) -> bool:
    namespaces = set(policy.get("instrumented_namespaces", []))
    if deployment_namespace(doc) not in namespaces:
        return True
    annotation = str(policy.get("instrumentation_annotation", ""))
    return annotation in annotations_for(doc)


def evaluate_deployment(doc: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    labels = labels_for(doc)
    required_part_of = str(policy.get("required_part_of_label", ""))
    deployment_controls = [
        control(
            "owner_labels",
            labels.get("app.kubernetes.io/name") is not None
            and labels.get("app.kubernetes.io/part-of") == required_part_of,
            "Deployment has owner labels used by admission selection and audit evidence.",
            {"labels": labels},
        ),
        control(
            "digest_pinned_images",
            has_digest_pinned_images(doc),
            "Every container image is pinned by sha256 digest.",
            {"images": [container.get("image") for container in containers(doc)]},
        ),
        control(
            "allowed_registry",
            has_allowed_registry(doc, policy),
            "Images come from allowed registries and avoid floating tags.",
            {
                "images": [
                    {
                        "image": container.get("image"),
                        "registry": image_registry(str(container.get("image", ""))),
                        "tag": image_tag(str(container.get("image", ""))),
                    }
                    for container in containers(doc)
                ]
            },
        ),
        control(
            "restricted_pod_security",
            has_restricted_pod_security(doc),
            "Pod template requires non-root execution and RuntimeDefault seccomp.",
            {"security_context": pod_spec(doc).get("securityContext", {})},
        ),
        control(
            "restricted_container_security",
            has_restricted_container_security(doc),
            "Containers cannot be privileged, escalate privileges, or keep capabilities.",
            {"security_contexts": [container.get("securityContext", {}) for container in containers(doc)]},
        ),
        control(
            "container_resources",
            has_resource_budgets(doc),
            "Containers declare CPU and memory requests and limits.",
            {"resources": [container.get("resources", {}) for container in containers(doc)]},
        ),
        control(
            "health_probes",
            has_health_probes(doc),
            "Containers define readiness and liveness probes.",
            {
                "probes": [
                    {
                        "container": container.get("name"),
                        "readiness": "readinessProbe" in container,
                        "liveness": "livenessProbe" in container,
                    }
                    for container in containers(doc)
                ]
            },
        ),
        control(
            "otel_instrumentation",
            has_required_instrumentation(doc, policy),
            "AI workload deployments keep OpenTelemetry instrumentation injection enabled.",
            {"annotations": annotations_for(doc), "namespace": deployment_namespace(doc)},
        ),
    ]
    failed = [item for item in deployment_controls if item["status"] != PASS]
    return {
        "namespace": deployment_namespace(doc),
        "deployment": deployment_name(doc),
        "decision": ALLOW if not failed else DENY,
        "failed_controls": [item["name"] for item in failed],
        "controls": deployment_controls,
    }


def policy_documents_by_kind(docs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(doc.get("kind", "")): doc for doc in docs}


def validate_policy_manifest(policy_docs: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    by_kind = policy_documents_by_kind(policy_docs)
    admission_policy = by_kind.get("ValidatingAdmissionPolicy", {})
    binding = by_kind.get("ValidatingAdmissionPolicyBinding", {})
    validations = admission_policy.get("spec", {}).get("validations", [])
    validation_messages = [str(item.get("message", "")) for item in validations]
    required_policy = config.get("required_policy", {})
    checks = [
        control(
            "validating_admission_policy_present",
            bool(admission_policy),
            "Native Kubernetes ValidatingAdmissionPolicy object is present.",
            {"kinds": sorted(by_kind)},
        ),
        control(
            "validating_admission_policy_binding_present",
            bool(binding),
            "Policy binding is present so the policy can enforce matching requests.",
            {"kinds": sorted(by_kind)},
        ),
        control(
            "failure_policy_fail",
            admission_policy.get("spec", {}).get("failurePolicy") == required_policy.get("failure_policy"),
            "Admission failure policy is fail-closed.",
            {"failure_policy": admission_policy.get("spec", {}).get("failurePolicy")},
        ),
        control(
            "deny_action",
            required_policy.get("validation_action") in binding.get("spec", {}).get("validationActions", []),
            "Policy binding denies invalid deployment create and update requests.",
            {"validation_actions": binding.get("spec", {}).get("validationActions", [])},
        ),
    ]
    for required_control in config.get("required_controls", []):
        fragment = str(required_control["message_fragment"])
        checks.append(
            control(
                f"control_{required_control['name']}",
                any(fragment in message for message in validation_messages),
                f"Admission policy contains the {required_control['name']} validation.",
                {"message_fragment": fragment},
            )
        )
    return checks


def deployment_by_name(docs: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for doc in docs:
        if doc.get("kind") == "Deployment" and deployment_name(doc) == name:
            return doc
    raise ValueError(f"deployment not found: {name}")


def first_container(doc: dict[str, Any]) -> dict[str, Any]:
    deployment_containers = containers(doc)
    if not deployment_containers:
        raise ValueError(f"deployment has no containers: {deployment_name(doc)}")
    return deployment_containers[0]


def build_fixture(docs: list[dict[str, Any]], mutation: str) -> dict[str, Any]:
    target_name = "toy-ai-inference-api" if mutation != "root_pod" else "otel-collector"
    fixture = copy.deepcopy(deployment_by_name(docs, target_name))
    container = first_container(fixture)
    if mutation == "missing_owner_label":
        labels_for(fixture).pop("app.kubernetes.io/part-of", None)
    elif mutation == "unpinned_image":
        container["image"] = str(container["image"]).split("@", 1)[0]
    elif mutation == "latest_tag":
        digest = str(container["image"]).split("@", 1)[1]
        container["image"] = f"python:latest@{digest}"
    elif mutation == "disallowed_registry":
        digest = str(container["image"]).split("@", 1)[1]
        container["image"] = f"ghcr.io/example/toy-ai-inference-api:1.0@{digest}"
    elif mutation == "root_pod":
        pod_spec(fixture)["securityContext"]["runAsNonRoot"] = False
    elif mutation == "privileged_container":
        container.setdefault("securityContext", {})["privileged"] = True
    elif mutation == "privilege_escalation":
        container.setdefault("securityContext", {})["allowPrivilegeEscalation"] = True
    elif mutation == "missing_resources":
        container.pop("resources", None)
    elif mutation == "missing_probes":
        container.pop("readinessProbe", None)
        container.pop("livenessProbe", None)
    elif mutation == "missing_instrumentation":
        annotations_for(fixture).pop("instrumentation.opentelemetry.io/inject-python", None)
    else:
        raise ValueError(f"unknown fixture mutation: {mutation}")
    return fixture


def build_report(repo_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    manifest_docs = load_manifest_set(repo_root, list(config["target_manifests"]))
    policy_docs = load_yaml_documents(repo_root / str(config["policy_manifest"]))
    deployments = [doc for doc in manifest_docs if doc.get("kind") == "Deployment"]
    policy_checks = validate_policy_manifest(policy_docs, config)
    current_decisions = [evaluate_deployment(doc, config) for doc in deployments]
    fixture_decisions = [
        {
            "fixture": mutation,
            **evaluate_deployment(build_fixture(deployments, mutation), config),
        }
        for mutation in config.get("fixture_mutations", [])
    ]
    failed_policy_checks = [item for item in policy_checks if item["status"] != PASS]
    denied_current = [item for item in current_decisions if item["decision"] != ALLOW]
    allowed_fixtures = [item for item in fixture_decisions if item["decision"] != DENY]
    failed_count = len(failed_policy_checks) + len(denied_current) + len(allowed_fixtures)
    allowed_deployment_count = len(current_decisions) - len(denied_current)
    denied_fixture_count = len(fixture_decisions) - len(allowed_fixtures)
    min_allowed = int(config.get("minimum_allowed_deployments", 0))
    min_denied = int(config.get("minimum_denied_fixtures", 0))
    if allowed_deployment_count < min_allowed:
        failed_count += 1
    if denied_fixture_count < min_denied:
        failed_count += 1
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "policy_manifest": str(config["policy_manifest"]),
        "policy_check_count": len(policy_checks),
        "deployment_count": len(current_decisions),
        "allowed_deployment_count": allowed_deployment_count,
        "fixture_count": len(fixture_decisions),
        "denied_fixture_count": denied_fixture_count,
        "failed_count": failed_count,
        "policy_checks": policy_checks,
        "current_decisions": current_decisions,
        "fixture_decisions": fixture_decisions,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "admission-policy-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Admission Policy Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit verifies that the lab has a Kubernetes admission policy",
        "pack for deployment guardrails and simulates admission decisions",
        "against both the committed manifests and negative fixtures. It is",
        "meant to prove the recipe can prevent later drift, not only detect",
        "drift after a manifest has already changed.",
        "",
        f"Policy manifest: `{report['policy_manifest']}`",
        "",
        "## Current Deployment Decisions",
        "",
        "| Namespace | Deployment | Decision | Failed controls |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["current_decisions"]:
        failed = ", ".join(item["failed_controls"]) or "-"
        lines.append(f"| `{item['namespace']}` | `{item['deployment']}` | `{item['decision']}` | {failed} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Decision | Failed controls |", "| --- | --- | --- |"])
    for item in report["fixture_decisions"]:
        failed = ", ".join(item["failed_controls"]) or "-"
        lines.append(f"| `{item['fixture']}` | `{item['decision']}` | {failed} |")
    lines.extend(["", "## Policy Manifest Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["policy_checks"]:
        lines.append(f"| `{item['name']}` | {item['status'].upper()} |")
    lines.append("")
    (output_dir / "admission-policy-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/admission-policy.json")
    parser.add_argument("--output-dir", default="out/admission-policy-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'admission-policy-audit.json'}")
    print(f"wrote {output_dir / 'admission-policy-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
