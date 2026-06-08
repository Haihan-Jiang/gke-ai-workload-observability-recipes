#!/usr/bin/env python3
"""Render incident replay output into committed portfolio evidence."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def load_summary(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("summary must be a JSON list")
    return data


def write_json(summary: list[dict[str, Any]], output_dir: Path) -> None:
    (output_dir / "sample-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown(summary: list[dict[str, Any]], output_dir: Path) -> None:
    lines = [
        "# Sample Incident Replay Evidence",
        "",
        "This is a committed sample output from the local incident replay. It lets a",
        "reviewer inspect the result without running Docker, GKE, or a cloud account.",
        "",
        "![Incident replay dashboard](incident-dashboard.svg)",
        "",
        "| Scenario | Requests | Errors | p50 ms | p95 ms | Cache miss rate | Telemetry loss | Queue pressure | Triage signal |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in summary:
        lines.append(
            "| {scenario} | {requests} | {errors} | {p50_ms} | {p95_ms} | {cache_miss_rate} | {telemetry_loss_rate} | {collector_queue_pressure} | {triage} |".format(
                **item
            )
        )

    lines.extend(
        [
            "",
            "## How To Read This",
            "",
            "- `baseline` is the control group for healthy inference traffic.",
            "- `cache_miss_storm` points to the cache path instead of the model path.",
            "- `dependency_timeout` isolates feature-store latency and user-visible errors.",
            "- `rollout_regression` ties degraded behavior to `service.version=v2`.",
            "- `collector_queue_pressure` separates app health from telemetry delivery loss.",
            "",
            "## Why It Matters",
            "",
            "The evidence is intentionally small, but it is shaped like an SRE debugging",
            "artifact: a scenario, measurable signal, trace attributes, and a concrete",
            "triage decision.",
            "",
        ]
    )
    (output_dir / "sample-incident-report.md").write_text("\n".join(lines), encoding="utf-8")


def bar_width(value: float, max_value: float, width: int = 280) -> int:
    if max_value <= 0:
        return 0
    return max(2, round((value / max_value) * width))


def write_svg(summary: list[dict[str, Any]], output_dir: Path) -> None:
    row_height = 86
    top = 92
    width = 980
    height = top + row_height * len(summary) + 90
    max_p95 = max(float(item["p95_ms"]) for item in summary)
    max_errors = max(float(item["errors"]) for item in summary) or 1.0
    colors = {
        "baseline": "#2f855a",
        "cache_miss_storm": "#b7791f",
        "dependency_timeout": "#c53030",
        "rollout_regression": "#2b6cb0",
    }

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        '<text x="40" y="46" font-family="Arial, sans-serif" font-size="26" font-weight="700" fill="#111827">GKE AI Inference Reliability Lab</text>',
        '<text x="40" y="74" font-family="Arial, sans-serif" font-size="14" fill="#4b5563">Sample output: latency, errors, and cache behavior across replayed inference incidents.</text>',
        '<text x="310" y="118" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#374151">p95 latency</text>',
        '<text x="650" y="118" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#374151">errors</text>',
        '<text x="775" y="118" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#374151">telemetry loss</text>',
    ]

    for index, item in enumerate(summary):
        y = top + index * row_height + 44
        scenario = str(item["scenario"])
        p95 = float(item["p95_ms"])
        errors = float(item["errors"])
        telemetry_loss_rate = float(item["telemetry_loss_rate"])
        color = colors.get(scenario, "#4b5563")
        parts.extend(
            [
                f'<rect x="32" y="{y - 34}" width="916" height="68" rx="8" fill="#ffffff" stroke="#e5e7eb"/>',
                f'<text x="54" y="{y - 8}" font-family="Arial, sans-serif" font-size="15" font-weight="700" fill="#111827">{html.escape(scenario)}</text>',
                f'<text x="54" y="{y + 16}" font-family="Arial, sans-serif" font-size="12" fill="#6b7280">{html.escape(str(item["triage"]))}</text>',
                f'<rect x="310" y="{y - 21}" width="{bar_width(p95, max_p95)}" height="18" rx="4" fill="{color}"/>',
                f'<text x="310" y="{y + 14}" font-family="Arial, sans-serif" font-size="13" fill="#374151">{int(p95)} ms</text>',
                f'<rect x="650" y="{y - 21}" width="{bar_width(errors, max_errors, 80)}" height="18" rx="4" fill="#dc2626"/>',
                f'<text x="650" y="{y + 14}" font-family="Arial, sans-serif" font-size="13" fill="#374151">{int(errors)} errors</text>',
                f'<rect x="775" y="{y - 21}" width="{bar_width(telemetry_loss_rate, 1.0, 120)}" height="18" rx="4" fill="#7c3aed"/>',
                f'<text x="775" y="{y + 14}" font-family="Arial, sans-serif" font-size="13" fill="#374151">{telemetry_loss_rate:.2f}</text>',
            ]
        )

    parts.extend(
        [
            f'<text x="40" y="{height - 36}" font-family="Arial, sans-serif" font-size="13" fill="#4b5563">Generated from demo/incident_replay.py with no cloud account required.</text>',
            "</svg>",
            "",
        ]
    )
    (output_dir / "incident-dashboard.svg").write_text("\n".join(parts), encoding="utf-8")


def write_index(output_dir: Path) -> None:
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                "# Evidence",
                "",
                "- [Sample incident report](sample-incident-report.md)",
                "- [Sample summary JSON](sample-summary.json)",
                "- [Incident replay dashboard](incident-dashboard.svg)",
                "- [Reliability gate report](reliability-gate.md)",
                "- [Reliability gate JSON](reliability-gate.json)",
                "- [Capacity plan](capacity-plan.md)",
                "- [Capacity plan JSON](capacity-plan.json)",
                "- [Incident runbooks](incident-runbooks.md)",
                "- [Incident runbooks JSON](incident-runbooks.json)",
                "- [Burn rate analysis](burn-rate-analysis.md)",
                "- [Rollout guard](rollout-guard.md)",
                "- [Trace quality audit](trace-quality-audit.md)",
                "- [Collector resilience model](collector-resilience.md)",
                "- [Incident correlation](incident-correlation.md)",
                "- [Complex problem coverage](complex-problems.md)",
                "- [Critical path attribution](critical-path-attribution.md)",
                "- [Evidence coverage](evidence-coverage.md)",
                "- [HPA lag analysis](hpa-lag-analysis.md)",
                "- [Tenant blast radius](tenant-blast-radius.md)",
                "- [Token cost guard](token-cost-guard.md)",
                "- [Detailed problem coverage](detailed-problems.md)",
                "- [Deployment policy decision](deployment-policy.md)",
                "- [Policy regression suite](policy-regression-suite.md)",
                "- [Supply chain audit](supply-chain-audit.md)",
                "- [Kubernetes manifest hardening audit](k8s-hardening-audit.md)",
                "- [Pod Security Admission audit](pod-security-admission-audit.md)",
                "- [Namespace resource audit](namespace-resource-audit.md)",
                "- [Availability topology audit](availability-topology-audit.md)",
                "- [Autoscaling policy audit](autoscaling-policy-audit.md)",
                "- [Scheduling placement audit](scheduling-placement-audit.md)",
                "- [Rollout safety audit](rollout-safety-audit.md)",
                "- [Config rollout audit](config-rollout-audit.md)",
                "- [Network boundary audit](network-boundary-audit.md)",
                "- [Collector self-observability audit](collector-self-observability-audit.md)",
                "- [Telemetry sampling audit](telemetry-sampling-audit.md)",
                "- [Workload Identity audit](workload-identity-audit.md)",
                "- [Admission policy audit](admission-policy-audit.md)",
                "- [SLO alerting rules](alerting-rules.md)",
                "- [Grafana dashboard evidence](grafana-dashboard.md)",
                "- [OpenSLO contract evidence](openslo-contract.md)",
                "- [Observability drift audit](observability-drift-audit.md)",
                "- [Telemetry redaction audit](telemetry-redaction-audit.md)",
                "- [Telemetry cost budget](telemetry-cost-budget.md)",
                "- [Error budget ledger](error-budget-ledger.md)",
                "- [Rollback drill](rollback-drill.md)",
                "- [Post-incident review](post-incident-review.md)",
                "- [Incident response drill](incident-response-drill.md)",
                "- [Dependency contract audit](dependency-contract-audit.md)",
                "- [Synthetic probe audit](synthetic-probe-audit.md)",
                "- [Model release safety audit](model-release-safety-audit.md)",
                "- [Shadow traffic replay audit](shadow-traffic-replay-audit.md)",
                "- [Accelerator quota fairness audit](accelerator-quota-fairness-audit.md)",
                "- [Load shedding policy audit](load-shedding-policy-audit.md)",
                "- [Regional failover audit](regional-failover-audit.md)",
                "- [Release waiver governance](release-waiver-governance.md)",
                "- [Disaster recovery drill](disaster-recovery-drill.md)",
                "- [Evidence provenance](evidence-provenance.md)",
                "- [Release readiness report](release-readiness.md)",
                "- [Release readiness JSON](release-readiness.json)",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to incident replay summary JSON")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = load_summary(Path(args.input))
    write_json(summary, output_dir)
    write_markdown(summary, output_dir)
    write_svg(summary, output_dir)
    write_index(output_dir)
    print(f"wrote evidence to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
