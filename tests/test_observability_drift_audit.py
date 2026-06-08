from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import observability_drift_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ObservabilityDriftAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = observability_drift_audit.load_json(REPO_ROOT / "config/observability-drift-policy.json")
        self.alerting = observability_drift_audit.load_json(REPO_ROOT / "docs/evidence/alerting-rules.json")
        self.dashboard = observability_drift_audit.load_json(REPO_ROOT / "docs/evidence/grafana-dashboard.json")
        self.openslo = observability_drift_audit.load_json(REPO_ROOT / "docs/evidence/openslo-contract.json")
        self.runbooks = observability_drift_audit.load_json(REPO_ROOT / "docs/evidence/incident-runbooks.json")

    def build_report(
        self,
        *,
        alerting: dict | None = None,
        dashboard: dict | None = None,
        openslo: dict | None = None,
        runbooks: dict | None = None,
    ) -> dict:
        return observability_drift_audit.build_report(
            alerting=alerting or self.alerting,
            dashboard=dashboard or self.dashboard,
            openslo=openslo or self.openslo,
            runbooks=runbooks or self.runbooks,
            policy=self.policy,
        )

    def test_current_observability_contract_is_consistent(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["failed_count"])
        self.assertEqual(5, report["required_scenario_count"])
        self.assertEqual(5, report["detected_fixture_count"])

    def test_detects_missing_alert_scenario(self) -> None:
        alerting = copy.deepcopy(self.alerting)
        alerting["alerts"] = [
            item
            for item in alerting["alerts"]
            if item["labels"]["scenario"] != "dependency_timeout"
        ]
        alerting["rule_count"] = len(alerting["alerts"])

        report = self.build_report(alerting=alerting)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["scenario_contract"])

    def test_detects_alert_severity_drift(self) -> None:
        alerting = copy.deepcopy(self.alerting)
        for item in alerting["alerts"]:
            if item["labels"]["scenario"] == "cache_miss_storm":
                item["labels"]["severity"] = "page"

        report = self.build_report(alerting=alerting)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["alert_metadata_contract"])

    def test_detects_missing_runbook_scenario(self) -> None:
        runbooks = copy.deepcopy(self.runbooks)
        runbooks["runbooks"] = [
            item
            for item in runbooks["runbooks"]
            if item["scenario"] != "rollout_regression"
        ]

        report = self.build_report(runbooks=runbooks)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["scenario_contract"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = self.build_report()

            observability_drift_audit.write_json(report, output_dir)
            observability_drift_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "observability-drift-audit.json").exists())
            self.assertIn(
                "Observability Drift Audit",
                (output_dir / "observability-drift-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
