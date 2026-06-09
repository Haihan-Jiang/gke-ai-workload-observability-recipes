#!/usr/bin/env python3
"""Audit committed Markdown links for local documentation integrity."""

from __future__ import annotations

import argparse
import copy
import json
import re
import urllib.parse
from pathlib import Path, PurePosixPath
from typing import Any


PASS = "pass"
FAIL = "fail"
LINK_RE = re.compile(r"(?P<image>!)?\[[^\]]+\]\((?P<target>[^)]+)\)")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*#*\s*$")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(name: str, ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": ok, "evidence": evidence}


def markdown_files(repo_root: Path, policy: dict[str, Any]) -> list[str]:
    discovered: set[str] = set()
    excluded = set(policy.get("exclude_markdown_paths", []))
    for root in policy.get("include_markdown_roots", []):
        path = repo_root / str(root)
        if path.is_file() and path.suffix == ".md":
            discovered.add(path.relative_to(repo_root).as_posix())
        elif path.is_dir():
            for item in path.rglob("*.md"):
                discovered.add(item.relative_to(repo_root).as_posix())
    return sorted(path for path in discovered if path not in excluded)


def load_markdown(repo_root: Path, policy: dict[str, Any]) -> dict[str, str | None]:
    files = {path: (repo_root / path).read_text(encoding="utf-8") for path in markdown_files(repo_root, policy)}
    for path in policy.get("required_files", []):
        files.setdefault(
            str(path),
            (repo_root / str(path)).read_text(encoding="utf-8") if (repo_root / str(path)).is_file() else None,
        )
    return files


def split_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    return value.split()[0] if value else value


def slugify_heading(title: str) -> str:
    text = title.strip().lower()
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[^a-z0-9 _-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def anchors_by_file(files: dict[str, str | None]) -> dict[str, set[str]]:
    anchors: dict[str, set[str]] = {}
    for path, text in files.items():
        current: set[str] = set()
        if text is not None:
            for line in text.splitlines():
                match = HEADING_RE.match(line)
                if match:
                    current.add(slugify_heading(match.group("title")))
        anchors[path] = current
    return anchors


def path_safe(source: str, target_path: str) -> tuple[bool, str]:
    decoded = urllib.parse.unquote(target_path)
    posix = PurePosixPath(decoded)
    if posix.is_absolute():
        return False, decoded
    source_parent = PurePosixPath(source).parent
    resolved_parts: list[str] = []
    for part in (source_parent / posix).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not resolved_parts:
                return False, decoded
            resolved_parts.pop()
        else:
            resolved_parts.append(part)
    return True, PurePosixPath(*resolved_parts).as_posix()


def extract_links(repo_root: Path, files: dict[str, str | None], policy: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_schemes = set(policy.get("allowed_external_schemes", []))
    anchors = anchors_by_file(files)
    results: list[dict[str, Any]] = []
    for source, text in files.items():
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in LINK_RE.finditer(line):
                target = split_target(match.group("target"))
                parsed = urllib.parse.urlparse(target)
                is_image = bool(match.group("image"))
                entry: dict[str, Any] = {
                    "source": source,
                    "line": line_number,
                    "target": target,
                    "is_image": is_image,
                    "kind": "local",
                    "scheme_allowed": True,
                    "path_safe": True,
                    "target_exists": True,
                    "anchor_exists": True,
                }
                if parsed.scheme:
                    entry["kind"] = "external"
                    entry["scheme"] = parsed.scheme
                    entry["scheme_allowed"] = parsed.scheme in allowed_schemes
                    results.append(entry)
                    continue
                if target.startswith("#"):
                    fragment = urllib.parse.unquote(target[1:])
                    entry["resolved_path"] = source
                    entry["fragment"] = fragment
                    entry["anchor_exists"] = not fragment or fragment in anchors.get(source, set())
                    results.append(entry)
                    continue
                target_path, _, fragment = target.partition("#")
                safe, resolved_path = path_safe(source, target_path)
                entry["resolved_path"] = resolved_path
                entry["fragment"] = urllib.parse.unquote(fragment)
                entry["path_safe"] = safe
                entry["target_exists"] = safe and (repo_root / resolved_path).exists()
                if safe and fragment and Path(resolved_path).suffix == ".md":
                    entry["anchor_exists"] = fragment in anchors.get(resolved_path, set())
                results.append(entry)
    return results


def evaluate_files(repo_root: Path, files: dict[str, str | None], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    required_files = [str(path) for path in policy.get("required_files", [])]
    missing_required = [path for path in required_files if files.get(path) is None]
    links = extract_links(repo_root, files, policy)
    local_links = [item for item in links if item["kind"] == "local"]
    external_links = [item for item in links if item["kind"] == "external"]
    image_links = [item for item in links if item["is_image"]]
    unsafe_links = [item for item in links if not item["path_safe"]]
    missing_targets = [item for item in local_links if item["path_safe"] and not item["target_exists"]]
    bad_anchors = [item for item in local_links if item["target_exists"] and not item["anchor_exists"]]
    bad_schemes = [item for item in external_links if not item["scheme_allowed"]]
    markdown_file_count = sum(1 for text in files.values() if text is not None)
    checks = [
        check(
            "required_file_inventory",
            not missing_required
            and len(required_files) >= int(policy.get("minimum_required_file_count", 0)),
            {"missing_required": missing_required, "required_file_count": len(required_files)},
        ),
        check(
            "markdown_inventory",
            markdown_file_count >= int(policy.get("minimum_markdown_file_count", 0)),
            {
                "markdown_file_count": markdown_file_count,
                "minimum_markdown_file_count": policy.get("minimum_markdown_file_count"),
            },
        ),
        check("path_safety", not unsafe_links, {"unsafe_links": unsafe_links}),
        check("scheme_contract", not bad_schemes, {"bad_schemes": bad_schemes}),
        check("local_link_targets", not missing_targets, {"missing_targets": missing_targets}),
        check("anchor_targets", not bad_anchors, {"bad_anchors": bad_anchors}),
        check(
            "link_volume_contract",
            len(local_links) >= int(policy.get("minimum_local_link_count", 0))
            and len(external_links) >= int(policy.get("minimum_external_link_count", 0))
            and len(image_links) >= int(policy.get("minimum_image_link_count", 0)),
            {
                "local_link_count": len(local_links),
                "external_link_count": len(external_links),
                "image_link_count": len(image_links),
            },
        ),
    ]
    metrics = {
        "markdown_file_count": markdown_file_count,
        "required_file_count": len(required_files),
        "local_link_count": len(local_links),
        "external_link_count": len(external_links),
        "image_link_count": len(image_links),
        "unsafe_link_count": len(unsafe_links),
        "missing_target_count": len(missing_targets),
        "bad_anchor_count": len(bad_anchors),
        "bad_scheme_count": len(bad_schemes),
    }
    return checks, metrics, links


def apply_fixture(files: dict[str, str | None], fixture: dict[str, Any]) -> dict[str, str | None]:
    mutated = copy.deepcopy(files)
    mutation = fixture.get("mutation")
    path = str(fixture.get("path", ""))
    if mutation == "remove_file":
        mutated[path] = None
        return mutated
    if mutation == "append_link":
        text = mutated.get(path) or ""
        mutated[path] = text.rstrip() + "\n\n" + str(fixture.get("link", "")) + "\n"
        return mutated
    raise ValueError(f"unsupported fixture mutation: {mutation}")


def evaluate_fixtures(repo_root: Path, files: dict[str, str | None], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated = apply_fixture(files, fixture)
        checks, _, _ = evaluate_files(repo_root, mutated, policy)
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


def build_report(repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    files = load_markdown(repo_root, policy)
    checks, metrics, links = evaluate_files(repo_root, files, policy)
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
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "check_count": len(checks),
        "failed_count": failed_count,
        "detected_fixture_count": detected_fixture_count,
        "links": links,
        "fixture_results": fixtures,
        "checks": checks,
        **metrics,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "documentation-link-integrity-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Documentation Link Integrity Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks committed Markdown documentation links without",
        "network access. Local repository links must resolve, local Markdown",
        "anchors must exist, paths must stay inside the repository, and external",
        "links must use approved schemes.",
        "",
        "## Summary",
        "",
        f"- Markdown files: `{report['markdown_file_count']}`",
        f"- Local links: `{report['local_link_count']}`",
        f"- External links: `{report['external_link_count']}`",
        f"- Image links: `{report['image_link_count']}`",
        f"- Missing targets: `{report['missing_target_count']}`",
        f"- Bad anchors: `{report['bad_anchor_count']}`",
        f"- Bad schemes: `{report['bad_scheme_count']}`",
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
    (output_dir / "documentation-link-integrity-audit.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/documentation-link-policy.json")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root).resolve(), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'documentation-link-integrity-audit.json'}")
    print(f"wrote {output_dir / 'documentation-link-integrity-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
