from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import release_waiver_governance


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReleaseWaiverGovernanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = release_waiver_governance.load_json(REPO_ROOT / "config/release-waiver-policy.json")
        self.waivers = release_waiver_governance.load_json(REPO_ROOT / "config/release-waivers.json")
        self.deployment_policy = release_waiver_governance.load_json(REPO_ROOT / "docs/evidence/deployment-policy.json")
        self.error_budget = release_waiver_governance.load_json(REPO_ROOT / "docs/evidence/error-budget-ledger.json")
        self.rollback_drill = release_waiver_governance.load_json(REPO_ROOT / "docs/evidence/rollback-drill.json")
        self.post_incident_review = release_waiver_governance.load_json(REPO_ROOT / "docs/evidence/post-incident-review.json")

    def build_report(self, waivers: dict | None = None) -> dict:
        return release_waiver_governance.build_report(
            policy=self.policy,
            waivers=waivers or self.waivers,
            deployment_policy=self.deployment_policy,
            error_budget=self.error_budget,
            rollback_drill=self.rollback_drill,
            post_incident_review=self.post_incident_review,
        )

    def test_current_waiver_register_passes(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["failed_count"])
        self.assertEqual(2, report["conditional_approval_count"])
        self.assertEqual(2, report["denied_override_count"])
        self.assertEqual(0, report["unsafe_approved_count"])

    def test_manual_review_waiver_can_be_conditionally_approved(self) -> None:
        ledger = release_waiver_governance.by_scenario(self.error_budget["ledger"])
        rollback = release_waiver_governance.by_scenario(self.rollback_drill["drills"])
        reviews = release_waiver_governance.by_scenario(self.post_incident_review["reviews"])

        decision = release_waiver_governance.evaluate_waiver(
            self.waivers["waivers"][0],
            policy=self.policy,
            ledger=ledger,
            rollback_drills=rollback,
            post_incident_reviews=reviews,
        )

        self.assertEqual("conditionally_approved", decision["decision"])
        self.assertEqual([], decision["failed_checks"])

    def test_budget_exhausted_override_is_denied(self) -> None:
        ledger = release_waiver_governance.by_scenario(self.error_budget["ledger"])
        rollback = release_waiver_governance.by_scenario(self.rollback_drill["drills"])
        reviews = release_waiver_governance.by_scenario(self.post_incident_review["reviews"])

        decision = release_waiver_governance.evaluate_waiver(
            self.waivers["waivers"][2],
            policy=self.policy,
            ledger=ledger,
            rollback_drills=rollback,
            post_incident_reviews=reviews,
        )

        self.assertEqual("denied_override", decision["decision"])
        self.assertEqual([], decision["failed_checks"])

    def test_missing_approver_invalidates_register(self) -> None:
        waivers = copy.deepcopy(self.waivers)
        waivers["waivers"][0]["approvers"] = ["sre_lead"]

        report = self.build_report(waivers)
        decisions = {item["id"]: item for item in report["decisions"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("invalid_request", decisions["WVR-CACHE-001"]["decision"])
        self.assertIn("owner_approvals", decisions["WVR-CACHE-001"]["failed_checks"])

    def test_expired_waiver_invalidates_register(self) -> None:
        waivers = copy.deepcopy(self.waivers)
        waivers["waivers"][1]["expires_at"] = "2026-06-01T11:00:00Z"

        report = self.build_report(waivers)
        decisions = {item["id"]: item for item in report["decisions"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("invalid_request", decisions["WVR-COLLECTOR-001"]["decision"])
        self.assertIn("validity_window", decisions["WVR-COLLECTOR-001"]["failed_checks"])

    def test_writes_json_and_markdown(self) -> None:
        report = self.build_report()
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            release_waiver_governance.write_json(report, output_dir)
            release_waiver_governance.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "release-waiver-governance.json").exists())
            self.assertIn(
                "Release Waiver Governance",
                (output_dir / "release-waiver-governance.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
