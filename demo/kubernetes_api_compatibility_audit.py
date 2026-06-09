#!/usr/bin/env python3
"""Audit Kubernetes API version compatibility and optional CRD boundaries."""

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
APPLY_RE = re.compile(r'kubectl apply -f "\$\{repo_root\}/([^"]+)"')


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("ruby is required to parse Kubernetes YAML manifests for the compatibility audit")
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


def optional_crd_kinds(policy: dict[str, Any]) -> set[str]:
    return {str(item["kind"]) for item in policy.get("optional_crds", [])}


def optional_crd_by_kind(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["kind"]): item for item in policy.get("optional_crds", [])}


def resource_summary(doc: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": doc.get("_source_path"),
        "apiVersion": doc.get("apiVersion"),
        "kind": doc.get("kind"),
        "namespace": namespace(doc),
        "name": name(doc),
        "resource": resource_key(doc),
        "optional_crd": str(doc.get("kind", "")) in optional_crd_kinds(policy),
    }


def extract_apply_order(script_text: str) -> list[str]:
    return APPLY_RE.findall(script_text)


def ordered_subset(sequence: list[str], expected: list[str]) -> bool:
    indexes = []
    for item in expected:
        if item not in sequence:
            return False
        indexes.append(sequence.index(item))
    return indexes == sorted(indexes)


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any], kind_smoke_text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    resources = [resource_summary(doc, policy) for doc in docs]
    required_versions = {str(kind): str(api) for kind, api in policy.get("required_api_versions", {}).items()}
    forbidden_versions = set(str(item) for item in policy.get("forbidden_api_versions", []))
    optional_by_kind = optional_crd_by_kind(policy)
    optional_kinds = set(optional_by_kind)
    version_gaps = []
    optional_gaps = []

    for doc in docs:
        kind = str(doc.get("kind", ""))
        api_version = str(doc.get("apiVersion", ""))
        expected = required_versions.get(kind)
        if api_version in forbidden_versions:
            version_gaps.append(
                {
                    "resource": resource_key(doc),
                    "observed": api_version,
                    "reason": "forbidden_api_version",
                }
            )
        if kind in optional_kinds:
            continue
        if expected and api_version != expected:
            version_gaps.append(
                {
                    "resource": resource_key(doc),
                    "observed": api_version,
                    "expected": expected,
                    "reason": "kind_api_mismatch",
                }
            )

    for optional in policy.get("optional_crds", []):
        kind = str(optional["kind"])
        expected_api = str(optional["api_version"])
        matches = [doc for doc in docs if doc.get("kind") == kind]
        if not matches:
            optional_gaps.append({"kind": kind, "reason": "missing_optional_crd_manifest"})
            continue
        for doc in matches:
            if doc.get("apiVersion") != expected_api:
                optional_gaps.append(
                    {
                        "kind": kind,
                        "resource": resource_key(doc),
                        "observed": doc.get("apiVersion"),
                        "expected": expected_api,
                        "reason": "optional_crd_api_mismatch",
                    }
                )
        api_group = str(optional["api_group"])
        if f"kubectl api-resources --api-group={api_group}" not in kind_smoke_text:
            optional_gaps.append({"kind": kind, "api_group": api_group, "reason": "missing_api_resource_probe"})
        skip_text = str(optional["skip_text"])
        if skip_text not in kind_smoke_text:
            optional_gaps.append({"kind": kind, "reason": "missing_skip_message"})

    admission_policies = [doc for doc in docs if doc.get("kind") == "ValidatingAdmissionPolicy"]
    admission_bindings = [doc for doc in docs if doc.get("kind") == "ValidatingAdmissionPolicyBinding"]
    admission_gaps = []
    for doc in admission_policies:
        if doc.get("apiVersion") != "admissionregistration.k8s.io/v1":
            admission_gaps.append({"resource": resource_key(doc), "reason": "policy_api_not_v1", "apiVersion": doc.get("apiVersion")})
        if doc.get("spec", {}).get("failurePolicy") != "Fail":
            admission_gaps.append({"resource": resource_key(doc), "reason": "failure_policy_not_fail"})
        rules = doc.get("spec", {}).get("matchConstraints", {}).get("resourceRules", [])
        if not any("v1" in item.get("apiVersions", []) for item in rules if isinstance(item, dict)):
            admission_gaps.append({"resource": resource_key(doc), "reason": "missing_v1_match_constraint"})
    for doc in admission_bindings:
        if doc.get("apiVersion") != "admissionregistration.k8s.io/v1":
            admission_gaps.append({"resource": resource_key(doc), "reason": "binding_api_not_v1", "apiVersion": doc.get("apiVersion")})
        if "Deny" not in doc.get("spec", {}).get("validationActions", []):
            admission_gaps.append({"resource": resource_key(doc), "reason": "binding_not_deny"})

    apply_order = extract_apply_order(kind_smoke_text)
    expected_order = list(policy.get("required_core_apply_order", []))
    missing_apply_steps = [path for path in expected_order if path not in apply_order]
    order_ok = ordered_subset(apply_order, expected_order)
    core_docs = [doc for doc in docs if doc.get("kind") not in optional_kinds]
    optional_docs = [doc for doc in docs if doc.get("kind") in optional_kinds]
    checks = [
        check(
            "document_inventory",
            len(docs) >= int(policy.get("minimum_document_count", 0)),
            "All configured Kubernetes manifest documents are parseable and present.",
            {"document_count": len(docs), "minimum_document_count": policy.get("minimum_document_count")},
        ),
        check(
            "stable_core_api_versions",
            not version_gaps and len(core_docs) >= int(policy.get("minimum_stable_resource_count", 0)),
            "Core Kubernetes resources use stable API versions and avoid removed beta API groups.",
            {
                "stable_resource_count": len(core_docs),
                "minimum_stable_resource_count": policy.get("minimum_stable_resource_count"),
                "version_gaps": version_gaps,
            },
        ),
        check(
            "optional_crd_boundary",
            not optional_gaps and len(optional_docs) >= int(policy.get("minimum_optional_crd_count", 0)),
            "Optional OpenTelemetry and Prometheus CRDs stay guarded by kind smoke API-resource probes and skip paths.",
            {
                "optional_crd_count": len(optional_docs),
                "minimum_optional_crd_count": policy.get("minimum_optional_crd_count"),
                "optional_gaps": optional_gaps,
            },
        ),
        check(
            "admission_policy_api",
            not admission_gaps and len(admission_policies) == 1 and len(admission_bindings) == 1,
            "Admission policy manifests use admissionregistration.k8s.io/v1 and fail closed with Deny bindings.",
            {
                "policy_count": len(admission_policies),
                "binding_count": len(admission_bindings),
                "admission_gaps": admission_gaps,
            },
        ),
        check(
            "kind_smoke_contract",
            not missing_apply_steps and order_ok,
            "The kind smoke path applies core manifests in dependency order before rollout checks.",
            {
                "apply_order": apply_order,
                "required_core_apply_order": expected_order,
                "missing_apply_steps": missing_apply_steps,
            },
        ),
    ]
    metrics = {
        "document_count": len(docs),
        "stable_resource_count": len(core_docs),
        "optional_crd_count": len(optional_docs),
        "admission_policy_count": len(admission_policies),
        "admission_binding_count": len(admission_bindings),
        "core_apply_step_count": len([path for path in expected_order if path in apply_order]),
        "resources": resources,
    }
    return checks, metrics


def find_doc(docs: list[dict[str, Any]], kind: str, doc_name: str) -> dict[str, Any]:
    for doc in docs:
        if doc.get("kind") == kind and name(doc) == doc_name:
            return doc
    raise ValueError(f"missing {kind}/{doc_name}")


def apply_fixture(
    docs: list[dict[str, Any]],
    kind_smoke_text: str,
    fixture: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    mutated_docs = copy.deepcopy(docs)
    mutated_script = str(kind_smoke_text)
    mutation = fixture.get("mutation")
    if mutation == "set_api_version":
        doc = find_doc(mutated_docs, str(fixture["kind"]), str(fixture["resource_name"]))
        doc["apiVersion"] = fixture.get("value")
    elif mutation == "set_binding_validation_action":
        doc = find_doc(mutated_docs, "ValidatingAdmissionPolicyBinding", "gke-ai-inference-reliability-deployments")
        doc.setdefault("spec", {})["validationActions"] = [fixture.get("value")]
    elif mutation == "set_admission_failure_policy":
        doc = find_doc(mutated_docs, "ValidatingAdmissionPolicy", "gke-ai-inference-reliability-deployments")
        doc.setdefault("spec", {})["failurePolicy"] = fixture.get("value")
    elif mutation == "remove_text":
        mutated_script = mutated_script.replace(str(fixture.get("text", "")), "")
    elif mutation == "remove_apply":
        path = str(fixture.get("path", ""))
        lines = [line for line in mutated_script.splitlines() if path not in line]
        mutated_script = "\n".join(lines) + "\n"
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated_docs, mutated_script


def evaluate_fixtures(docs: list[dict[str, Any]], policy: dict[str, Any], kind_smoke_text: str) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_docs, mutated_script = apply_fixture(docs, kind_smoke_text, fixture)
        checks, _ = evaluate_documents(mutated_docs, policy, mutated_script)
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
    kind_smoke_path = repo_root / str(policy.get("kind_smoke_script", "scripts/kind-smoke.sh"))
    kind_smoke_text = kind_smoke_path.read_text(encoding="utf-8")
    checks, metrics = evaluate_documents(docs, policy, kind_smoke_text)
    fixtures = evaluate_fixtures(docs, policy, kind_smoke_text)
    detected_fixture_count = sum(1 for item in fixtures if item["detected"])
    checks.append(
        check(
            "negative_fixture_coverage",
            detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
            "Negative fixtures prove beta API drift, optional CRD skip drift, and fail-open admission drift are detected.",
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
        "stable_resource_count": metrics["stable_resource_count"],
        "optional_crd_count": metrics["optional_crd_count"],
        "admission_policy_count": metrics["admission_policy_count"],
        "admission_binding_count": metrics["admission_binding_count"],
        "core_apply_step_count": metrics["core_apply_step_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "resources": metrics["resources"],
        "checks": checks,
        "fixture_results": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "kubernetes-api-compatibility-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Kubernetes API Compatibility Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit verifies that the GKE-shaped manifests use stable",
        "Kubernetes API versions, keep optional OpenTelemetry and Prometheus",
        "CRDs behind kind-smoke skip paths, and keep the admission policy on",
        "the v1 fail-closed API surface.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Documents | {report['document_count']} |",
        f"| Stable core resources | {report['stable_resource_count']} |",
        f"| Optional CRDs | {report['optional_crd_count']} |",
        f"| Admission policies | {report['admission_policy_count']} |",
        f"| Admission bindings | {report['admission_binding_count']} |",
        f"| Core apply steps | {report['core_apply_step_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {item['status'].upper()} |")
    lines.extend(["", "## Resources", "", "| Resource | API version | Optional CRD |", "| --- | --- | --- |"])
    for item in report["resources"]:
        lines.append(
            f"| `{item['resource']}` | `{item['apiVersion']}` | {'yes' if item['optional_crd'] else 'no'} |"
        )
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Expected Failed Check | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item['expected_failed_check']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    (output_dir / "kubernetes-api-compatibility-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/kubernetes-api-compatibility-policy.json")
    parser.add_argument("--output-dir", default="out/kubernetes-api-compatibility-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'kubernetes-api-compatibility-audit.json'}")
    print(f"wrote {output_dir / 'kubernetes-api-compatibility-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
