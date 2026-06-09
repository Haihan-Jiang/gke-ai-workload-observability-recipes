#!/usr/bin/env python3
"""Audit OpenTelemetry Collector self-observability metrics wiring."""

from __future__ import annotations

import argparse
import copy
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


def parse_duration_seconds(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.endswith("ms"):
        return float(text[:-2]) / 1000.0
    if text.endswith("s"):
        return float(text[:-1])
    if text.endswith("m"):
        return float(text[:-1]) * 60.0
    return float(text)


def collector_config_map(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    collector = policy["collector"]
    index = index_documents(docs)
    return index.get(("ConfigMap", collector["namespace"], collector["config_map"]), {})


def collector_config(config_map: dict[str, Any]) -> dict[str, Any]:
    config_yaml = config_map.get("data", {}).get("config.yaml", "")
    if not config_yaml:
        return {}
    parsed = parse_yaml_text(config_yaml)
    return parsed if isinstance(parsed, dict) else {}


def pipeline(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get("service", {}).get("pipelines", {}).get(name, {})
    return value if isinstance(value, dict) else {}


def pipeline_receivers(config: dict[str, Any], name: str) -> list[str]:
    receivers = pipeline(config, name).get("receivers", [])
    return [str(item) for item in receivers] if isinstance(receivers, list) else []


def pipeline_processors(config: dict[str, Any], name: str) -> list[str]:
    processors = pipeline(config, name).get("processors", [])
    return [str(item) for item in processors] if isinstance(processors, list) else []


def pipeline_exporters(config: dict[str, Any], name: str) -> list[str]:
    exporters = pipeline(config, name).get("exporters", [])
    return [str(item) for item in exporters] if isinstance(exporters, list) else []


def self_metrics_receiver(config: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    name = policy["collector"]["self_metrics_receiver"]
    value = config.get("receivers", {}).get(name, {})
    return value if isinstance(value, dict) else {}


def scrape_configs(receiver: dict[str, Any]) -> list[dict[str, Any]]:
    configs = receiver.get("config", {}).get("scrape_configs", [])
    return [item for item in configs if isinstance(item, dict)] if isinstance(configs, list) else []


def scrape_targets(receiver: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    for scrape_config in scrape_configs(receiver):
        for static_config in scrape_config.get("static_configs", []):
            if isinstance(static_config, dict):
                targets.extend(str(item) for item in static_config.get("targets", []))
    return targets


def scrape_job_names(receiver: dict[str, Any]) -> list[str]:
    return [str(item.get("job_name", "")) for item in scrape_configs(receiver)]


def scrape_intervals(receiver: dict[str, Any]) -> list[float]:
    values = []
    for item in scrape_configs(receiver):
        if "scrape_interval" in item:
            values.append(parse_duration_seconds(item["scrape_interval"]))
    return values


def exporter_queue_ok(config: dict[str, Any], exporter_name: str) -> bool:
    exporter = config.get("exporters", {}).get(exporter_name, {})
    return (
        exporter.get("sending_queue", {}).get("enabled") is True
        and exporter.get("retry_on_failure", {}).get("enabled") is True
    )


def loopback_targets_ok(targets: list[str], required_targets: list[str]) -> bool:
    if not set(required_targets).issubset(set(targets)):
        return False
    return all(target.startswith("127.0.0.1:") or target.startswith("localhost:") for target in targets)


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    config_map = collector_config_map(docs, policy)
    config = collector_config(config_map) if config_map else {}
    collector = policy["collector"]
    receiver = self_metrics_receiver(config, policy)
    targets = scrape_targets(receiver)
    intervals = scrape_intervals(receiver)
    metrics_receivers = pipeline_receivers(config, collector["metrics_pipeline"])
    metrics_processors = pipeline_processors(config, collector["metrics_pipeline"])
    metrics_exporters = pipeline_exporters(config, collector["metrics_pipeline"])
    labels = metadata(config_map).get("labels", {}) if config_map else {}
    missing_labels = [label for label in policy.get("required_labels", []) if label not in labels]
    forbidden_processors = [
        item for item in metrics_processors if item in set(collector.get("forbidden_metrics_processors", []))
    ]

    checks = [
        check(
            "collector_config_map",
            bool(config_map) and bool(config),
            "Collector ConfigMap exists and its embedded OpenTelemetry config is parseable.",
            {"config_map": name(config_map) if config_map else None},
        ),
        check(
            "self_metrics_receiver_defined",
            bool(receiver),
            "Collector config defines a Prometheus receiver for collector internal metrics.",
            {"receiver": collector["self_metrics_receiver"], "defined": bool(receiver)},
        ),
        check(
            "self_metrics_scrape_job",
            collector["required_job_name"] in scrape_job_names(receiver),
            "Collector self-metrics scrape job has an explicit reviewable job name.",
            {"required": collector["required_job_name"], "observed": scrape_job_names(receiver)},
        ),
        check(
            "self_metrics_loopback_target",
            loopback_targets_ok(targets, list(collector["required_targets"])),
            "Collector self-metrics scrape target stays on loopback and is not exposed as a cross-pod service dependency.",
            {"required": collector["required_targets"], "observed": targets},
        ),
        check(
            "self_metrics_scrape_interval",
            bool(intervals) and max(intervals) <= float(collector["max_scrape_interval_seconds"]),
            "Collector self-metrics scrape interval is short enough for queue/exporter incident response.",
            {"interval_seconds": intervals, "max": collector["max_scrape_interval_seconds"]},
        ),
        check(
            "metrics_pipeline_collects_self_metrics",
            collector["self_metrics_receiver"] in metrics_receivers
            and set(collector["required_receivers"]).issubset(set(metrics_receivers)),
            "Metrics pipeline includes collector self-metrics alongside OTLP and Kubernetes cluster metrics.",
            {"required": collector["required_receivers"], "observed": metrics_receivers},
        ),
        check(
            "metrics_pipeline_processor_order",
            metrics_processors == collector["required_processors"],
            "Collector self-metrics are enriched and batched through the expected metrics processors.",
            {"required": collector["required_processors"], "observed": metrics_processors},
        ),
        check(
            "metrics_pipeline_excludes_trace_sampling",
            not forbidden_processors,
            "Trace-only sampling processors are not applied to collector self-metrics.",
            {"forbidden": collector.get("forbidden_metrics_processors", []), "observed": forbidden_processors},
        ),
        check(
            "self_metrics_exporter_path",
            collector["required_exporter"] in metrics_exporters,
            "Collector self-metrics leave through the same upstream telemetry gateway exporter as other metrics.",
            {"required": collector["required_exporter"], "observed": metrics_exporters},
        ),
        check(
            "self_metrics_exporter_queue",
            exporter_queue_ok(config, collector["required_exporter"]),
            "Collector self-metrics keep the queued exporter and retry path enabled.",
            {"exporter": collector["required_exporter"]},
        ),
        check(
            "collector_config_label_governance",
            not missing_labels,
            "Collector ConfigMap carries owner labels used by review and policy tooling.",
            {"missing_labels": missing_labels},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "receiver_count": len(config.get("receivers", {})) if config else 0,
        "self_metrics_target_count": len(targets),
        "scrape_job_count": len(scrape_configs(receiver)),
        "check_count": len(checks),
        "failed_count": len(failed),
        "checks": checks,
    }


def find_config_map(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    doc = collector_config_map(docs, policy)
    if not doc:
        collector = policy["collector"]
        raise ValueError(f"missing ConfigMap/{collector['namespace']}/{collector['config_map']}")
    return doc


def mutated_config_doc(docs: list[dict[str, Any]], policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    config_map = find_config_map(mutated, policy)
    config = collector_config(config_map)
    return mutated, config_map, config


def first_scrape_config(config: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    receiver = self_metrics_receiver(config, policy)
    configs = scrape_configs(receiver)
    if not configs:
        receiver.setdefault("config", {})["scrape_configs"] = [{}]
        configs = receiver["config"]["scrape_configs"]
    return configs[0]


def mutate_fixture(docs: list[dict[str, Any]], policy: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutated, config_map, config = mutated_config_doc(docs, policy)
    collector = policy["collector"]
    mutation = fixture["mutation"]
    metrics_pipeline = config.setdefault("service", {}).setdefault("pipelines", {}).setdefault(
        collector["metrics_pipeline"], {}
    )

    if mutation == "remove_receiver":
        config.setdefault("receivers", {}).pop(str(fixture["receiver"]), None)
    elif mutation == "remove_pipeline_receiver":
        receivers = pipeline_receivers(config, collector["metrics_pipeline"])
        metrics_pipeline["receivers"] = [item for item in receivers if item != str(fixture["receiver"])]
    elif mutation == "set_scrape_job_name":
        first_scrape_config(config, policy)["job_name"] = str(fixture["job_name"])
    elif mutation == "clear_scrape_targets":
        first_scrape_config(config, policy)["static_configs"] = [{"targets": []}]
    elif mutation == "set_scrape_target":
        first_scrape_config(config, policy)["static_configs"] = [{"targets": [str(fixture["target"])]}]
    elif mutation == "set_scrape_interval":
        first_scrape_config(config, policy)["scrape_interval"] = str(fixture["scrape_interval"])
    elif mutation == "add_pipeline_processor":
        processors = pipeline_processors(config, collector["metrics_pipeline"])
        if str(fixture["processor"]) not in processors:
            processors.append(str(fixture["processor"]))
        metrics_pipeline["processors"] = processors
    elif mutation == "remove_pipeline_processor":
        processors = pipeline_processors(config, collector["metrics_pipeline"])
        metrics_pipeline["processors"] = [item for item in processors if item != str(fixture["processor"])]
    elif mutation == "set_exporter_queue_enabled":
        exporter = config.setdefault("exporters", {}).setdefault(collector["required_exporter"], {})
        exporter.setdefault("sending_queue", {})["enabled"] = bool(fixture["enabled"])
    elif mutation == "remove_config_map_label":
        metadata(config_map).setdefault("labels", {}).pop(str(fixture["label"]), None)
    else:
        raise ValueError(f"unsupported fixture mutation: {mutation}")

    config_map.setdefault("data", {})["config.yaml"] = json.dumps(config)
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
        "Negative fixtures prove collector self-observability drift is detected before release readiness passes.",
        {
            "fixture_count": len(fixture_results),
            "detected_fixture_count": detected_fixture_count,
            "undetected": undetected,
        },
    )
    checks = audit["checks"] + [negative_fixture_check]
    failed_count = sum(1 for item in checks if item["status"] != PASS)
    return {
        "status": PASS if failed_count == 0 else FAIL,
        "receiver_count": audit["receiver_count"],
        "self_metrics_target_count": audit["self_metrics_target_count"],
        "scrape_job_count": audit["scrape_job_count"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "collector-self-observability-audit.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Collector Self-Observability Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that the OpenTelemetry Collector scrapes its own",
        "internal metrics on loopback, sends them through the metrics pipeline,",
        "and preserves queued export and retry behavior for collector health",
        "signals.",
        "",
        "## Summary",
        "",
        f"- Receivers: `{report['receiver_count']}`",
        f"- Self-metrics scrape jobs: `{report['scrape_job_count']}`",
        f"- Self-metrics targets: `{report['self_metrics_target_count']}`",
        f"- Detected negative fixtures: `{report['detected_fixture_count']}`",
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
    (output_dir / "collector-self-observability-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/collector-self-observability-policy.json")
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
    print(f"wrote {output_dir / 'collector-self-observability-audit.json'}")
    print(f"wrote {output_dir / 'collector-self-observability-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
