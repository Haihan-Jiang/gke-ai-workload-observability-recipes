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


if __name__ == "__main__":
    unittest.main()
