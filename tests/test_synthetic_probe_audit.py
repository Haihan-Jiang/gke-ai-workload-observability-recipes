from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import synthetic_probe_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class SyntheticProbeAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = synthetic_probe_audit.load_json(REPO_ROOT / "config/synthetic-probe-policy.json")
        self.summary = synthetic_probe_audit.load_json(REPO_ROOT / "docs/evidence/sample-summary.json")
        self.alerting = synthetic_probe_audit.load_json(REPO_ROOT / "docs/evidence/alerting-rules.json")
        self.dependency_contract = synthetic_probe_audit.load_json(
            REPO_ROOT / "docs/evidence/dependency-contract-audit.json"
        )
        self.incident_response = synthetic_probe_audit.load_json(
            REPO_ROOT / "docs/evidence/incident-response-drill.json"
        )
        self.rollback_drill = synthetic_probe_audit.load_json(REPO_ROOT / "docs/evidence/rollback-drill.json")
        self.error_budget = synthetic_probe_audit.load_json(REPO_ROOT / "docs/evidence/error-budget-ledger.json")

    def build_report(
        self,
        *,
        policy: dict | None = None,
        summary: list[dict] | None = None,
        alerting: dict | None = None,
        rollback_drill: dict | None = None,
    ) -> dict:
        return synthetic_probe_audit.build_report(
            summary=summary or self.summary,
            alerting=alerting or self.alerting,
            dependency_contract=self.dependency_contract,
            incident_response=self.incident_response,
            rollback_drill=rollback_drill or self.rollback_drill,
            error_budget=self.error_budget,
            policy=policy or self.policy,
        )

    def test_current_synthetic_probe_audit_passes(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["probe_count"])
        self.assertEqual(4, report["incident_probe_count"])
        self.assertEqual(2, report["preflight_block_count"])
        self.assertEqual(5, report["detected_fixture_count"])

    def test_detects_unhealthy_baseline_probe(self) -> None:
        summary = copy.deepcopy(self.summary)
        for item in summary:
            if item["scenario"] == "baseline":
                item["p95_ms"] = 180

        report = self.build_report(summary=summary)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["signal_contract"])

    def test_detects_missing_dependency_link(self) -> None:
        policy = copy.deepcopy(self.policy)
        for probe in policy["probes"]:
            if probe["name"] == "feature_store_timeout_probe":
                probe["dependency"] = ""

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["dependency_contract_linkage"])

    def test_detects_alert_route_mismatch(self) -> None:
        alerting = copy.deepcopy(self.alerting)
        for alert in alerting["alerts"]:
            if alert["labels"]["scenario"] == "rollout_regression":
                alert["labels"]["severity"] = "ticket"

        report = self.build_report(alerting=alerting)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["alert_response_contract"])

    def test_detects_missing_canary_rollback(self) -> None:
        rollback_drill = copy.deepcopy(self.rollback_drill)
        for drill in rollback_drill["drills"]:
            if drill["scenario"] == "rollout_regression":
                drill["response_type"] = "manual_review"

        report = self.build_report(rollback_drill=rollback_drill)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["rollout_preflight_guard"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = self.build_report()

            synthetic_probe_audit.write_json(report, output_dir)
            synthetic_probe_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "synthetic-probe-audit.json").exists())
            self.assertIn(
                "Synthetic Probe Audit",
                (output_dir / "synthetic-probe-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
