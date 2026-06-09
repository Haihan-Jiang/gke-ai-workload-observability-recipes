#!/usr/bin/env python3
"""Audit NetworkPolicy boundaries for workload and telemetry namespaces."""

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


def load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    ruby = shutil.which("ruby")
    if not ruby:
        raise RuntimeError("ruby is required to parse Kubernetes YAML manifests for the audit")
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


def selector(doc: dict[str, Any]) -> dict[str, Any]:
    labels = doc.get("spec", {}).get("podSelector", {}).get("matchLabels", {})
    return labels if isinstance(labels, dict) else {}


def ports(rule: dict[str, Any]) -> set[int]:
    observed: set[int] = set()
    for item in rule.get("ports", []):
        value = item.get("port")
        if isinstance(value, int):
            observed.add(value)
        elif isinstance(value, str) and value.isdigit():
            observed.add(int(value))
    return observed


def protocols(rule: dict[str, Any]) -> set[str]:
    observed = set()
    for item in rule.get("ports", []):
        observed.add(str(item.get("protocol", "TCP")))
    return observed


def peer_matches(peer: dict[str, Any], namespace_selector: dict[str, str], pod_selector: dict[str, str] | None = None) -> bool:
    observed_ns = peer.get("namespaceSelector", {}).get("matchLabels", {})
    observed_pod = peer.get("podSelector", {}).get("matchLabels", {})
    pod_selector = pod_selector or {}
    return all(observed_ns.get(key) == value for key, value in namespace_selector.items()) and all(
        observed_pod.get(key) == value for key, value in pod_selector.items()
    )


def rule_matches(
    rule: dict[str, Any],
    peer_key: str,
    namespace_selector: dict[str, str],
    required_ports: list[int],
    pod_selector: dict[str, str] | None = None,
    required_protocols: set[str] | None = None,
) -> bool:
    required_protocols = required_protocols or {"TCP"}
    return any(peer_matches(peer, namespace_selector, pod_selector) for peer in rule.get(peer_key, [])) and set(
        required_ports
    ).issubset(ports(rule)) and required_protocols.issubset(protocols(rule))


def has_unbounded_egress(policy: dict[str, Any]) -> bool:
    for rule in policy.get("spec", {}).get("egress", []):
        if not rule.get("to") and not rule.get("ports"):
            return True
        if not rule.get("to"):
            return True
        for peer in rule.get("to", []):
            ip_block = peer.get("ipBlock", {})
            if ip_block.get("cidr") == "0.0.0.0/0" and not ip_block.get("except"):
                return True
    return False


def find_doc(docs: list[dict[str, Any]], kind: str, doc_namespace: str, doc_name: str) -> dict[str, Any]:
    for doc in docs:
        if doc.get("kind") == kind and namespace(doc) == doc_namespace and name(doc) == doc_name:
            return doc
    raise ValueError(f"missing {kind}/{doc_namespace}/{doc_name}")


def remove_doc(docs: list[dict[str, Any]], kind: str, doc_namespace: str, doc_name: str) -> list[dict[str, Any]]:
    return [
        doc
        for doc in docs
        if not (doc.get("kind") == kind and namespace(doc) == doc_namespace and name(doc) == doc_name)
    ]


def workload_policy(policy: dict[str, Any], index: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
    workload = policy["workload"]
    return index.get(("NetworkPolicy", workload["namespace"], workload["network_policy"]), {})


def collector_policy(policy: dict[str, Any], index: dict[tuple[str, str, str], dict[str, Any]]) -> dict[str, Any]:
    collector = policy["collector"]
    return index.get(("NetworkPolicy", collector["namespace"], collector["network_policy"]), {})


def egress_rule(policy_doc: dict[str, Any], kind: str, policy: dict[str, Any]) -> dict[str, Any]:
    workload = policy["workload"]
    if kind == "telemetry":
        for rule in policy_doc.get("spec", {}).get("egress", []):
            if rule_matches(
                rule,
                "to",
                workload["telemetry_namespace_selector"],
                workload["telemetry_ports"],
                workload["telemetry_pod_selector"],
                {"TCP"},
            ):
                return rule
    if kind == "dns":
        for rule in policy_doc.get("spec", {}).get("egress", []):
            if rule_matches(
                rule,
                "to",
                workload["dns_namespace_selector"],
                workload["dns_ports"],
                workload["dns_pod_selector"],
                {"TCP", "UDP"},
            ):
                return rule
    return {}


def evaluate_documents(docs: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    index = index_documents(docs)
    workload = policy["workload"]
    collector = policy["collector"]
    workload_np = workload_policy(policy, index)
    collector_np = collector_policy(policy, index)
    telemetry_rule = egress_rule(workload_np, "telemetry", policy) if workload_np else {}
    dns_rule = egress_rule(workload_np, "dns", policy) if workload_np else {}
    collector_ingress_rules = collector_np.get("spec", {}).get("ingress", []) if collector_np else []
    collector_ingress_ok = any(
        rule_matches(rule, "from", collector["workload_namespace_selector"], collector["otlp_ports"], None, {"TCP"})
        for rule in collector_ingress_rules
    )
    missing_labels = []
    for label in policy.get("required_labels", []):
        for role, doc in (("workload", workload_np), ("collector", collector_np)):
            if not doc or label not in metadata(doc).get("labels", {}):
                missing_labels.append({"policy": role, "label": label})

    checks = [
        check(
            "workload_egress_policy",
            bool(workload_np),
            "The sample workload has an egress NetworkPolicy.",
            {"network_policy": name(workload_np) if workload_np else None},
        ),
        check(
            "workload_policy_selector",
            selector(workload_np) == workload["pod_selector"],
            "The workload egress policy selects only the sample inference pods.",
            {"observed": selector(workload_np), "expected": workload["pod_selector"]},
        ),
        check(
            "workload_egress_policy_type",
            "Egress" in workload_np.get("spec", {}).get("policyTypes", []),
            "The workload policy explicitly enables egress isolation.",
            {"policy_types": workload_np.get("spec", {}).get("policyTypes", [])},
        ),
        check(
            "telemetry_egress",
            bool(telemetry_rule),
            "Workload egress is allowed to the telemetry collector namespace and pods.",
            {"rule": telemetry_rule},
        ),
        check(
            "telemetry_ports",
            bool(telemetry_rule) and set(workload["telemetry_ports"]).issubset(ports(telemetry_rule)),
            "Workload telemetry egress allows the expected OTLP ports.",
            {"required_ports": workload["telemetry_ports"], "observed_ports": sorted(ports(telemetry_rule))},
        ),
        check(
            "dns_egress",
            bool(dns_rule),
            "Workload egress keeps a bounded DNS exception for Kubernetes service discovery.",
            {"rule": dns_rule},
        ),
        check(
            "deny_unbounded_egress",
            bool(workload_np) and not has_unbounded_egress(workload_np),
            "Workload egress policy does not include allow-all egress peers or empty egress rules.",
            {"unbounded": has_unbounded_egress(workload_np) if workload_np else None},
        ),
        check(
            "collector_ingress_boundary",
            bool(collector_np) and collector_ingress_ok,
            "Collector ingress remains scoped to workload namespaces on OTLP ports.",
            {"network_policy": name(collector_np) if collector_np else None},
        ),
        check(
            "network_policy_label_governance",
            not missing_labels,
            "NetworkPolicies carry owner labels used by review and policy tooling.",
            {"missing_labels": missing_labels},
        ),
    ]
    failed = [item for item in checks if item["status"] != PASS]
    return {
        "status": PASS if not failed else FAIL,
        "network_policy_count": sum(1 for doc in docs if doc.get("kind") == "NetworkPolicy"),
        "egress_rule_count": len(workload_np.get("spec", {}).get("egress", [])) if workload_np else 0,
        "check_count": len(checks),
        "failed_count": len(failed),
        "checks": checks,
    }


def mutate_fixture(docs: list[dict[str, Any]], policy: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(docs)
    workload = policy["workload"]
    collector = policy["collector"]
    mutation = fixture["mutation"]
    if mutation == "remove_workload_policy":
        return remove_doc(mutated, "NetworkPolicy", workload["namespace"], workload["network_policy"])
    workload_np = find_doc(mutated, "NetworkPolicy", workload["namespace"], workload["network_policy"])
    collector_np = find_doc(mutated, "NetworkPolicy", collector["namespace"], collector["network_policy"])
    if mutation == "set_workload_pod_selector":
        workload_np.setdefault("spec", {}).setdefault("podSelector", {}).setdefault("matchLabels", {})[
            str(fixture["label"])
        ] = str(fixture["value"])
    elif mutation == "remove_policy_type":
        target = workload_np if fixture["policy"] == "workload" else collector_np
        target.setdefault("spec", {})["policyTypes"] = [
            item for item in target.get("spec", {}).get("policyTypes", []) if item != fixture["value"]
        ]
    elif mutation == "remove_egress_kind":
        kind = str(fixture["kind"])
        workload_np.setdefault("spec", {})["egress"] = [
            rule
            for rule in workload_np.get("spec", {}).get("egress", [])
            if not (rule == egress_rule(workload_np, kind, policy))
        ]
    elif mutation == "set_egress_namespace_selector":
        rule = egress_rule(workload_np, str(fixture["kind"]), policy)
        rule["to"][0].setdefault("namespaceSelector", {}).setdefault("matchLabels", {})[
            str(fixture["label"])
        ] = str(fixture["value"])
    elif mutation == "remove_egress_port":
        rule = egress_rule(workload_np, str(fixture["kind"]), policy)
        rule["ports"] = [item for item in rule.get("ports", []) if item.get("port") != int(fixture["port"])]
    elif mutation == "add_allow_all_egress":
        workload_np.setdefault("spec", {}).setdefault("egress", []).append({})
    elif mutation == "set_collector_ingress_namespace_selector":
        collector_np.setdefault("spec", {}).setdefault("ingress", [])[0]["from"][0].setdefault(
            "namespaceSelector", {}
        ).setdefault("matchLabels", {})[str(fixture["label"])] = str(fixture["value"])
    elif mutation == "remove_owner_label":
        target = workload_np if fixture["policy"] == "workload" else collector_np
        metadata(target).setdefault("labels", {}).pop(str(fixture["label"]), None)
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
        "Negative fixtures prove workload egress, DNS, telemetry, collector ingress, and label drift is detected.",
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
        "network_policy_count": audit["network_policy_count"],
        "egress_rule_count": audit["egress_rule_count"],
        "check_count": len(checks),
        "detected_fixture_count": detected_fixture_count,
        "failed_count": failed_count,
        "fixture_results": fixture_results,
        "checks": checks,
    }


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "network-boundary-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Network Boundary Audit",
        "",
        f"Overall status: **{str(report['status']).upper()}**",
        "",
        "This audit checks that the sample inference workload has bounded",
        "egress to telemetry and DNS, while the collector keeps inbound OTLP",
        "traffic scoped to workload namespaces. It also rejects allow-all egress",
        "rules and verifies NetworkPolicy owner labels.",
        "",
        "## Summary",
        "",
        f"- NetworkPolicies: `{report['network_policy_count']}`",
        f"- Workload egress rules: `{report['egress_rule_count']}`",
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
    (output_dir / "network-boundary-audit.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="config/network-boundary-policy.json")
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
    print(f"wrote {output_dir / 'network-boundary-audit.json'}")
    print(f"wrote {output_dir / 'network-boundary-audit.md'}")
    return 0 if report["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
