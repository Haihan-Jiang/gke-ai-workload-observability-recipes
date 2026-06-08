from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import release_readiness


def ready_inputs(evidence_dir: Path) -> dict:
    scenarios = [f"scenario_{index}" for index in range(5)]
    for name in release_readiness.REQUIRED_EVIDENCE:
        (evidence_dir / name).write_text("evidence\n", encoding="utf-8")
    return {
        "gate": {"status": "pass"},
        "capacity": {
            "scenarios": [
                {
                    "scenario": scenario,
                    "warnings": [],
                }
                for scenario in scenarios
            ]
        },
        "runbooks": {
            "runbooks": [
                {
                    "scenario": scenario,
                }
                for scenario in scenarios
            ]
        },
        "advanced": {"problems": [{"id": f"C0{index}"} for index in range(5)]},
        "detailed": {"problems": [{"id": f"C1{index}"} for index in range(5)]},
        "policy": {
            "status": "generated",
            "decision": "promote",
            "control_count": 8,
        },
        "policy_regression": {
            "status": "pass",
            "fixture_count": 8,
            "failed_count": 0,
            "controls_under_test": sorted(release_readiness.REQUIRED_POLICY_REGRESSION_CONTROLS),
        },
        "k8s_hardening": {
            "status": "pass",
            "check_count": 11,
            "failed_count": 0,
        },
        "alerting": {
            "status": "pass",
            "rule_count": 5,
            "failed_count": 0,
        },
        "dashboard": {
            "status": "pass",
            "panel_count": 6,
            "failed_count": 0,
        },
        "openslo": {
            "status": "pass",
            "objective_target": 99.5,
            "scenario_count": 5,
            "failed_count": 0,
        },
        "telemetry_redaction": {
            "status": "pass",
            "payload_count": 5,
            "redaction_violation_count": 0,
            "failed_count": 0,
        },
        "telemetry_cost": {
            "status": "pass",
            "scenario_count": 5,
            "daily_ingest_gib": 11.0,
            "failed_count": 0,
        },
        "error_budget": {
            "status": "pass",
            "scenario_count": 5,
            "non_green_count": 4,
            "failed_count": 0,
            "decision_counts": {
                "within_budget": 1,
                "manual_review_required": 2,
                "budget_exhausted": 2,
            },
        },
        "rollback_drill": {
            "status": "pass",
            "drill_count": 4,
            "rollback_required_count": 2,
            "failed_count": 0,
        },
        "post_incident_review": {
            "status": "pass",
            "review_count": 4,
            "action_item_count": 8,
            "failed_count": 0,
        },
        "evidence_provenance": {
            "status": "pass",
            "artifact_count": 50,
            "source_input_count": 27,
            "failed_count": 0,
        },
        "evidence_dir": evidence_dir,
    }


class ReleaseReadinessTest(unittest.TestCase):
    def test_requires_policy_regression_control_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}
            self.assertEqual("pass", report["status"])
            self.assertTrue(checks["policy_regression_suite"])

            inputs["policy_regression"]["controls_under_test"] = ["burn_rate"]
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}
            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["policy_regression_suite"])

    def test_requires_k8s_manifest_hardening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["k8s_hardening"]["failed_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["k8s_manifest_hardening"])

    def test_requires_slo_alerting_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["alerting"]["rule_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["slo_alerting_rules"])

    def test_requires_grafana_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["dashboard"]["panel_count"] = 3
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["grafana_dashboard"])

    def test_requires_openslo_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["openslo"]["scenario_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["openslo_contract"])

    def test_requires_error_budget_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["error_budget"]["non_green_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["error_budget_ledger"])

    def test_requires_telemetry_redaction_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["telemetry_redaction"]["redaction_violation_count"] = 1
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["telemetry_redaction_audit"])

    def test_requires_telemetry_cost_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["telemetry_cost"]["daily_ingest_gib"] = 99.0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["telemetry_cost_budget"])

    def test_requires_rollback_drill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["rollback_drill"]["rollback_required_count"] = 0
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["rollback_drill"])

    def test_requires_post_incident_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["post_incident_review"]["action_item_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["post_incident_review"])

    def test_requires_evidence_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inputs = ready_inputs(Path(tmp))

            inputs["evidence_provenance"]["artifact_count"] = 2
            report = release_readiness.evaluate(**inputs)
            checks = {item["name"]: item["ok"] for item in report["checks"]}

            self.assertEqual("fail", report["status"])
            self.assertFalse(checks["evidence_provenance"])


if __name__ == "__main__":
    unittest.main()
