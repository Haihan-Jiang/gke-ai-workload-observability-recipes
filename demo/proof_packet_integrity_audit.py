#!/usr/bin/env python3
"""Audit proof-packet checksum integrity against the current repository tree."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


PASS = "pass"
FAIL = "fail"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def safe_relative_path(value: str) -> bool:
    if not value or value.strip() != value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def manifest_entries(provenance: dict[str, Any]) -> list[dict[str, Any]]:
    sections = [
        ("artifacts", "evidence"),
        ("generated_artifacts", "generated-artifact"),
        ("source_inputs", "source-input"),
    ]
    entries: list[dict[str, Any]] = []
    for section, default_group in sections:
        for item in provenance.get(section, []):
            entry = dict(item)
            entry["section"] = section
            entry["group"] = str(entry.get("group") or default_group)
            entries.append(entry)
    return entries


def entry_status(repo_root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    relative_path = str(entry.get("path", ""))
    path_safe = safe_relative_path(relative_path)
    current_path = repo_root / relative_path if path_safe else None
    exists = bool(current_path and current_path.is_file())
    declared_sha = str(entry.get("sha256", ""))
    declared_bytes = entry.get("bytes")
    status: dict[str, Any] = {
        "path": relative_path,
        "section": entry.get("section"),
        "group": entry.get("group"),
        "path_safe": path_safe,
        "exists": exists,
        "declared_bytes": declared_bytes,
        "declared_sha256": declared_sha,
        "checksum_shape_ok": bool(SHA256_RE.match(declared_sha)),
    }
    if exists and current_path:
        current_bytes = current_path.stat().st_size
        current_sha = sha256_file(current_path)
        status.update(
            {
                "current_bytes": current_bytes,
                "current_sha256": current_sha,
                "bytes_match": declared_bytes == current_bytes,
                "digest_match": declared_sha == current_sha,
                "empty": current_bytes <= 0,
            }
        )
    else:
        status.update(
            {
                "current_bytes": None,
                "current_sha256": None,
                "bytes_match": False,
                "digest_match": False,
                "empty": False,
            }
        )
    return status


def duplicate_paths(entries: list[dict[str, Any]]) -> list[str]:
    paths = [str(item.get("path", "")) for item in entries]
    return sorted({path for path in paths if paths.count(path) > 1})


def mutate_provenance(provenance: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(provenance)
    mutation = fixture.get("mutation")
    section = str(fixture.get("section", ""))
    index = int(fixture.get("index", 0))
    if mutation == "set_digest":
        mutated[section][index]["sha256"] = fixture["sha256"]
        return mutated
    if mutation == "set_path":
        mutated[section][index]["path"] = fixture["path"]
        return mutated
    if mutation == "append_forbidden_entry":
        base = dict(mutated.get("artifacts", [{}])[0])
        base["path"] = fixture["path"]
        mutated.setdefault(section, []).append(base)
        return mutated
    if mutation == "duplicate_entry":
        mutated.setdefault(section, []).append(copy.deepcopy(mutated[section][index]))
        return mutated
    if mutation == "remove_validation_command":
        command = fixture.get("command")
        mutated["validation_commands"] = [
            item for item in mutated.get("validation_commands", []) if item != command
        ]
        return mutated
    raise ValueError(f"unsupported fixture mutation: {mutation}")


def evaluate(
    repo_root: Path,
    provenance: dict[str, Any],
    policy: dict[str, Any],
    *,
    include_fixtures: bool = True,
) -> dict[str, Any]:
    entries = manifest_entries(provenance)
    statuses = [entry_status(repo_root, entry) for entry in entries]
    paths = [str(item.get("path", "")) for item in entries]
    duplicates = duplicate_paths(entries)
    unsafe_paths = [item["path"] for item in statuses if not item["path_safe"]]
    missing_paths = [item["path"] for item in statuses if not item["exists"]]
    invalid_checksums = [item["path"] for item in statuses if not item["checksum_shape_ok"]]
    digest_mismatches = [
        item["path"] for item in statuses if item["exists"] and not item["digest_match"]
    ]
    byte_mismatches = [
        item["path"] for item in statuses if item["exists"] and not item["bytes_match"]
    ]
    empty_paths = [item["path"] for item in statuses if item["empty"]]
    forbidden = set(policy.get("forbidden_circular_artifacts", []))
    forbidden_present = sorted(forbidden & set(paths))
    required_commands = set(policy.get("required_validation_commands", []))
    observed_commands = set(provenance.get("validation_commands", []))
    missing_commands = sorted(required_commands - observed_commands)
    evidence_count = sum(1 for item in entries if item.get("section") == "artifacts")
    generated_count = sum(1 for item in entries if item.get("section") == "generated_artifacts")
    source_count = sum(1 for item in entries if item.get("section") == "source_inputs")
    matched_digest_count = sum(1 for item in statuses if item["exists"] and item["digest_match"])

    checks = [
        check(
            "provenance_status_contract",
            provenance.get("status") == PASS and int(provenance.get("failed_count", -1)) == 0,
            {
                "status": provenance.get("status"),
                "failed_count": provenance.get("failed_count"),
            },
        ),
        check(
            "manifest_inventory",
            evidence_count >= int(policy.get("minimum_evidence_artifacts", 0))
            and generated_count >= int(policy.get("minimum_generated_artifacts", 0))
            and source_count >= int(policy.get("minimum_source_inputs", 0))
            and len(entries) >= int(policy.get("minimum_manifest_entries", 0))
            and not duplicates,
            {
                "evidence_artifact_count": evidence_count,
                "generated_artifact_count": generated_count,
                "source_input_count": source_count,
                "manifest_entry_count": len(entries),
                "duplicate_paths": duplicates,
            },
        ),
        check(
            "path_safety_contract",
            not unsafe_paths,
            {"unsafe_paths": unsafe_paths},
        ),
        check(
            "checksum_contract",
            not invalid_checksums and not empty_paths,
            {"invalid_checksums": invalid_checksums, "empty_paths": empty_paths},
        ),
        check(
            "current_digest_match",
            not missing_paths and not digest_mismatches and not byte_mismatches,
            {
                "missing_paths": missing_paths,
                "digest_mismatches": digest_mismatches,
                "byte_mismatches": byte_mismatches,
                "matched_digest_count": matched_digest_count,
            },
        ),
        check(
            "circular_artifact_boundary",
            not forbidden_present,
            {"forbidden_present": forbidden_present},
        ),
        check(
            "validation_command_contract",
            not missing_commands,
            {
                "required_commands": sorted(required_commands),
                "observed_commands": sorted(observed_commands),
                "missing_commands": missing_commands,
            },
        ),
    ]
    fixture_results: list[dict[str, Any]] = []
    if include_fixtures:
        for fixture in policy.get("fixtures", []):
            mutated = mutate_provenance(provenance, fixture)
            fixture_report = evaluate(repo_root, mutated, policy, include_fixtures=False)
            failed_checks = [
                item["name"] for item in fixture_report["checks"] if not item["ok"]
            ]
            expected = str(fixture.get("expected_failed_check"))
            fixture_results.append(
                {
                    "name": fixture.get("name"),
                    "mutation": fixture.get("mutation"),
                    "expected_failed_check": expected,
                    "failed_checks": failed_checks,
                    "detected": expected in failed_checks,
                }
            )
        detected_fixture_count = sum(1 for item in fixture_results if item["detected"])
        checks.append(
            check(
                "negative_fixture_coverage",
                detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
                {
                    "detected_fixture_count": detected_fixture_count,
                    "minimum_detected_fixtures": policy.get("minimum_detected_fixtures"),
                    "fixtures": fixture_results,
                },
            )
        )
    else:
        detected_fixture_count = 0

    failed_count = sum(1 for item in checks if not item["ok"])
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "check_count": len(checks),
        "failed_count": failed_count,
        "manifest_entry_count": len(entries),
        "evidence_artifact_count": evidence_count,
        "generated_artifact_count": generated_count,
        "source_input_count": source_count,
        "matched_digest_count": matched_digest_count,
        "missing_path_count": len(missing_paths),
        "mismatched_digest_count": len(digest_mismatches),
        "circular_artifact_count": len(forbidden_present),
        "detected_fixture_count": detected_fixture_count,
        "checks": checks,
        "manifest_entries": statuses,
        "fixture_results": fixture_results,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "proof-packet-integrity-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Proof Packet Integrity Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit re-checks the evidence provenance manifest against the",
        "current repository tree. It proves that release evidence, generated",
        "artifacts, and source inputs still match the checksums that release",
        "readiness consumes, while keeping release-readiness and provenance",
        "artifacts out of the manifest cycle.",
        "",
        "## Summary",
        "",
        f"- Manifest entries: `{report['manifest_entry_count']}`",
        f"- Evidence artifacts: `{report['evidence_artifact_count']}`",
        f"- Generated artifacts: `{report['generated_artifact_count']}`",
        f"- Source inputs: `{report['source_input_count']}`",
        f"- Matched digests: `{report['matched_digest_count']}`",
        f"- Missing paths: `{report['missing_path_count']}`",
        f"- Digest mismatches: `{report['mismatched_digest_count']}`",
        f"- Circular artifacts: `{report['circular_artifact_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {'PASS' if item['ok'] else 'FAIL'} |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Detected |", "| --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(f"| `{item['name']}` | {'yes' if item['detected'] else 'no'} |")
    lines.append("")
    (output_dir / "proof-packet-integrity-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/proof-packet-integrity-policy.json")
    parser.add_argument("--provenance", default="docs/evidence/evidence-provenance.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = evaluate(
        Path(args.repo_root).resolve(),
        load_json(Path(args.provenance)),
        load_json(Path(args.policy)),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'proof-packet-integrity-audit.json'}")
    print(f"wrote {output_dir / 'proof-packet-integrity-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
