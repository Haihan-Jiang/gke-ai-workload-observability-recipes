#!/usr/bin/env python3
"""Generate a checksum manifest for committed evidence and generated assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any


PASS = "pass"
FAIL = "fail"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_entry(repo_root: Path, relative_path: str, group: str) -> dict[str, Any]:
    path = repo_root / relative_path
    exists = path.is_file()
    entry: dict[str, Any] = {
        "path": relative_path,
        "group": group,
        "exists": exists,
    }
    if exists:
        entry["bytes"] = path.stat().st_size
        entry["sha256"] = sha256_file(path)
    return entry


def entries(repo_root: Path, paths: list[str], group: str) -> list[dict[str, Any]]:
    return [artifact_entry(repo_root, path, group) for path in paths]


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def build_provenance(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    required_artifacts = entries(repo_root, policy["required_artifacts"], "evidence")
    generated_artifacts = entries(repo_root, policy["generated_artifacts"], "generated-artifact")
    source_inputs = entries(repo_root, policy["source_inputs"], "source-input")
    all_entries = required_artifacts + generated_artifacts + source_inputs
    excluded = set(policy.get("excluded_circular_artifacts", []))
    configured = set(policy["required_artifacts"] + policy["generated_artifacts"] + policy["source_inputs"])
    missing_required = [item["path"] for item in required_artifacts if not item["exists"]]
    missing_generated = [item["path"] for item in generated_artifacts if not item["exists"]]
    missing_sources = [item["path"] for item in source_inputs if not item["exists"]]
    missing_checksums = [
        item["path"]
        for item in all_entries
        if item["exists"] and len(str(item.get("sha256", ""))) != 64
    ]
    empty_files = [
        item["path"]
        for item in all_entries
        if item["exists"] and int(item.get("bytes", 0)) <= 0
    ]
    circular = sorted(configured & excluded)
    checks = [
        check(
            "required_evidence_present",
            not missing_required and len(required_artifacts) >= int(policy["minimum_evidence_artifacts"]),
            {
                "missing": missing_required,
                "count": len(required_artifacts),
                "minimum": policy["minimum_evidence_artifacts"],
            },
        ),
        check(
            "generated_artifacts_present",
            not missing_generated,
            {"missing": missing_generated, "count": len(generated_artifacts)},
        ),
        check(
            "source_inputs_present",
            not missing_sources and len(source_inputs) >= int(policy["minimum_source_inputs"]),
            {
                "missing": missing_sources,
                "count": len(source_inputs),
                "minimum": policy["minimum_source_inputs"],
            },
        ),
        check(
            "checksum_coverage",
            not missing_checksums and not empty_files,
            {"missing_checksums": missing_checksums, "empty_files": empty_files},
        ),
        check(
            "no_release_readiness_cycle",
            not circular,
            {"excluded_configured": circular},
        ),
        check(
            "validation_commands_recorded",
            len(policy.get("validation_commands", [])) >= 4,
            {"commands": policy.get("validation_commands", [])},
        ),
    ]
    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "failed_count": failed_count,
        "artifact_count": len(required_artifacts),
        "generated_artifact_count": len(generated_artifacts),
        "source_input_count": len(source_inputs),
        "validation_commands": policy.get("validation_commands", []),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "artifacts": required_artifacts,
        "generated_artifacts": generated_artifacts,
        "source_inputs": source_inputs,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "evidence-provenance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Evidence Provenance",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This manifest records checksums for committed evidence, generated",
        "Kubernetes/Grafana/OpenSLO artifacts, and source inputs used to build",
        "the lab's release-readiness packet. It makes stale or hand-edited",
        "evidence easier to detect during review.",
        "",
        "## Summary",
        "",
        f"- Evidence artifacts: `{report['artifact_count']}`",
        f"- Generated artifacts: `{report['generated_artifact_count']}`",
        f"- Source inputs: `{report['source_input_count']}`",
        f"- Python: `{report['runtime']['python']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Evidence Artifacts", "", "| Path | Bytes | SHA-256 |", "| --- | ---: | --- |"])
    for item in report["artifacts"]:
        lines.append(
            f"| `{item['path']}` | {item.get('bytes', 0)} | `{str(item.get('sha256', 'missing'))[:16]}...` |"
        )
    lines.extend(["", "## Generated Artifacts", "", "| Path | Bytes | SHA-256 |", "| --- | ---: | --- |"])
    for item in report["generated_artifacts"]:
        lines.append(
            f"| `{item['path']}` | {item.get('bytes', 0)} | `{str(item.get('sha256', 'missing'))[:16]}...` |"
        )
    lines.extend(["", "## Validation Commands", ""])
    for command in report["validation_commands"]:
        lines.append(f"- `{command}`")
    lines.append("")
    (output_dir / "evidence-provenance.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/evidence-provenance-policy.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_provenance(
        Path(args.repo_root).resolve(),
        load_json(Path(args.policy)),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'evidence-provenance.json'}")
    print(f"wrote {output_dir / 'evidence-provenance.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
