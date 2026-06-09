from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import accelerator_quota_fairness_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class AcceleratorQuotaFairnessAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = accelerator_quota_fairness_audit.load_json(REPO_ROOT / "config/accelerator-quota-policy.json")
        self.capacity = accelerator_quota_fairness_audit.load_json(REPO_ROOT / "docs/evidence/capacity-plan.json")
        self.tenant_blast_radius = accelerator_quota_fairness_audit.load_json(
            REPO_ROOT / "docs/evidence/tenant-blast-radius.json"
        )
        self.token_cost = accelerator_quota_fairness_audit.load_json(REPO_ROOT / "docs/evidence/token-cost-guard.json")
        self.load_shedding = accelerator_quota_fairness_audit.load_json(
            REPO_ROOT / "docs/evidence/load-shedding-policy-audit.json"
        )
        self.shadow_traffic = accelerator_quota_fairness_audit.load_json(
            REPO_ROOT / "docs/evidence/shadow-traffic-replay-audit.json"
        )
        self.model_release_safety = accelerator_quota_fairness_audit.load_json(
            REPO_ROOT / "docs/evidence/model-release-safety-audit.json"
        )

    def build_report(
        self,
        *,
        policy: dict | None = None,
        shadow_traffic: dict | None = None,
    ) -> dict:
        return accelerator_quota_fairness_audit.build_report(
            policy=policy or self.policy,
            capacity=self.capacity,
            tenant_blast_radius=self.tenant_blast_radius,
            token_cost=self.token_cost,
            load_shedding=self.load_shedding,
            shadow_traffic=shadow_traffic or self.shadow_traffic,
            model_release_safety=self.model_release_safety,
        )

    def test_current_accelerator_quota_fairness_audit_passes(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["quota_count"])
        self.assertEqual(1, report["candidate_quota_count"])
        self.assertGreaterEqual(report["protected_tier_count"], 2)
        self.assertEqual(7, report["detected_fixture_count"])

    def test_detects_gpu_quota_without_cost_review(self) -> None:
        policy = copy.deepcopy(self.policy)
        for quota in policy["quotas"]:
            if quota["name"] == "candidate_premium_quota":
                quota["expected_cost_decision"] = "allow"

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["accelerator_budget_guard"])

    def test_detects_premium_not_protected(self) -> None:
        policy = copy.deepcopy(self.policy)
        for quota in policy["quotas"]:
            if quota["name"] == "candidate_premium_quota":
                quota["protect_tiers"] = ["standard"]

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["tenant_fairness_contract"])

    def test_detects_best_effort_not_shed(self) -> None:
        policy = copy.deepcopy(self.policy)
        for quota in policy["quotas"]:
            if quota["name"] == "dependency_standard_quota":
                quota["shed_tiers"] = []

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["tenant_fairness_contract"])

    def test_detects_wrong_traffic_action(self) -> None:
        policy = copy.deepcopy(self.policy)
        for quota in policy["quotas"]:
            if quota["name"] == "dependency_standard_quota":
                quota["expected_traffic_action"] = "no_action"

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["load_shedding_linkage"])

    def test_detects_missing_shadow_candidate_block(self) -> None:
        shadow_traffic = copy.deepcopy(self.shadow_traffic)
        shadow_traffic["blocked_shadow_count"] = 0

        report = self.build_report(shadow_traffic=shadow_traffic)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["shadow_candidate_quota"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = self.build_report()

            accelerator_quota_fairness_audit.write_json(report, output_dir)
            accelerator_quota_fairness_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "accelerator-quota-fairness-audit.json").exists())
            self.assertIn(
                "Accelerator Quota Fairness Audit",
                (output_dir / "accelerator-quota-fairness-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
