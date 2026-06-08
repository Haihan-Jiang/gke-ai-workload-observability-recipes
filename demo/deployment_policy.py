#!/usr/bin/env python3
"""Evaluate production promotion policy from reliability evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


BLOCK = "block"
REVIEW = "review"
PASS = "pass"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def control(name: str, severity: str, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "severity": severity,
        "reason": reason,
        "evidence": evidence,
    }


def evaluate(
    *,
    gate: dict[str, Any],
    burn_rate: dict[str, Any],
    rollout_guard: dict[str, Any],
    trace_quality: dict[str, Any],
    collector_resilience: dict[str, Any],
    hpa_lag: dict[str, Any],
    tenant_blast_radius: dict[str, Any],
    token_cost_guard: dict[str, Any],
) -> dict[str, Any]:
    controls = [
        evaluate_reliability_gate(gate),
        evaluate_burn_rate(burn_rate),
        evaluate_rollout_guard(rollout_guard),
        evaluate_trace_quality(trace_quality),
        evaluate_collector_resilience(collector_resilience),
        evaluate_hpa_lag(hpa_lag),
        evaluate_tenant_blast_radius(tenant_blast_radius),
        evaluate_token_cost_guard(token_cost_guard),
    ]
    if any(item["severity"] == BLOCK for item in controls):
        decision = "block_production_promotion"
    elif any(item["severity"] == REVIEW for item in controls):
        decision = "manual_review_required"
    else:
        decision = "promote"

    return {
        "status": "generated",
        "decision": decision,
        "human_approval_required": decision != "promote",
        "control_count": len(controls),
        "blocking_controls": [item["name"] for item in controls if item["severity"] == BLOCK],
        "review_controls": [item["name"] for item in controls if item["severity"] == REVIEW],
        "controls": controls,
        "operator_actions": build_operator_actions(controls),
    }


def evaluate_reliability_gate(gate: dict[str, Any]) -> dict[str, Any]:
    status = str(gate.get("status", "unknown"))
    if status != "pass":
        return control(
            "reliability_gate",
            BLOCK,
            "SLO gate did not pass.",
            {"status": status},
        )
    return control("reliability_gate", PASS, "SLO gate passed.", {"status": status})


def evaluate_burn_rate(burn_rate: dict[str, Any]) -> dict[str, Any]:
    windows = burn_rate.get("windows", [])
    page_windows = [item for item in windows if item.get("action") == "page"]
    ticket_windows = [item for item in windows if item.get("action") == "ticket"]
    if page_windows:
        return control(
            "burn_rate",
            BLOCK,
            "One or more burn-rate windows require paging.",
            {"windows": summarize_windows(page_windows)},
        )
    if ticket_windows:
        return control(
            "burn_rate",
            REVIEW,
            "One or more burn-rate windows require ticket follow-up.",
            {"windows": summarize_windows(ticket_windows)},
        )
    return control("burn_rate", PASS, "Burn-rate windows are inside policy.", {"windows": summarize_windows(windows)})


def summarize_windows(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "window": item.get("window"),
            "burn_rate": item.get("burn_rate"),
            "action": item.get("action"),
        }
        for item in windows
    ]


def evaluate_rollout_guard(rollout_guard: dict[str, Any]) -> dict[str, Any]:
    decision = str(rollout_guard.get("decision", "unknown"))
    if decision == "rollback":
        return control(
            "rollout_guard",
            BLOCK,
            "Canary rollout guard recommends rollback.",
            {
                "candidate": rollout_guard.get("candidate"),
                "candidate_version": rollout_guard.get("candidate_version"),
                "violations": rollout_guard.get("violations", []),
            },
        )
    if decision != "promote":
        return control("rollout_guard", REVIEW, "Canary decision is not promote.", {"decision": decision})
    return control("rollout_guard", PASS, "Canary rollout guard allows promotion.", {"decision": decision})


def evaluate_trace_quality(trace_quality: dict[str, Any]) -> dict[str, Any]:
    status = str(trace_quality.get("status", "unknown"))
    if status != "pass":
        return control(
            "trace_quality",
            BLOCK,
            "Trace evidence is incomplete or too high-cardinality.",
            {
                "status": status,
                "resource_missing": trace_quality.get("resource_missing", {}),
                "root_missing": trace_quality.get("root_missing", {}),
                "child_span_missing": trace_quality.get("child_span_missing", {}),
            },
        )
    return control(
        "trace_quality",
        PASS,
        "Trace evidence has required resource, root-span, and child-span fields.",
        {"payloads": trace_quality.get("payloads"), "spans": trace_quality.get("spans")},
    )


def evaluate_collector_resilience(collector_resilience: dict[str, Any]) -> dict[str, Any]:
    risk = str(collector_resilience.get("risk", "unknown"))
    if risk == "data_loss":
        return control(
            "collector_resilience",
            BLOCK,
            "Collector queue or storage model predicts data loss.",
            {
                "queue_utilization": collector_resilience.get("queue_utilization"),
                "estimated_lost_spans": collector_resilience.get("estimated_lost_spans"),
                "required_storage_mib": collector_resilience.get("required_storage_mib"),
                "configured_storage_mib": collector_resilience.get("configured_storage_mib"),
            },
        )
    if risk != "ok":
        return control("collector_resilience", REVIEW, "Collector resilience risk is unknown.", {"risk": risk})
    return control(
        "collector_resilience",
        PASS,
        "Collector queue and persistent storage are inside modeled outage budget.",
        {"queue_utilization": collector_resilience.get("queue_utilization")},
    )


def evaluate_hpa_lag(hpa_lag: dict[str, Any]) -> dict[str, Any]:
    risky = [
        item
        for item in hpa_lag.get("scenarios", [])
        if item.get("decision") in {"fix_dependency_or_rollout", "pre_scale_or_raise_hpa_budget"}
    ]
    if any(item.get("decision") == "fix_dependency_or_rollout" for item in risky):
        return control(
            "hpa_lag",
            REVIEW,
            "Some scenarios are not solved by autoscaling and need dependency or rollout remediation.",
            {"scenarios": summarize_scenarios(risky)},
        )
    if risky:
        return control(
            "hpa_lag",
            REVIEW,
            "Some scenarios need pre-scaling or higher HPA budget.",
            {"scenarios": summarize_scenarios(risky)},
        )
    return control("hpa_lag", PASS, "HPA recovery model is inside policy.", {"scenarios": len(hpa_lag.get("scenarios", []))})


def evaluate_tenant_blast_radius(tenant_blast_radius: dict[str, Any]) -> dict[str, Any]:
    breached = tenant_blast_radius.get("breached_scenarios", [])
    if breached:
        return control(
            "tenant_blast_radius",
            BLOCK,
            "Tenant SLO breach detected.",
            {"breached_scenarios": breached},
        )
    return control("tenant_blast_radius", PASS, "No tenant SLO breach detected.", {"breached_scenarios": []})


def evaluate_token_cost_guard(token_cost_guard: dict[str, Any]) -> dict[str, Any]:
    blocked = [
        item
        for item in token_cost_guard.get("scenarios", [])
        if item.get("decision") == "block_or_review"
    ]
    if blocked:
        return control(
            "token_cost_guard",
            REVIEW,
            "Token/GPU cost policy requires review.",
            {"scenarios": summarize_scenarios(blocked)},
        )
    return control("token_cost_guard", PASS, "Token/GPU cost policy is inside budget.", {"scenarios": len(token_cost_guard.get("scenarios", []))})


def summarize_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for item in scenarios:
        summary.append(
            {
                "scenario": item.get("scenario"),
                "decision": item.get("decision") or item.get("blast_radius"),
                "violations": item.get("violations", []),
            }
        )
    return summary


def build_operator_actions(controls: list[dict[str, Any]]) -> list[str]:
    actions = []
    for item in controls:
        if item["severity"] == PASS:
            continue
        if item["name"] == "burn_rate":
            actions.append("Freeze rollout until burn-rate paging windows return below threshold.")
        elif item["name"] == "rollout_guard":
            actions.append("Rollback or hold the candidate version before expanding traffic.")
        elif item["name"] == "trace_quality":
            actions.append("Fix trace resource/span attributes before relying on incident evidence.")
        elif item["name"] == "collector_resilience":
            actions.append("Increase collector queue/storage or reduce outage exposure.")
        elif item["name"] == "hpa_lag":
            actions.append("Separate dependency or rollout remediation from autoscaling changes.")
        elif item["name"] == "tenant_blast_radius":
            actions.append("Protect impacted tenant tier before aggregate service promotion.")
        elif item["name"] == "token_cost_guard":
            actions.append("Review token/GPU regression before approving the model variant.")
        else:
            actions.append(f"Resolve `{item['name']}` before production promotion.")
    return actions


def write_json(report: dict[str, Any], output_dir: Path) -> None:
    (output_dir / "deployment-policy.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def write_markdown(report: dict[str, Any], output_dir: Path) -> None:
    lines = [
        "# Deployment Policy Decision",
        "",
        f"Decision: **{report['decision']}**",
        "",
        "This policy-as-code report combines replay evidence into a production",
        "promotion decision. It is intentionally stricter than a demo summary:",
        "a release can have valid telemetry and still be blocked by burn-rate,",
        "tenant impact, or cost signals.",
        "",
        "## Controls",
        "",
        "| Control | Severity | Reason |",
        "| --- | --- | --- |",
    ]
    for item in report["controls"]:
        lines.append(f"| `{item['name']}` | `{item['severity']}` | {item['reason']} |")
    lines.extend(["", "## Operator Actions", ""])
    if report["operator_actions"]:
        for action in report["operator_actions"]:
            lines.append(f"- {action}")
    else:
        lines.append("- none")
    lines.append("")
    (output_dir / "deployment-policy.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", default="docs/evidence/reliability-gate.json")
    parser.add_argument("--burn-rate", default="docs/evidence/burn-rate-analysis.json")
    parser.add_argument("--rollout-guard", default="docs/evidence/rollout-guard.json")
    parser.add_argument("--trace-quality", default="docs/evidence/trace-quality-audit.json")
    parser.add_argument("--collector-resilience", default="docs/evidence/collector-resilience.json")
    parser.add_argument("--hpa-lag", default="docs/evidence/hpa-lag-analysis.json")
    parser.add_argument("--tenant-blast-radius", default="docs/evidence/tenant-blast-radius.json")
    parser.add_argument("--token-cost-guard", default="docs/evidence/token-cost-guard.json")
    parser.add_argument("--output-dir", default="out/deployment-policy")
    args = parser.parse_args()

    report = evaluate(
        gate=load_json(Path(args.gate)),
        burn_rate=load_json(Path(args.burn_rate)),
        rollout_guard=load_json(Path(args.rollout_guard)),
        trace_quality=load_json(Path(args.trace_quality)),
        collector_resilience=load_json(Path(args.collector_resilience)),
        hpa_lag=load_json(Path(args.hpa_lag)),
        tenant_blast_radius=load_json(Path(args.tenant_blast_radius)),
        token_cost_guard=load_json(Path(args.token_cost_guard)),
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, output_dir)
    write_markdown(report, output_dir)
    print(f"wrote {output_dir / 'deployment-policy.json'}")
    print(f"wrote {output_dir / 'deployment-policy.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
