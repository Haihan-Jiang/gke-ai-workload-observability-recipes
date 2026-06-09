#!/usr/bin/env python3
"""Audit OpenTelemetry tail-sampling policy for AI inference traces."""

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


def sampling_processor(config: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    processors = config.get("processors", {})
    value = processors.get(policy["collector"]["sampling_processor"], {})
    return value if isinstance(value, dict) else {}


def pipeline_processors(config: dict[str, Any], pipeline_name: str) -> list[str]:
    pipelines = config.get("service", {}).get("pipelines", {})
    processors = pipelines.get(pipeline_name, {}).get("processors", [])
    return [str(item) for item in processors] if isinstance(processors, list) else []


def sampling_policies(sampler: dict[str, Any]) -> dict[str, dict[str, Any]]:
    policies = sampler.get("policies", [])
    if not isinstance(policies, list):
        return {}
    return {str(item.get("name", "")): item for item in policies if isinstance(item, dict)}


def policy_matches(observed: dict[str, Any], expected: dict[str, Any]) -> bool:
    if observed.get("type") != expected.get("type"):
        return False
    body = observed.get(str(expected["body"]), {})
    if not isinstance(body, dict):
        return False
    if expected["type"] == "status_code":
        return set(expected.get("status_codes", [])).issubset(set(body.get("status_codes", [])))
    if expected["type"] == "string_attribute":
        return body.get("key") == expected.get("key") and set(expected.get("values", [])).issubset(
            set(body.get("values", []))
        )
    if expected["type"] == "probabilistic":
        value = float(body.get("sampling_percentage", -1))
        return float(expected["min_sampling_percentage"]) <= value <= float(expected["max_sampling_percentage"])
    return False


def critical_policy_gaps(sampler: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    observed = sampling_policies(sampler)
    gaps = []
    for expected in policy.get("required_policies", []):
        if expected.get("type") == "probabilistic":
            continue
        item = observed.get(str(expected["name"]), {})
        if not item or not policy_matches(item, expected):
            gaps.append({"policy": expected["name"], "expected_type": expected["type"], "observed": item})
    return gaps


def baseline_sampling_policy(sampler: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    observed = sampling_policies(sampler)
    for expected in policy.get("required_policies", []):
        if expected.get("type") == "probabilistic":
            item = observed.get(str(expected["name"]), {})
            return {"expected": expected, "observed": item}
    return {"expected": {}, "observed": {}}


def exporter_queue_ok(config: dict[str, Any], policy: dict[str, Any]) -> bool:
    exporter_name = policy["collector"]["required_exporter"]
    exporter = config.get("exporters", {}).get(exporter_name, {})
    return (
        exporter.get("sending_queue", {}).get("enabled") is True
        and exporter.get("retry_on_failure", {}).get("enabled") is True
    )


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    config_map = collector_config_map(docs, policy)
    config = collector_config(config_map) if config_map else {}
    sampler = sampling_processor(config, policy)
    collector = policy["collector"]
    trace_processors = pipeline_processors(config, collector["trace_pipeline"])
    metrics_processors = pipeline_processors(config, collector["metrics_pipeline"])
    baseline = baseline_sampling_policy(sampler, policy)
    baseline_ok = bool(baseline["observed"]) and policy_matches(baseline["observed"], baseline["expected"])
    critical_gaps = critical_policy_gaps(sampler, policy)
    labels = metadata(config_map).get("labels", {}) if config_map else {}
    missing_labels = [label for label in policy.get("required_labels", []) if label not in labels]

    decision_wait_seconds = None
    if sampler:
        decision_wait_seconds = parse_duration_seconds(sampler.get("decision_wait", "0s"))

    checks = [
        check(
            "collector_config_map",
            bool(config_map) and bool(config),
            "Collector ConfigMap exists and its embedded OpenTelemetry config is parseable.",
            {"config_map": name(config_map) if config_map else None},
        ),
        check(
            "sampling_processor_defined",
            bool(sampler),
            "The collector defines a tail_sampling processor for trace retention control.",
            {"processor": collector["sampling_processor"], "defined": bool(sampler)},
        ),
        check(
            "trace_pipeline_sampling_order",
            trace_processors == collector["required_processor_order"],
            "Trace processors keep resource enrichment before tail sampling and batch export after sampling.",
            {"expected": collector["required_processor_order"], "observed": trace_processors},
        ),
        check(
            "metrics_pipeline_excludes_tail_sampling",
            collector["sampling_processor"] not in metrics_processors,
            "Tail sampling is only applied to traces, not metrics.",
            {"metrics_processors": metrics_processors},
        ),
        check(
            "sampling_decision_window",
            decision_wait_seconds is not None and decision_wait_seconds <= float(collector["max_decision_wait_seconds"]),
            "Tail sampling waits long enough for child spans but is bounded for incident latency.",
            {"decision_wait_seconds": decision_wait_seconds, "max": collector["max_decision_wait_seconds"]},
        ),
        check(
            "sampling_buffer",
            int(sampler.get("num_traces", 0)) >= int(collector["min_num_traces"])
            and int(sampler.get("expected_new_traces_per_sec", 0)) >= int(collector["min_expected_new_traces_per_sec"]),
            "The sampler has enough trace buffer and expected throughput for replayed AI inference bursts.",
            {
                "num_traces": sampler.get("num_traces"),
                "expected_new_traces_per_sec": sampler.get("expected_new_traces_per_sec"),
            },
        ),
        check(
            "critical_trace_policy_coverage",
            not critical_gaps,
            "Critical error, dependency-timeout, rollout-regression, and collector-pressure traces are kept.",
            {"gaps": critical_gaps},
        ),
        check(
            "baseline_sampling_budget",
            baseline_ok,
            "Healthy baseline traffic uses bounded probabilistic sampling instead of full retention.",
            {"expected": baseline["expected"], "observed": baseline["observed"]},
        ),
        check(
            "exporter_queue_preserved",
            exporter_queue_ok(config, policy),
            "Tail sampling keeps the durable queued exporter and retry path enabled.",
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
        "policy_count": len(sampling_policies(sampler)),
        "critical_policy_count": len(policy.get("required_policies", [])) - 1,
        "baseline_sampling_percentage": baseline.get("observed", {}).get("probabilistic", {}).get("sampling_percentage"),
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


def mutated_config_doc(
    docs: list[dict[str, Any]], policy: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    config_map = find_config_map(mutated, policy)
    config = collector_config(config_map)
    sampler = sampling_processor(config, policy)
    return mutated, config_map, config, sampler


def mutate_fixture(docs: list[dict[str, Any]], policy: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutated, config_map, config, sampler = mutated_config_doc(docs, policy)
    collector = policy["collector"]
    mutation = fixture["mutation"]

    if mutation == "remove_sampling_processor":
        config.setdefault("processors", {}).pop(collector["sampling_processor"], None)
    elif mutation == "remove_pipeline_processor":
        processors = pipeline_processors(config, str(fixture["pipeline"]))
        config["service"]["pipelines"][str(fixture["pipeline"])]["processors"] = [
            item for item in processors if item != str(fixture["processor"])
        ]
    elif mutation == "move_processor_after":
        processors = [item for item in pipeline_processors(config, str(fixture["pipeline"])) if item != str(fixture["processor"])]
        after_index = processors.index(str(fixture["after"])) if str(fixture["after"]) in processors else len(processors) - 1
        processors.insert(after_index + 1, str(fixture["processor"]))
        config["service"]["pipelines"][str(fixture["pipeline"])]["processors"] = processors
    elif mutation == "add_pipeline_processor":
        processors = pipeline_processors(config, str(fixture["pipeline"]))
        if str(fixture["processor"]) not in processors:
            processors.append(str(fixture["processor"]))
        config["service"]["pipelines"][str(fixture["pipeline"])]["processors"] = processors
    elif mutation == "set_sampling_field":
        sampler[str(fixture["field"])] = fixture["value"]
    elif mutation == "remove_policy":
        sampler["policies"] = [
            item for item in sampler.get("policies", []) if item.get("name") != str(fixture["policy"])
        ]
    elif mutation == "set_policy_attribute_key":
        for item in sampler.get("policies", []):
            if item.get("name") == str(fixture["policy"]):
                body = item.get(str(item.get("type")), {})
                body["key"] = str(fixture["key"])
    elif mutation == "set_policy_sampling_percentage":
        for item in sampler.get("policies", []):
            if item.get("name") == str(fixture["policy"]):
                item.setdefault("probabilistic", {})["sampling_percentage"] = int(fixture["sampling_percentage"])
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
        "Negative fixtures prove tail-sampling drift is detected before release readiness passes.",
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
        "policy_count": audit["policy_count"],
        "critical_policy_count": audit["critical_policy_count"],
        "baseline_sampling_percentage": audit["baseline_sampling_percentage"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "telemetry-sampling-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Telemetry Sampling Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that OpenTelemetry tail sampling keeps critical AI",
        "inference traces for errors, dependency timeouts, rollout regressions,",
        "and collector pressure while bounding healthy baseline trace volume.",
        "",
        "## Summary",
        "",
        f"- Sampling policies: `{report['policy_count']}`",
        f"- Critical policies: `{report['critical_policy_count']}`",
        f"- Baseline sampling percentage: `{report['baseline_sampling_percentage']}`",
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
    (output_dir / "telemetry-sampling-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/telemetry-sampling-policy.json")
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
    print(f"wrote {output_dir / 'telemetry-sampling-audit.json'}")
    print(f"wrote {output_dir / 'telemetry-sampling-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
