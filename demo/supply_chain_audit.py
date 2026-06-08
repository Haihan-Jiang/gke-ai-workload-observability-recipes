#!/usr/bin/env python3
"""Audit Kubernetes image references for digest pinning and artifact hygiene."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
DIGEST_RE = re.compile(r"@sha256:[0-9a-f]{64}$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("ruby is required to parse Kubernetes YAML manifests for the supply-chain audit")
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


def deployment_containers(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if doc.get("kind") != "Deployment":
        return []
    return (
        doc.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )


def labels_for(doc: dict[str, Any]) -> dict[str, Any]:
    labels = doc.get("metadata", {}).get("labels", {})
    return labels if isinstance(labels, dict) else {}


def collect_images(docs: list[dict[str, Any]], required_labels: list[str]) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    for doc in docs:
        deployment = str(doc.get("metadata", {}).get("name", ""))
        namespace = str(doc.get("metadata", {}).get("namespace", "default"))
        labels = labels_for(doc)
        label_missing = sorted(label for label in required_labels if label not in labels)
        for container in deployment_containers(doc):
            image = str(container.get("image", ""))
            images.append(
                {
                    "namespace": namespace,
                    "deployment": deployment,
                    "container": str(container.get("name", "")),
                    "image": image,
                    "registry": image_registry(image),
                    "tag": image_tag(image),
                    "digest_pinned": bool(DIGEST_RE.search(image)),
                    "image_pull_policy": container.get("imagePullPolicy"),
                    "missing_labels": label_missing,
                }
            )
    return images


def build_report(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    docs = load_manifest_set(repo_root, list(policy["target_manifests"]))
    images = collect_images(docs, list(policy.get("required_labels", [])))
    allowed_registries = set(policy.get("allowed_registries", []))
    forbidden_tags = set(policy.get("forbidden_tags", []))
    required_pull_policy = policy.get("required_image_pull_policy")
    unpinned = [item for item in images if not item["digest_pinned"]]
    forbidden = [item for item in images if item["tag"] in forbidden_tags]
    registry_violations = [item for item in images if item["registry"] not in allowed_registries]
    pull_policy_violations = [
        item for item in images if item["image_pull_policy"] != required_pull_policy
    ]
    label_violations = [item for item in images if item["missing_labels"]]
    checks = [
        {
            "name": "image_coverage",
            "ok": len(images) >= int(policy["minimum_images"]),
            "evidence": {"image_count": len(images)},
        },
        {
            "name": "digest_pinning",
            "ok": not unpinned if policy.get("require_digest", True) else True,
            "evidence": {"violations": unpinned},
        },
        {
            "name": "forbidden_tags",
            "ok": not forbidden,
            "evidence": {"violations": forbidden},
        },
        {
            "name": "allowed_registries",
            "ok": not registry_violations,
            "evidence": {"violations": registry_violations},
        },
        {
            "name": "pull_policy",
            "ok": not pull_policy_violations,
            "evidence": {
                "required": required_pull_policy,
                "violations": pull_policy_violations,
            },
        },
        {
            "name": "artifact_owner_labels",
            "ok": not label_violations,
            "evidence": {"violations": label_violations},
        },
    ]
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "image_count": len(images),
        "digest_pinned_count": sum(1 for item in images if item["digest_pinned"]),
        "failed_count": failed_count,
        "images": images,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "supply-chain-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Supply Chain Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks Kubernetes image references before treating the",
        "manifests as production-style deployment evidence. It requires",
        "digest-pinned images, non-floating tags, an explicit pull policy,",
        "allowed registries, and ownership labels on workload artifacts.",
        "",
        "## Images",
        "",
        "| Namespace | Deployment | Container | Image |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["images"]:
        lines.append(f"| `{item['namespace']}` | `{item['deployment']}` | `{item['container']}` | `{item['image']}` |")
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.append("")
    (output_dir / "supply-chain-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/supply-chain-policy.json")
    parser.add_argument("--output-dir", default="out/supply-chain-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'supply-chain-audit.json'}")
    print(f"wrote {output_dir / 'supply-chain-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
