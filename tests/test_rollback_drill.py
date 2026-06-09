from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import error_budget_ledger, incident_replay, rollback_drill, runbook_generator


REPO_ROOT = Path(__file__).resolve().parents[1]


class RollbackDrillTest(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = [
            incident_replay.summarize_scenario(scenario)
            for scenario in incident_replay.SCENARIOS
        ]
        self.slo_config = error_budget_ledger.load_json(REPO_ROOT / "config/reliability-slo.json")
        self.openslo_policy = error_budget_ledger.load_json(REPO_ROOT / "config/openslo-policy.json")
        self.error_budget_policy = error_budget_ledger.load_json(REPO_ROOT / "config/error-budget-policy.json")
        self.drill_policy = rollback_drill.load_json(REPO_ROOT / "config/rollback-drill-policy.json")
        self.error_budget = error_budget_ledger.build_ledger(
            self.summary,
            self.slo_config,
            self.openslo_policy,
            self.error_budget_policy,
        )
        self.deployment_policy = {
            "decision": "block_production_promotion",
            "blocking_controls": ["burn_rate", "rollout_guard"],
        }
        self.runbooks = {
            "runbooks": runbook_generator.build_runbooks(
                self.summary,
                {"gates": []},
            )
        }

    def build_report(self, policy: dict | None = None, runbooks: dict | None = None) -> dict:
        return rollback_drill.build_drills(
            summary=self.summary,
            runbooks=runbooks or self.runbooks,
            deployment_policy=self.deployment_policy,
            error_budget=self.error_budget,
            drill_policy=policy or self.drill_policy,
        )

    def test_builds_rollback_and_manual_review_drills(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(4, report["drill_count"])
        self.assertEqual(2, report["rollback_required_count"])
        self.assertEqual(2, report["manual_review_count"])
        self.assertTrue(all(item["within_rto"] for item in report["drills"]))

    def test_detects_missing_runbook_linkage(self) -> None:
        runbooks = {"runbooks": self.runbooks["runbooks"][:-1]}

        report = self.build_report(runbooks=runbooks)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["runbook_linkage"])

    def test_detects_rto_violation(self) -> None:
        policy = copy.deepcopy(self.drill_policy)
        policy["rto_minutes"] = 5

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["rto_coverage"])

    def test_writes_evidence(self) -> None:
        report = self.build_report()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            rollback_drill.write_json(report, output_dir)
            rollback_drill.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "rollback-drill.json").exists())
            self.assertIn("Rollback Drill Evidence", (output_dir / "rollback-drill.md").read_text())


if __name__ == "__main__":
    unittest.main()
