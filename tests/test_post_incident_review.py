from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import post_incident_review


REPO_ROOT = Path(__file__).resolve().parents[1]


class PostIncidentReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = post_incident_review.load_json(REPO_ROOT / "docs/evidence/sample-summary.json")
        self.incident_correlation = post_incident_review.load_json(REPO_ROOT / "docs/evidence/incident-correlation.json")
        self.rollback_drill = post_incident_review.load_json(REPO_ROOT / "docs/evidence/rollback-drill.json")
        self.error_budget = post_incident_review.load_json(REPO_ROOT / "docs/evidence/error-budget-ledger.json")
        self.deployment_policy = post_incident_review.load_json(REPO_ROOT / "docs/evidence/deployment-policy.json")
        self.policy = post_incident_review.load_json(REPO_ROOT / "config/post-incident-review-policy.json")

    def build_report(self, policy: dict | None = None, rollback_drill: dict | None = None) -> dict:
        return post_incident_review.build_reviews(
            summary=self.summary,
            incident_correlation=self.incident_correlation,
            rollback_drill=rollback_drill or self.rollback_drill,
            error_budget=self.error_budget,
            deployment_policy=self.deployment_policy,
            policy=policy or self.policy,
        )

    def test_builds_review_packet_for_non_healthy_scenarios(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(4, report["review_count"])
        self.assertEqual(8, report["action_item_count"])
        self.assertGreaterEqual(report["preventive_control_count"], 5)

    def test_detects_missing_rollback_review(self) -> None:
        rollback_drill = copy.deepcopy(self.rollback_drill)
        rollback_drill["drills"] = [
            item
            for item in rollback_drill["drills"]
            if item["scenario"] != "rollout_regression"
        ]

        report = self.build_report(rollback_drill=rollback_drill)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["review_coverage"])

    def test_requires_review_for_manual_error_budget_scenario(self) -> None:
        rollback_drill = copy.deepcopy(self.rollback_drill)
        rollback_drill["drills"] = [
            item
            for item in rollback_drill["drills"]
            if item["scenario"] != "cache_miss_storm"
        ]
        policy = copy.deepcopy(self.policy)
        policy["minimum_reviews"] = 3

        report = self.build_report(policy=policy, rollback_drill=rollback_drill)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["review_coverage"])

    def test_detects_action_item_gap(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["corrective_actions"]["collector_queue_pressure"] = []

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["action_item_coverage"])

    def test_writes_evidence(self) -> None:
        report = self.build_report()
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            post_incident_review.write_json(report, output_dir)
            post_incident_review.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "post-incident-review.json").exists())
            self.assertIn("Post-Incident Review Packet", (output_dir / "post-incident-review.md").read_text())


if __name__ == "__main__":
    unittest.main()
