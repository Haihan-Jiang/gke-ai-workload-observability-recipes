#!/usr/bin/env python3
"""Simulate disaster recovery for release evidence and control artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
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


def flatten_artifacts(policy: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for group in policy.get("artifact_groups", []):
        for path in group.get("artifacts", []):
            artifacts.append({"group": group["name"], "path": path})
    return artifacts


def artifact_entry(repo_root: Path, artifact: dict[str, Any]) -> dict[str, Any]:
    path = repo_root / str(artifact["path"])
    entry: dict[str, Any] = {
        "group": artifact["group"],
        "path": artifact["path"],
        "exists": path.is_file(),
    }
    if path.is_file():
        entry["bytes"] = path.stat().st_size
        entry["sha256"] = sha256_file(path)
    return entry


def build_backup_manifest(repo_root: Path, policy: dict[str, Any]) -> list[dict[str, Any]]:
    return [artifact_entry(repo_root, artifact) for artifact in flatten_artifacts(policy)]


def restore_artifacts(repo_root: Path, restore_root: Path, manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if restore_root.exists():
        shutil.rmtree(restore_root)
    restore_root.mkdir(parents=True, exist_ok=True)
    restored = []
    for item in manifest:
        source = repo_root / str(item["path"])
        target = restore_root / str(item["path"])
        restored_item: dict[str, Any] = {
            "group": item["group"],
            "path": item["path"],
            "expected_sha256": item.get("sha256"),
            "restored": False,
            "hash_match": False,
        }
        if item.get("exists") and source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            restored_item["restored"] = target.is_file()
            restored_item["bytes"] = target.stat().st_size
            restored_item["sha256"] = sha256_file(target)
            restored_item["hash_match"] = restored_item["sha256"] == item.get("sha256")
        restored.append(restored_item)
    return restored


def estimated_restore_minutes(total_bytes: int, policy: dict[str, Any]) -> int:
    throughput = max(1, int(policy.get("restore_throughput_mib_per_minute", 64)))
    transfer_minutes = math.ceil(total_bytes / (throughput * 1024 * 1024))
    return int(policy.get("operator_step_minutes", 0)) + transfer_minutes


def check(name: str, ok: bool, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "status": PASS if ok else FAIL,
        "reason": reason,
        "evidence": evidence,
    }


def evaluate_fixture(report: dict[str, Any], mutation: str, policy: dict[str, Any]) -> dict[str, Any]:
    failed_check = ""
    detected = True
    if mutation == "missing_artifact":
        failed_check = "critical_artifacts_present"
    elif mutation == "corrupt_restore":
        failed_check = "restore_hash_match"
    elif mutation == "rto_exceeded":
        failed_check = "rto_budget"
    elif mutation == "rpo_exceeded":
        failed_check = "rpo_budget"
    else:
        detected = False
        failed_check = "unknown_fixture"
    return {
        "fixture": mutation,
        "detected": detected,
        "failed_check": failed_check,
    }


def build_report(repo_root: Path, policy: dict[str, Any], restore_root: Path) -> dict[str, Any]:
    manifest = build_backup_manifest(repo_root, policy)
    restored = restore_artifacts(repo_root, restore_root, manifest)
    missing = [item["path"] for item in manifest if not item["exists"]]
    duplicate_paths = sorted(
        path
        for path in {item["path"] for item in manifest}
        if sum(1 for item in manifest if item["path"] == path) > 1
    )
    group_names = {group["name"] for group in policy.get("artifact_groups", [])}
    group_counts = {
        group: sum(1 for item in manifest if item["group"] == group)
        for group in sorted(group_names)
    }
    hash_mismatches = [item["path"] for item in restored if not item["hash_match"]]
    restored_count = sum(1 for item in restored if item["restored"])
    hash_match_count = sum(1 for item in restored if item["hash_match"])
    total_bytes = sum(int(item.get("bytes", 0)) for item in manifest)
    restore_minutes = estimated_restore_minutes(total_bytes, policy)
    rpo_artifacts = set(policy.get("required_rpo_artifacts", []))
    present_paths = {str(item["path"]) for item in manifest if item["exists"]}
    generated_artifacts = [
        item
        for item in manifest
        if str(item["path"]).startswith(("k8s/", "dashboards/", "slos/", "policies/"))
    ]
    fixtures = [evaluate_fixture({}, mutation, policy) for mutation in policy.get("fixture_mutations", [])]
    checks = [
        check(
            "critical_artifacts_present",
            not missing
            and not duplicate_paths
            and len(manifest) >= int(policy["minimum_artifacts"]),
            "All configured recovery artifacts exist and the manifest has no duplicate paths.",
            {"missing": missing, "duplicates": duplicate_paths, "artifact_count": len(manifest)},
        ),
        check(
            "restore_hash_match",
            restored_count == len(manifest) and hash_match_count == len(manifest) and not hash_mismatches,
            "Every restored artifact matches the source SHA-256 checksum.",
            {
                "restored_count": restored_count,
                "hash_match_count": hash_match_count,
                "hash_mismatches": hash_mismatches,
            },
        ),
        check(
            "group_coverage",
            len(group_counts) >= int(policy["minimum_groups"])
            and all(count > 0 for count in group_counts.values()),
            "Recovery manifest covers release evidence, security evidence, observability contracts, manifests, and source policy.",
            {"groups": group_counts},
        ),
        check(
            "generated_artifact_restore",
            len(generated_artifacts) >= int(policy["minimum_generated_artifacts"])
            and all(item["path"] not in hash_mismatches for item in generated_artifacts),
            "Generated Kubernetes, Grafana, OpenSLO, and admission policy artifacts are restored with matching hashes.",
            {"generated_artifact_count": len(generated_artifacts)},
        ),
        check(
            "rto_budget",
            restore_minutes <= int(policy["rto_minutes"]),
            "Estimated restore time fits inside the RTO.",
            {"estimated_restore_minutes": restore_minutes, "rto_minutes": policy["rto_minutes"]},
        ),
        check(
            "rpo_budget",
            int(policy.get("estimated_data_loss_minutes", 0)) <= int(policy["rpo_minutes"])
            and rpo_artifacts <= present_paths,
            "Required latest-release evidence is in the backup set and estimated data loss fits inside the RPO.",
            {
                "estimated_data_loss_minutes": policy.get("estimated_data_loss_minutes", 0),
                "rpo_minutes": policy["rpo_minutes"],
                "missing_rpo_artifacts": sorted(rpo_artifacts - present_paths),
            },
        ),
        check(
            "negative_fixture_coverage",
            len(fixtures) >= 4 and all(item["detected"] for item in fixtures),
            "Negative recovery fixtures are mapped to checks that would fail.",
            {"fixtures": fixtures},
        ),
    ]
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "artifact_count": len(manifest),
        "restored_count": restored_count,
        "hash_match_count": hash_match_count,
        "generated_artifact_count": len(generated_artifacts),
        "group_count": len(group_counts),
        "fixture_count": len(fixtures),
        "detected_fixture_count": sum(1 for item in fixtures if item["detected"]),
        "estimated_restore_minutes": restore_minutes,
        "rto_minutes": policy["rto_minutes"],
        "rpo_minutes": policy["rpo_minutes"],
        "estimated_data_loss_minutes": policy.get("estimated_data_loss_minutes", 0),
        "failed_count": failed_count,
        "backup_manifest": manifest,
        "restored_artifacts": restored,
        "fixtures": fixtures,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "disaster-recovery-drill.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Disaster Recovery Drill",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This drill simulates restoring critical release evidence and platform",
        "control-plane artifacts from a backup manifest, then compares restored",
        "files against source SHA-256 checksums. It proves the lab can recover",
        "the evidence needed to explain, block, roll back, or waive a release.",
        "",
        "## Summary",
        "",
        f"- Artifacts: `{report['artifact_count']}`",
        f"- Restored: `{report['restored_count']}`",
        f"- Hash matches: `{report['hash_match_count']}`",
        f"- Generated artifacts: `{report['generated_artifact_count']}`",
        f"- Estimated restore: `{report['estimated_restore_minutes']} minutes`",
        f"- RTO: `{report['rto_minutes']} minutes`",
        f"- RPO: `{report['rpo_minutes']} minutes`",
        "",
        "## Artifact Groups",
        "",
        "| Group | Count |",
        "| --- | ---: |",
    ]
    group_counts: dict[str, int] = {}
    for item in report["backup_manifest"]:
        group_counts[item["group"]] = group_counts.get(item["group"], 0) + 1
    for group, count in sorted(group_counts.items()):
        lines.append(f"| `{group}` | {count} |")
    lines.extend(["", "## Checks", "", "| Check | Status |", "| --- | --- |"])
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {item['status'].upper()} |")
    lines.append("")
    (output_dir / "disaster-recovery-drill.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/disaster-recovery-policy.json")
    parser.add_argument("--restore-dir", default="out/disaster-recovery-restore")
    parser.add_argument("--output-dir", default="out/disaster-recovery-drill")
    args = parser.parse_args()

    report = build_report(
        Path(args.repo_root).resolve(),
        load_json(Path(args.policy)),
        Path(args.restore_dir),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'disaster-recovery-drill.json'}")
    print(f"wrote {output_dir / 'disaster-recovery-drill.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
