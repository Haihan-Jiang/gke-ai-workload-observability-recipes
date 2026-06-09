#!/usr/bin/env python3
"""Audit ConfigMap-to-Deployment rollout binding for collector config."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_yaml_text(text: str) -> Any:
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("ruby is required to parse Kubernetes YAML manifests for the audit")
    script = "require 'yaml'; require 'json'; puts JSON.generate(YAML.load_stream(STDIN.read))"
    result = subprocess.run(
        [ruby, "-e", script],
        input=text,
        text=True,
        check=True,
        capture_output=True,
    )
    docs = json.loads(result.stdout)
    if len(docs) == 1:
        return docs[0]
    return docs


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    docs = parse_yaml_text(path.read_text(encoding="utf-8"))
    if not isinstance(docs, list):
        docs = [docs]
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


def pod_template(deployment: dict[str, Any]) -> dict[str, Any]:
    value = deployment.get("spec", {}).get("template", {})
    return value if isinstance(value, dict) else {}


def pod_metadata(deployment: dict[str, Any]) -> dict[str, Any]:
    value = pod_template(deployment).get("metadata", {})
    return value if isinstance(value, dict) else {}


def pod_spec(deployment: dict[str, Any]) -> dict[str, Any]:
    value = pod_template(deployment).get("spec", {})
    return value if isinstance(value, dict) else {}


def containers(deployment: dict[str, Any]) -> list[dict[str, Any]]:
    value = pod_spec(deployment).get("containers", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def find_container(deployment: dict[str, Any], container_name: str) -> dict[str, Any]:
    for container in containers(deployment):
        if container.get("name") == container_name:
            return container
    return {}


def volume_for_config_map(deployment: dict[str, Any], config_map_name: str) -> dict[str, Any]:
    for volume in pod_spec(deployment).get("volumes", []):
        if not isinstance(volume, dict):
            continue
        if volume.get("configMap", {}).get("name") == config_map_name:
            return volume
    return {}


def config_mount(container: dict[str, Any], volume_name: str) -> dict[str, Any]:
    for mount in container.get("volumeMounts", []):
        if isinstance(mount, dict) and mount.get("name") == volume_name:
            return mount
    return {}


def config_text(config_map: dict[str, Any], policy: dict[str, Any]) -> str:
    key = policy["collector"]["config_key"]
    value = config_map.get("data", {}).get(key, "")
    return value if isinstance(value, str) else ""


def config_hash(config_map: dict[str, Any], policy: dict[str, Any]) -> str:
    return hashlib.sha256(config_text(config_map, policy).encode()).hexdigest()


def parsed_collector_config(config_map: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    raw = config_text(config_map, policy)
    if not raw:
        return {}
    parsed = parse_yaml_text(raw)
    return parsed if isinstance(parsed, dict) else {}


def inline_config_markers(raw: str, policy: dict[str, Any]) -> list[str]:
    lowered = raw.lower()
    return sorted(marker for marker in policy["collector"]["forbidden_inline_markers"] if marker.lower() in lowered)


def label_gaps(config_map: dict[str, Any], deployment: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    for kind, doc in (("ConfigMap", config_map), ("Deployment", deployment)):
        labels = metadata(doc).get("labels", {}) if doc else {}
        missing = [label for label in policy.get("required_labels", []) if label not in labels]
        if missing:
            gaps.append({"kind": kind, "missing": missing})
    return gaps


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    collector = policy["collector"]
    index = index_documents(docs)
    config_map = index.get(("ConfigMap", collector["namespace"], collector["config_map"]), {})
    deployment = index.get(("Deployment", collector["namespace"], collector["deployment"]), {})
    container = find_container(deployment, collector["container"])
    volume = volume_for_config_map(deployment, collector["config_map"])
    mount = config_mount(container, str(volume.get("name", ""))) if volume else {}
    raw_config = config_text(config_map, policy)
    parsed_config = parsed_collector_config(config_map, policy)
    expected_hash = config_hash(config_map, policy) if raw_config else ""
    annotations = pod_metadata(deployment).get("annotations", {}) if deployment else {}
    observed_hash = annotations.get(collector["checksum_annotation"])
    required_sections = set(collector["required_top_level_sections"])
    present_sections = set(parsed_config.keys())
    inline_markers = inline_config_markers(raw_config, policy)
    labels_missing = label_gaps(config_map, deployment, policy)

    schema_gaps = []
    if not config_map:
        schema_gaps.append({"reason": "missing_config_map", "config_map": collector["config_map"]})
    if not raw_config:
        schema_gaps.append({"reason": "missing_config_key", "key": collector["config_key"]})
    missing_sections = sorted(required_sections - present_sections)
    if missing_sections:
        schema_gaps.append({"reason": "missing_top_level_sections", "missing": missing_sections})

    checksum_gap = None
    if not observed_hash or observed_hash != expected_hash:
        checksum_gap = {
            "annotation": collector["checksum_annotation"],
            "observed": observed_hash,
            "expected": expected_hash,
        }

    path_gaps = []
    args = [str(item) for item in container.get("args", [])] if container else []
    if collector["required_config_arg"] not in args:
        path_gaps.append({"reason": "missing_required_arg", "expected": collector["required_config_arg"], "args": args})
    if volume.get("name") != collector["config_volume_name"]:
        path_gaps.append({"reason": "missing_config_volume", "expected": collector["config_volume_name"]})
    if mount.get("mountPath") != collector["config_mount_path"]:
        path_gaps.append({"reason": "missing_config_mount", "expected": collector["config_mount_path"], "mount": mount})

    mount_gaps = []
    if mount.get("readOnly") is not True:
        mount_gaps.append({"reason": "config_mount_must_be_read_only", "mount": mount})

    checks = [
        check(
            "config_map_schema",
            not schema_gaps,
            "Collector ConfigMap exists, exposes config.yaml, and keeps required top-level collector sections.",
            {"gaps": schema_gaps, "present_sections": sorted(present_sections)},
        ),
        check(
            "checksum_rollout_binding",
            checksum_gap is None,
            "Deployment pod template checksum annotation matches the current collector ConfigMap content.",
            {"gap": checksum_gap},
        ),
        check(
            "config_path_alignment",
            not path_gaps,
            "Collector container args, ConfigMap volume, and mount path point at the same config file.",
            {"gaps": path_gaps},
        ),
        check(
            "config_volume_mount_safety",
            not mount_gaps,
            "Collector config is mounted read-only so runtime cannot mutate the reviewed config artifact.",
            {"gaps": mount_gaps},
        ),
        check(
            "config_inline_value_hygiene",
            not inline_markers,
            "Collector config does not embed restricted inline literals.",
            {"marker_count": len(inline_markers)},
        ),
        check(
            "config_label_governance",
            not labels_missing,
            "ConfigMap and Deployment carry owner labels used by review and policy tooling.",
            {"gaps": labels_missing},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "config_map_count": 1 if config_map else 0,
        "deployment_count": 1 if deployment else 0,
        "checksum_annotation_count": 1 if observed_hash else 0,
        "read_only_config_mount_count": 1 if mount.get("readOnly") is True else 0,
        "inline_marker_count": len(inline_markers),
        "check_count": len(checks),
        "failed_count": len(failed),
        "config_hash": expected_hash,
        "observed_checksum": observed_hash,
        "checks": checks,
    }


def find_doc(docs: list[dict[str, Any]], kind: str, doc_namespace: str, doc_name: str) -> dict[str, Any]:
    for doc in docs:
        if doc.get("kind") == kind and namespace(doc) == doc_namespace and name(doc) == doc_name:
            return doc
    raise ValueError(f"missing {kind}/{doc_namespace}/{doc_name}")


def set_config_arg(container: dict[str, Any], expected_arg: str, value: str) -> None:
    args = [str(item) for item in container.setdefault("args", [])]
    if expected_arg in args:
        args[args.index(expected_arg)] = value
    else:
        args.append(value)
    container["args"] = args


def mutate_fixture(docs: list[dict[str, Any]], policy: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    collector = policy["collector"]
    mutation = fixture["mutation"]
    if mutation == "remove_config_map":
        return [
            doc
            for doc in mutated
            if not (
                doc.get("kind") == "ConfigMap"
                and namespace(doc) == collector["namespace"]
                and name(doc) == collector["config_map"]
            )
        ]

    config_map = find_doc(mutated, "ConfigMap", collector["namespace"], collector["config_map"])
    deployment = find_doc(mutated, "Deployment", collector["namespace"], collector["deployment"])
    container = find_container(deployment, collector["container"])
    if mutation == "remove_config_key":
        config_map.setdefault("data", {}).pop(collector["config_key"], None)
    elif mutation == "remove_checksum_annotation":
        pod_metadata(deployment).setdefault("annotations", {}).pop(collector["checksum_annotation"], None)
    elif mutation == "set_checksum_annotation":
        pod_metadata(deployment).setdefault("annotations", {})[collector["checksum_annotation"]] = str(fixture["value"])
    elif mutation == "append_config_comment":
        config_map.setdefault("data", {})[collector["config_key"]] = (
            config_text(config_map, policy).rstrip() + "\n" + str(fixture["comment"]) + "\n"
        )
    elif mutation == "set_config_mount_read_only":
        volume = volume_for_config_map(deployment, collector["config_map"])
        mount = config_mount(container, str(volume.get("name", "")))
        mount["readOnly"] = fixture["value"]
    elif mutation == "set_config_arg":
        set_config_arg(container, collector["required_config_arg"], str(fixture["value"]))
    elif mutation == "remove_config_map_label":
        metadata(config_map).setdefault("labels", {}).pop(str(fixture["label"]), None)
    elif mutation == "remove_deployment_label":
        metadata(deployment).setdefault("labels", {}).pop(str(fixture["label"]), None)
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
        "Negative fixtures prove checksum, config path, mount safety, inline value hygiene, and label drift is detected.",
        {"fixture_count": len(fixture_results), "detected_fixture_count": detected_fixture_count, "undetected": undetected},
    )
    checks = audit["checks"] + [negative_fixture_check]
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "config_map_count": audit["config_map_count"],
        "deployment_count": audit["deployment_count"],
        "checksum_annotation_count": audit["checksum_annotation_count"],
        "read_only_config_mount_count": audit["read_only_config_mount_count"],
        "inline_marker_count": audit["inline_marker_count"],
        "config_hash": audit["config_hash"],
        "observed_checksum": audit["observed_checksum"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "config-rollout-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Config Rollout Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit verifies that the collector ConfigMap is bound to Deployment",
        "rollouts through a pod-template checksum, that the reviewed config is",
        "mounted read-only at the path used by the collector process, and that",
        "the config does not embed restricted inline literals.",
        "",
        "## Summary",
        "",
        f"- ConfigMaps: `{report['config_map_count']}`",
        f"- Deployments: `{report['deployment_count']}`",
        f"- Checksum annotations: `{report['checksum_annotation_count']}`",
        f"- Read-only config mounts: `{report['read_only_config_mount_count']}`",
        f"- Inline markers: `{report['inline_marker_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        f"- Config hash: `{report['config_hash']}`",
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
    (output_dir / "config-rollout-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/config-rollout-policy.json")
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
    print(f"wrote {output_dir / 'config-rollout-audit.json'}")
    print(f"wrote {output_dir / 'config-rollout-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
