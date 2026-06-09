#!/usr/bin/env python3
"""Generate and audit a local SBOM inventory for third-party references."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"
ACTION_RE = re.compile(r"\buses:\s*([^\s#]+)")
IMAGE_RE = re.compile(r"\bimage:\s*['\"]?([^'\"\s#]+)")
CI_PYTHON_RE = re.compile(r"python-version:\s*['\"]?([^'\"\s#]+)")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def read_files(repo_root: Path, paths: list[str]) -> dict[str, str | None]:
    return {
        path: (repo_root / path).read_text(encoding="utf-8") if (repo_root / path).is_file() else None
        for path in sorted({str(path) for path in paths})
    }


def action_ref(value: str) -> str:
    return f"github-action:{value}"


def image_ref(value: str) -> str:
    return f"container:{value}"


def runtime_ref(name: str, version: str) -> str:
    return f"runtime:{name}@{version}"


def collect_matches(files: dict[str, str | None], paths: list[str], regex: re.Pattern[str]) -> list[dict[str, str]]:
    matches = []
    for path in paths:
        for value in regex.findall(files.get(path) or ""):
            matches.append({"path": path, "value": value})
    return matches


def discover_components(files: dict[str, str | None], policy: dict[str, Any]) -> dict[str, Any]:
    workflow_files = [str(path) for path in policy.get("workflow_files", [])]
    image_files = [str(path) for path in policy.get("image_files", [])]
    python_version_file = str(policy.get("python_version_file", ".python-version"))
    runtime_doc = str(policy.get("developer_runtime_doc", "docs/developer-runtime.md"))
    actions = collect_matches(files, workflow_files, ACTION_RE)
    images = collect_matches(files, image_files, IMAGE_RE)
    python_version = (files.get(python_version_file) or "").strip()
    ci_versions = [
        item["value"]
        for item in collect_matches(files, workflow_files, CI_PYTHON_RE)
    ]
    ruby_documented = "Ruby" in (files.get(runtime_doc) or "")
    runtime_components = []
    if python_version:
        runtime_components.append({"path": python_version_file, "value": python_version, "bom_ref": runtime_ref("python", python_version)})
    if ruby_documented:
        runtime_components.append({"path": runtime_doc, "value": "documented", "bom_ref": runtime_ref("ruby", "documented")})
    discovered_refs = [action_ref(item["value"]) for item in actions]
    discovered_refs.extend(image_ref(item["value"]) for item in images)
    discovered_refs.extend(item["bom_ref"] for item in runtime_components)
    return {
        "actions": actions,
        "images": images,
        "runtimes": runtime_components,
        "python_version": python_version,
        "ci_python_versions": ci_versions,
        "ruby_documented": ruby_documented,
        "discovered_refs": sorted(set(discovered_refs)),
    }


def component_refs(components: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("bom_ref", "")) for item in components]


def duplicate_refs(refs: list[str]) -> list[str]:
    return sorted({ref for ref in refs if refs.count(ref) > 1})


def source_path_gaps(repo_root: Path, components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps = []
    for component in components:
        source_paths = [str(path) for path in component.get("source_paths", [])]
        if not source_paths:
            gaps.append({"bom_ref": component.get("bom_ref"), "reason": "missing_source_paths"})
            continue
        for path in source_paths:
            if not (repo_root / path).is_file():
                gaps.append({"bom_ref": component.get("bom_ref"), "path": path, "reason": "missing_source_file"})
    return gaps


def build_sbom(policy: dict[str, Any]) -> dict[str, Any]:
    components = []
    for item in policy.get("expected_components", []):
        component = {
            "bom-ref": item["bom_ref"],
            "type": item["type"],
            "name": item["name"],
            "version": item["version"],
            "purl": item["purl"],
            "scope": "required",
            "properties": [
                {"name": "category", "value": item["category"]},
                {"name": "source_paths", "value": ",".join(item.get("source_paths", []))},
            ],
        }
        components.append(component)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "bom-ref": "application:gke-ai-inference-reliability-lab",
                "type": "application",
                "name": "GKE AI Inference Reliability Lab",
            }
        },
        "components": components,
    }


def evaluate(repo_root: Path, files: dict[str, str | None], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    discovery = discover_components(files, policy)
    components = list(policy.get("expected_components", []))
    refs = component_refs(components)
    duplicates = duplicate_refs(refs)
    expected_refs = set(refs)
    discovered_refs = set(discovery["discovered_refs"])
    missing_from_sbom = sorted(discovered_refs - expected_refs)
    stale_inventory = sorted(expected_refs - discovered_refs)
    source_gaps = source_path_gaps(repo_root, components)
    python_components = [item for item in components if item.get("bom_ref", "").startswith("runtime:python@")]
    ruby_components = [item for item in components if item.get("bom_ref") == "runtime:ruby@documented"]
    python_versions_match = (
        bool(discovery["python_version"])
        and set(discovery["ci_python_versions"]) == {discovery["python_version"]}
        and len(python_components) == 1
        and python_components[0].get("version") == discovery["python_version"]
    )
    ruby_boundary_ok = discovery["ruby_documented"] and len(ruby_components) == 1
    sbom = build_sbom(policy)
    sbom_refs = [str(item.get("bom-ref", "")) for item in sbom.get("components", [])]
    checks = [
        check(
            "component_discovery",
            len(discovery["actions"]) >= int(policy.get("minimum_action_count", 0))
            and len(discovery["images"]) >= int(policy.get("minimum_image_count", 0))
            and len(discovery["runtimes"]) >= int(policy.get("minimum_runtime_count", 0))
            and len(discovered_refs) >= int(policy.get("minimum_component_count", 0)),
            {
                "action_count": len(discovery["actions"]),
                "image_count": len(discovery["images"]),
                "runtime_count": len(discovery["runtimes"]),
                "discovered_component_count": len(discovered_refs),
            },
        ),
        check(
            "sbom_component_coverage",
            not missing_from_sbom and not stale_inventory and len(expected_refs) >= int(policy.get("minimum_component_count", 0)),
            {
                "missing_from_sbom": missing_from_sbom,
                "stale_inventory": stale_inventory,
                "component_count": len(expected_refs),
            },
        ),
        check(
            "cyclonedx_shape",
            sbom.get("bomFormat") == "CycloneDX"
            and sbom.get("specVersion") == "1.5"
            and not duplicates
            and not duplicate_refs(sbom_refs)
            and len(sbom_refs) == len(expected_refs),
            {
                "duplicate_policy_refs": duplicates,
                "duplicate_sbom_refs": duplicate_refs(sbom_refs),
                "sbom_component_count": len(sbom_refs),
            },
        ),
        check(
            "source_traceability",
            not source_gaps
            and sum(len(item.get("source_paths", [])) for item in components) >= int(policy.get("minimum_source_path_count", 0)),
            {
                "source_path_count": sum(len(item.get("source_paths", [])) for item in components),
                "source_gaps": source_gaps,
            },
        ),
        check(
            "runtime_boundary",
            python_versions_match and ruby_boundary_ok,
            {
                "python_version": discovery["python_version"],
                "ci_python_versions": discovery["ci_python_versions"],
                "ruby_documented": discovery["ruby_documented"],
                "python_components": python_components,
                "ruby_components": ruby_components,
            },
        ),
    ]
    metrics = {
        "component_count": len(expected_refs),
        "action_count": len(discovery["actions"]),
        "image_count": len(discovery["images"]),
        "runtime_count": len(discovery["runtimes"]),
        "source_path_count": sum(len(item.get("source_paths", [])) for item in components),
    }
    return checks, metrics, sbom


def apply_fixture(files: dict[str, str | None], policy: dict[str, Any], fixture: dict[str, Any]) -> tuple[dict[str, str | None], dict[str, Any]]:
    mutated_files = copy.deepcopy(files)
    mutated_policy = copy.deepcopy(policy)
    mutation = fixture.get("mutation")
    bom_ref = str(fixture.get("bom_ref", ""))
    if mutation == "remove_component":
        mutated_policy["expected_components"] = [
            item for item in mutated_policy.get("expected_components", []) if item.get("bom_ref") != bom_ref
        ]
    elif mutation == "set_component_bom_ref":
        for item in mutated_policy.get("expected_components", []):
            if item.get("bom_ref") == bom_ref:
                item["bom_ref"] = fixture.get("value")
    elif mutation == "clear_source_paths":
        for item in mutated_policy.get("expected_components", []):
            if item.get("bom_ref") == bom_ref:
                item["source_paths"] = []
    elif mutation == "set_component_version":
        for item in mutated_policy.get("expected_components", []):
            if item.get("bom_ref") == bom_ref:
                item["version"] = fixture.get("value")
    elif mutation == "append_text":
        path = str(fixture.get("path", ""))
        mutated_files[path] = (mutated_files.get(path) or "") + str(fixture.get("text", ""))
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated_files, mutated_policy


def evaluate_fixtures(repo_root: Path, files: dict[str, str | None], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_files, mutated_policy = apply_fixture(files, policy, fixture)
        checks, _, _ = evaluate(repo_root, mutated_files, mutated_policy)
        failed_checks = [item["name"] for item in checks if not item["ok"]]
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


def policy_paths(policy: dict[str, Any]) -> list[str]:
    paths = []
    paths.extend(policy.get("workflow_files", []))
    paths.extend(policy.get("image_files", []))
    paths.append(policy.get("python_version_file", ".python-version"))
    paths.append(policy.get("developer_runtime_doc", "docs/developer-runtime.md"))
    return [str(path) for path in paths]


def build_report(repo_root: Path, policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    files = read_files(repo_root, policy_paths(policy))
    checks, metrics, sbom = evaluate(repo_root, files, policy)
    fixtures = evaluate_fixtures(repo_root, files, policy)
    detected_fixture_count = sum(1 for item in fixtures if item["detected"])
    checks.append(
        check(
            "negative_fixture_coverage",
            detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
            {
                "detected_fixture_count": detected_fixture_count,
                "minimum_detected_fixtures": policy.get("minimum_detected_fixtures"),
                "fixtures": fixtures,
            },
        )
    )
    failed_count = sum(1 for item in checks if not item["ok"])
    report = {
        "status": PASS if failed_count == 0 else FAIL,
        "failed_count": failed_count,
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        **metrics,
        "checks": checks,
        "fixtures": fixtures,
        "sbom_path": "docs/evidence/sbom-inventory.json",
    }
    return report, sbom


def write_json(report: dict[str, Any], sbom: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "sbom-inventory-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output_dir / "sbom-inventory.json").write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# SBOM Inventory Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit generates and validates a local CycloneDX-style SBOM",
        "inventory for third-party GitHub Actions, container images, and",
        "runtime tools used by the lab validation path.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Components | {report['component_count']} |",
        f"| GitHub Actions | {report['action_count']} |",
        f"| Container images | {report['image_count']} |",
        f"| Runtime tools | {report['runtime_count']} |",
        f"| Source path links | {report['source_path_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Expected Failed Check | Detected |", "| --- | --- | --- |"])
    for item in report["fixtures"]:
        lines.append(
            f"| `{item['name']}` | `{item['expected_failed_check']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    (output_dir / "sbom-inventory-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/sbom-inventory-policy.json")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report, sbom = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, sbom, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'sbom-inventory-audit.json'}")
    print(f"wrote {output_dir / 'sbom-inventory-audit.md'}")
    print(f"wrote {output_dir / 'sbom-inventory.json'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
