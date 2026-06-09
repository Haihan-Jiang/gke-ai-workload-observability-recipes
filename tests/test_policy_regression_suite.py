from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from demo import policy_regression_suite


REPO_ROOT = Path(__file__).resolve().parents[1]


class PolicyRegressionSuiteTest(unittest.TestCase):
    def test_configured_fixtures_pass(self) -> None:
        config = json.loads((REPO_ROOT / "config/deployment-policy-fixtures.json").read_text())
        report = policy_regression_suite.run_suite(config["fixtures"])

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["fixture_count"], 8)
        self.assertEqual(report["fixture_count"], report["passed_count"])
        self.assertIn("burn_rate", report["controls_under_test"])
        self.assertIn("collector_resilience", report["controls_under_test"])
        self.assertIn("reliability_gate", report["controls_under_test"])

    def test_suite_detects_bad_expected_decision(self) -> None:
        fixture = {
            "name": "bad_expectation",
            "expected_decision": "promote",
            "expected_blocking_controls": [],
            "expected_review_controls": [],
            "overrides": {
                "burn_rate": {
                    "windows": [
                        {
                            "window": "5m",
                            "burn_rate": 20.5,
                            "action": "page",
                        }
                    ]
                }
            },
        }

        report = policy_regression_suite.run_suite([fixture])

        self.assertEqual("fail", report["status"])
        self.assertEqual(1, report["failed_count"])
        self.assertEqual("block_production_promotion", report["fixtures"][0]["actual_decision"])

    def test_writes_markdown_and_json(self) -> None:
        config = json.loads((REPO_ROOT / "config/deployment-policy-fixtures.json").read_text())
        report = policy_regression_suite.run_suite(config["fixtures"])
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            policy_regression_suite.write_json(report, output_dir)
            policy_regression_suite.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "policy-regression-suite.json").exists())
            self.assertIn(
                "Policy Regression Suite",
                (output_dir / "policy-regression-suite.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
