from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import error_budget_ledger, incident_replay


REPO_ROOT = Path(__file__).resolve().parents[1]


class ErrorBudgetLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = [
            incident_replay.summarize_scenario(scenario)
            for scenario in incident_replay.SCENARIOS
        ]
        self.slo_config = error_budget_ledger.load_json(REPO_ROOT / "config/reliability-slo.json")
        self.openslo_policy = error_budget_ledger.load_json(REPO_ROOT / "config/openslo-policy.json")
        self.policy = error_budget_ledger.load_json(REPO_ROOT / "config/error-budget-policy.json")

    def test_ledger_maps_replay_scenarios_to_budget_actions(self) -> None:
        report = error_budget_ledger.build_ledger(
            self.summary,
            self.slo_config,
            self.openslo_policy,
            self.policy,
        )
        by_scenario = {item["scenario"]: item for item in report["ledger"]}

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["scenario_count"])
        self.assertEqual(4, report["non_green_count"])
        self.assertEqual("within_budget", by_scenario["baseline"]["decision"])
        self.assertEqual("budget_exhausted", by_scenario["dependency_timeout"]["decision"])
        self.assertEqual("block_release_or_rollback", by_scenario["rollout_regression"]["release_action"])

    def test_audit_detects_baseline_budget_regression(self) -> None:
        summary = copy.deepcopy(self.summary)
        summary[0]["errors"] = 1
        summary[0]["error_rate"] = 0.12

        report = error_budget_ledger.build_ledger(
            summary,
            self.slo_config,
            self.openslo_policy,
            self.policy,
        )
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["baseline_within_budget"])

    def test_audit_detects_missing_required_scenario(self) -> None:
        report = error_budget_ledger.build_ledger(
            self.summary[:-1],
            self.slo_config,
            self.openslo_policy,
            self.policy,
        )
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["scenario_coverage"])

    def test_writes_evidence(self) -> None:
        report = error_budget_ledger.build_ledger(
            self.summary,
            self.slo_config,
            self.openslo_policy,
            self.policy,
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            error_budget_ledger.write_json(report, output_dir)
            error_budget_ledger.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "error-budget-ledger.json").exists())
            self.assertIn("Error Budget Ledger", (output_dir / "error-budget-ledger.md").read_text())


if __name__ == "__main__":
    unittest.main()
