from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import load_shedding_policy_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class LoadSheddingPolicyAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_shedding_policy_audit.load_json(REPO_ROOT / "config/load-shedding-policy.json")
        self.capacity = load_shedding_policy_audit.load_json(REPO_ROOT / "docs/evidence/capacity-plan.json")
        self.tenant_blast_radius = load_shedding_policy_audit.load_json(
            REPO_ROOT / "docs/evidence/tenant-blast-radius.json"
        )
        self.token_cost = load_shedding_policy_audit.load_json(REPO_ROOT / "docs/evidence/token-cost-guard.json")
        self.error_budget = load_shedding_policy_audit.load_json(REPO_ROOT / "docs/evidence/error-budget-ledger.json")
        self.synthetic_probe = load_shedding_policy_audit.load_json(
            REPO_ROOT / "docs/evidence/synthetic-probe-audit.json"
        )
        self.runbooks = load_shedding_policy_audit.load_json(REPO_ROOT / "docs/evidence/incident-runbooks.json")

    def build_report(self, *, policy: dict | None = None) -> dict:
        return load_shedding_policy_audit.build_report(
            capacity=self.capacity,
            tenant_blast_radius=self.tenant_blast_radius,
            token_cost=self.token_cost,
            error_budget=self.error_budget,
            synthetic_probe=self.synthetic_probe,
            runbooks=self.runbooks,
            policy=policy or self.policy,
        )

    def test_current_load_shedding_policy_passes(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["action_count"])
        self.assertEqual(4, report["protective_action_count"])
        self.assertEqual(5, report["detected_fixture_count"])

    def test_detects_scale_only_dependency_timeout(self) -> None:
        policy = copy.deepcopy(self.policy)
        for action in policy["actions"]:
            if action["scenario"] == "dependency_timeout":
                action["traffic_action"] = "scale_only"

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["capacity_guardrail"])

    def test_detects_shed_premium_canary(self) -> None:
        policy = copy.deepcopy(self.policy)
        for action in policy["actions"]:
            if action["scenario"] == "rollout_regression":
                action["shed_tiers"].append("premium")

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["tenant_priority_contract"])

    def test_detects_missing_cost_review(self) -> None:
        policy = copy.deepcopy(self.policy)
        for action in policy["actions"]:
            if action["scenario"] == "rollout_regression":
                action["requires_cost_review"] = False

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["cost_guardrail_linkage"])

    def test_detects_release_action_mismatch(self) -> None:
        policy = copy.deepcopy(self.policy)
        for action in policy["actions"]:
            if action["scenario"] == "dependency_timeout":
                action["expected_release_action"] = "eligible_for_release"

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["release_probe_runbook_linkage"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = self.build_report()

            load_shedding_policy_audit.write_json(report, output_dir)
            load_shedding_policy_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "load-shedding-policy-audit.json").exists())
            self.assertIn(
                "Load Shedding Policy Audit",
                (output_dir / "load-shedding-policy-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
