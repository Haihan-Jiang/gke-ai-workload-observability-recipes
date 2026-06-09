from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import dependency_contract_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class DependencyContractAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = dependency_contract_audit.load_json(REPO_ROOT / "config/dependency-contract-policy.json")
        self.summary = dependency_contract_audit.load_json(REPO_ROOT / "docs/evidence/sample-summary.json")
        self.critical_path = dependency_contract_audit.load_json(REPO_ROOT / "docs/evidence/critical-path-attribution.json")
        self.runbooks = dependency_contract_audit.load_json(REPO_ROOT / "docs/evidence/incident-runbooks.json")
        self.alerting = dependency_contract_audit.load_json(REPO_ROOT / "docs/evidence/alerting-rules.json")
        self.error_budget = dependency_contract_audit.load_json(REPO_ROOT / "docs/evidence/error-budget-ledger.json")
        self.rollback_drill = dependency_contract_audit.load_json(REPO_ROOT / "docs/evidence/rollback-drill.json")

    def build_report(
        self,
        *,
        policy: dict | None = None,
        critical_path: dict | None = None,
        alerting: dict | None = None,
        error_budget: dict | None = None,
    ) -> dict:
        return dependency_contract_audit.build_report(
            summary=self.summary,
            critical_path=critical_path or self.critical_path,
            runbooks=self.runbooks,
            alerting=alerting or self.alerting,
            error_budget=error_budget or self.error_budget,
            rollback_drill=self.rollback_drill,
            policy=policy or self.policy,
        )

    def test_current_dependency_contract_passes(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(4, report["dependency_count"])
        self.assertEqual(4, report["incident_contract_count"])
        self.assertEqual(3, report["dominant_dependency_count"])
        self.assertEqual(5, report["detected_fixture_count"])

    def test_detects_owner_mismatch(self) -> None:
        policy = copy.deepcopy(self.policy)
        for dependency in policy["dependencies"]:
            if dependency["name"] == "feature_store":
                dependency["owner"] = "wrong owner"

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["owner_runbook_contract"])

    def test_detects_alert_severity_mismatch(self) -> None:
        alerting = copy.deepcopy(self.alerting)
        for alert in alerting["alerts"]:
            if alert["labels"]["scenario"] == "rollout_regression":
                alert["labels"]["severity"] = "ticket"

        report = self.build_report(alerting=alerting)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["alert_contract"])

    def test_detects_missing_failure_signal(self) -> None:
        critical_path = copy.deepcopy(self.critical_path)
        for item in critical_path["scenarios"]:
            if item["scenario"] == "dependency_timeout":
                item["average_child_span_ms"]["feature-store lookup"] = 50

        report = self.build_report(critical_path=critical_path)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["failure_mode_contract"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = self.build_report()

            dependency_contract_audit.write_json(report, output_dir)
            dependency_contract_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "dependency-contract-audit.json").exists())
            self.assertIn(
                "Dependency Contract Audit",
                (output_dir / "dependency-contract-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
