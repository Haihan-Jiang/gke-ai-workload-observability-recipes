#!/usr/bin/env python3
"""Audit the OpenTelemetry Collector authoritative exporter boundary."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


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


def load_manifest_set(repo_root: Path, paths: list[str]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in paths:
        docs.extend(load_yaml_documents(repo_root / path))
    return docs


def load_documentation(repo_root: Path, paths: list[str]) -> dict[str, str]:
    return {path: (repo_root / path).read_text(encoding="utf-8") for path in paths}


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


def collector_config_map(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    collector = policy["collector"]
    index = index_documents(docs)
    return index.get(("ConfigMap", collector["namespace"], collector["config_map"]), {})


def collector_config(config_map: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    key = policy["collector"]["config_key"]
    config_yaml = config_map.get("data", {}).get(key, "")
    if not config_yaml:
        return {}
    parsed = parse_yaml_text(str(config_yaml))
    return parsed if isinstance(parsed, dict) else {}


def pipeline(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get("service", {}).get("pipelines", {}).get(name, {})
    return value if isinstance(value, dict) else {}


def pipeline_exporters(config: dict[str, Any], name: str) -> list[str]:
    exporters = pipeline(config, name).get("exporters", [])
    return [str(item) for item in exporters] if isinstance(exporters, list) else []


def exporter(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get("exporters", {}).get(name, {})
    return value if isinstance(value, dict) else {}


def endpoint_gap(endpoint: str | None, policy: dict[str, Any]) -> dict[str, Any] | None:
    if not endpoint:
        return {"reason": "missing_endpoint"}
    parsed = urlparse(endpoint)
    collector = policy["collector"]
    if parsed.scheme != collector["required_endpoint_scheme"]:
        return {"reason": "wrong_scheme", "observed": parsed.scheme, "expected": collector["required_endpoint_scheme"]}
    if parsed.hostname in set(collector.get("forbidden_endpoint_hosts", [])):
        return {"reason": "forbidden_host", "host": parsed.hostname}
    if parsed.port != int(collector["required_endpoint_port"]):
        return {"reason": "wrong_port", "observed": parsed.port, "expected": collector["required_endpoint_port"]}
    return None


def queue_gaps(config: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    collector = policy["collector"]
    authoritative = collector["authoritative_exporter"]
    upstream = exporter(config, authoritative)
    service_extensions = config.get("service", {}).get("extensions", [])
    extensions = service_extensions if isinstance(service_extensions, list) else []
    gaps = []
    if collector["required_service_extension"] not in extensions:
        gaps.append({"reason": "missing_service_extension", "extension": collector["required_service_extension"]})
    if upstream.get("sending_queue", {}).get("enabled") is not True:
        gaps.append({"reason": "sending_queue_disabled", "exporter": authoritative})
    if upstream.get("sending_queue", {}).get("storage") != collector["required_queue_storage"]:
        gaps.append(
            {
                "reason": "wrong_queue_storage",
                "observed": upstream.get("sending_queue", {}).get("storage"),
                "expected": collector["required_queue_storage"],
            }
        )
    if upstream.get("retry_on_failure", {}).get("enabled") is not True:
        gaps.append({"reason": "retry_disabled", "exporter": authoritative})
    return gaps


def evaluate(docs: list[dict[str, Any]], documentation: dict[str, str], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config_map = collector_config_map(docs, policy)
    config = collector_config(config_map, policy) if config_map else {}
    collector = policy["collector"]
    annotations = metadata(config_map).get("annotations", {}) if config_map else {}
    authoritative = collector["authoritative_exporter"]
    local = collector["local_exporter"]
    required_pipelines = list(collector["required_pipelines"])
    observed_pipelines = {name: pipeline_exporters(config, name) for name in required_pipelines}
    authority_annotation_gaps = []
    if annotations.get(collector["authoritative_exporter_annotation"]) != authoritative:
        authority_annotation_gaps.append(
            {
                "annotation": collector["authoritative_exporter_annotation"],
                "observed": annotations.get(collector["authoritative_exporter_annotation"]),
                "expected": authoritative,
            }
        )
    if annotations.get(collector["local_exporter_annotation"]) != local:
        authority_annotation_gaps.append(
            {
                "annotation": collector["local_exporter_annotation"],
                "observed": annotations.get(collector["local_exporter_annotation"]),
                "expected": local,
            }
        )
    if annotations.get(collector["authority_mode_annotation"]) != collector["authority_mode"]:
        authority_annotation_gaps.append(
            {
                "annotation": collector["authority_mode_annotation"],
                "observed": annotations.get(collector["authority_mode_annotation"]),
                "expected": collector["authority_mode"],
            }
        )

    missing_authoritative = [
        {"pipeline": name, "exporters": exporters}
        for name, exporters in observed_pipelines.items()
        if authoritative not in exporters
    ]
    debug_only = [
        {"pipeline": name, "exporters": exporters}
        for name, exporters in observed_pipelines.items()
        if local in exporters and authoritative not in exporters
    ]
    missing_local = [
        {"pipeline": name, "exporters": exporters}
        for name, exporters in observed_pipelines.items()
        if local not in exporters
    ]
    upstream = exporter(config, authoritative)
    endpoint = upstream.get("endpoint")
    secure_gap = endpoint_gap(str(endpoint) if endpoint is not None else None, policy)
    delivery_gaps = queue_gaps(config, policy)
    doc_text = "\n".join(documentation.values())
    missing_doc_text = [
        text for text in policy.get("required_documentation_text", []) if text not in doc_text
    ]
    checks = [
        check(
            "collector_config_map",
            bool(config_map) and bool(config),
            "Collector ConfigMap exists and its embedded collector config is parseable.",
            {"config_map": name(config_map) if config_map else None},
        ),
        check(
            "exporter_authority_annotations",
            not authority_annotation_gaps,
            "Collector ConfigMap explicitly declares the authoritative upstream exporter and the local debug exporter.",
            {"gaps": authority_annotation_gaps},
        ),
        check(
            "authoritative_pipeline_path",
            not missing_authoritative,
            "Every required telemetry pipeline exports to the authoritative upstream gateway.",
            {"gaps": missing_authoritative, "pipelines": observed_pipelines},
        ),
        check(
            "local_debug_boundary",
            not debug_only and not missing_local,
            "Debug export remains a local companion path and is never the only exporter for a release pipeline.",
            {"debug_only": debug_only, "missing_local": missing_local},
        ),
        check(
            "secure_upstream_endpoint",
            secure_gap is None,
            "The authoritative upstream endpoint uses the expected secure OTLP/HTTP gateway boundary.",
            {"endpoint": endpoint, "gap": secure_gap},
        ),
        check(
            "queued_delivery_boundary",
            not delivery_gaps,
            "The authoritative exporter uses file-backed queueing and retry so telemetry survives gateway outages.",
            {"gaps": delivery_gaps},
        ),
        check(
            "production_replacement_docs",
            not missing_doc_text,
            "README documents that the placeholder endpoint must be replaced by a production telemetry backend.",
            {"missing_text": missing_doc_text},
        ),
    ]
    metrics = {
        "exporter_count": len(config.get("exporters", {})) if config else 0,
        "authoritative_pipeline_count": sum(1 for exporters in observed_pipelines.values() if authoritative in exporters),
        "local_debug_pipeline_count": sum(1 for exporters in observed_pipelines.values() if local in exporters),
        "queued_exporter_count": 1 if not delivery_gaps else 0,
        "retry_enabled_count": 1 if exporter(config, authoritative).get("retry_on_failure", {}).get("enabled") is True else 0,
        "pipelines": observed_pipelines,
        "authoritative_endpoint": endpoint,
    }
    return checks, metrics


def find_doc(docs: list[dict[str, Any]], kind: str, doc_namespace: str, doc_name: str) -> dict[str, Any]:
    for doc in docs:
        if doc.get("kind") == kind and namespace(doc) == doc_namespace and name(doc) == doc_name:
            return doc
    raise ValueError(f"missing {kind}/{doc_namespace}/{doc_name}")


def set_config_map_config(config_map: dict[str, Any], policy: dict[str, Any], config: dict[str, Any]) -> None:
    key = policy["collector"]["config_key"]
    config_map.setdefault("data", {})[key] = json.dumps(config)


def apply_fixture(
    docs: list[dict[str, Any]],
    documentation: dict[str, str],
    fixture: dict[str, Any],
    policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    mutated_docs = copy.deepcopy(docs)
    mutated_docs_text = copy.deepcopy(documentation)
    collector = policy["collector"]
    config_map = find_doc(mutated_docs, "ConfigMap", collector["namespace"], collector["config_map"])
    config = collector_config(config_map, policy)
    mutation = fixture.get("mutation")
    if mutation == "remove_config_map_annotation":
        metadata(config_map).setdefault("annotations", {}).pop(str(fixture["annotation"]), None)
    elif mutation == "set_config_map_annotation":
        metadata(config_map).setdefault("annotations", {})[str(fixture["annotation"])] = fixture.get("value")
    elif mutation == "remove_pipeline_exporter":
        pipeline_name = str(fixture["pipeline"])
        target = str(fixture["exporter"])
        exporters = pipeline(config, pipeline_name).get("exporters", [])
        if isinstance(exporters, list):
            pipeline(config, pipeline_name)["exporters"] = [item for item in exporters if item != target]
        set_config_map_config(config_map, policy, config)
    elif mutation == "set_pipeline_exporters":
        pipeline(config, str(fixture["pipeline"]))["exporters"] = list(fixture.get("exporters", []))
        set_config_map_config(config_map, policy, config)
    elif mutation == "set_exporter_endpoint":
        exporter(config, str(fixture["exporter"]))["endpoint"] = fixture.get("endpoint")
        set_config_map_config(config_map, policy, config)
    elif mutation == "set_exporter_queue_enabled":
        exporter(config, str(fixture["exporter"])).setdefault("sending_queue", {})["enabled"] = fixture.get("enabled")
        set_config_map_config(config_map, policy, config)
    elif mutation == "remove_documentation_text":
        target = str(fixture["text"])
        for path, text in mutated_docs_text.items():
            mutated_docs_text[path] = text.replace(target, "")
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")
    return mutated_docs, mutated_docs_text


def evaluate_fixtures(docs: list[dict[str, Any]], documentation: dict[str, str], policy: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for fixture in policy.get("fixtures", []):
        mutated_docs, mutated_documentation = apply_fixture(docs, documentation, fixture, policy)
        checks, _ = evaluate(mutated_docs, mutated_documentation, policy)
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
    documentation = load_documentation(repo_root, list(policy.get("documentation_files", [])))
    checks, metrics = evaluate(docs, documentation, policy)
    fixtures = evaluate_fixtures(docs, documentation, policy)
    detected_fixture_count = sum(1 for item in fixtures if item["detected"])
    checks.append(
        check(
            "negative_fixture_coverage",
            detected_fixture_count >= int(policy.get("minimum_detected_fixtures", 0)),
            "Negative fixtures prove exporter authority, endpoint, queue, and documentation drift are detected.",
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
        "exporter_count": metrics["exporter_count"],
        "authoritative_pipeline_count": metrics["authoritative_pipeline_count"],
        "local_debug_pipeline_count": metrics["local_debug_pipeline_count"],
        "queued_exporter_count": metrics["queued_exporter_count"],
        "retry_enabled_count": metrics["retry_enabled_count"],
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "check_count": len(checks),
        "authoritative_endpoint": metrics["authoritative_endpoint"],
        "pipelines": metrics["pipelines"],
        "checks": checks,
        "fixture_results": fixtures,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "telemetry-exporter-authority-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Telemetry Exporter Authority Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit verifies that the collector has an explicit authoritative",
        "upstream telemetry exporter, keeps local debug export bounded, and",
        "uses queued retry delivery for traces and metrics.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Exporters | {report['exporter_count']} |",
        f"| Authoritative pipelines | {report['authoritative_pipeline_count']} |",
        f"| Local debug pipelines | {report['local_debug_pipeline_count']} |",
        f"| Queued exporters | {report['queued_exporter_count']} |",
        f"| Retry-enabled exporters | {report['retry_enabled_count']} |",
        f"| Detected fixtures | {report['detected_fixture_count']} |",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for item in report["checks"]:
        lines.append(f"| `{item['name']}` | {item['status'].upper()} |")
    lines.extend(["", "## Pipelines", "", "| Pipeline | Exporters |", "| --- | --- |"])
    for name, exporters in report["pipelines"].items():
        lines.append(f"| `{name}` | `{', '.join(exporters)}` |")
    lines.extend(["", "## Negative Fixtures", "", "| Fixture | Expected Failed Check | Detected |", "| --- | --- | --- |"])
    for item in report["fixture_results"]:
        lines.append(
            f"| `{item['name']}` | `{item['expected_failed_check']}` | {'yes' if item['detected'] else 'no'} |"
        )
    lines.append("")
    (output_dir / "telemetry-exporter-authority-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default="config/telemetry-exporter-policy.json")
    parser.add_argument("--output-dir", default="out/telemetry-exporter-authority-audit")
    args = parser.parse_args()

    report = build_report(Path(args.repo_root), load_json(Path(args.policy)))
    output_dir = Path(args.output_dir)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'telemetry-exporter-authority-audit.json'}")
    print(f"wrote {output_dir / 'telemetry-exporter-authority-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
