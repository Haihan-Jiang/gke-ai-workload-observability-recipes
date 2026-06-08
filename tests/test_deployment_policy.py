from __future__ import annotations

import unittest

from demo import deployment_policy


def clean_inputs() -> dict:
    return {
        "gate": {"status": "pass"},
        "burn_rate": {"windows": [{"window": "5m", "burn_rate": 0.4, "action": "observe"}]},
        "rollout_guard": {"decision": "promote"},
        "trace_quality": {"status": "pass", "payloads": 5, "spans": 136},
        "collector_resilience": {"risk": "ok", "queue_utilization": 0.42},
        "hpa_lag": {"scenarios": [{"scenario": "baseline", "decision": "steady_state"}]},
        "tenant_blast_radius": {"breached_scenarios": []},
        "token_cost_guard": {"scenarios": [{"scenario": "baseline", "decision": "allow"}]},
    }


class DeploymentPolicyTest(unittest.TestCase):
    def test_promotes_when_all_controls_pass(self) -> None:
        report = deployment_policy.evaluate(**clean_inputs())
        self.assertEqual("promote", report["decision"])
        self.assertFalse(report["human_approval_required"])
        self.assertEqual([], report["blocking_controls"])
        self.assertEqual([], report["review_controls"])

    def test_blocks_on_burn_rate_rollout_and_tenant_breach(self) -> None:
        inputs = clean_inputs()
        inputs["burn_rate"] = {
            "windows": [{"window": "5m", "burn_rate": 20.0, "action": "page"}],
        }
        inputs["rollout_guard"] = {
            "decision": "rollback",
            "candidate": "rollout_regression",
            "candidate_version": "v2",
            "violations": ["p95 ratio 5.2 exceeds 1.5"],
        }
        inputs["tenant_blast_radius"] = {"breached_scenarios": ["rollout_regression"]}

        report = deployment_policy.evaluate(**inputs)

        self.assertEqual("block_production_promotion", report["decision"])
        self.assertIn("burn_rate", report["blocking_controls"])
        self.assertIn("rollout_guard", report["blocking_controls"])
        self.assertIn("tenant_blast_radius", report["blocking_controls"])
        self.assertGreaterEqual(len(report["operator_actions"]), 3)

    def test_manual_review_for_hpa_and_cost_risks(self) -> None:
        inputs = clean_inputs()
        inputs["hpa_lag"] = {
            "scenarios": [
                {"scenario": "dependency_timeout", "decision": "fix_dependency_or_rollout"},
            ],
        }
        inputs["token_cost_guard"] = {
            "scenarios": [
                {
                    "scenario": "rollout_regression",
                    "decision": "block_or_review",
                    "violations": ["tokens 900 exceed 700"],
                },
            ],
        }

        report = deployment_policy.evaluate(**inputs)

        self.assertEqual("manual_review_required", report["decision"])
        self.assertEqual([], report["blocking_controls"])
        self.assertIn("hpa_lag", report["review_controls"])
        self.assertIn("token_cost_guard", report["review_controls"])


if __name__ == "__main__":
    unittest.main()
