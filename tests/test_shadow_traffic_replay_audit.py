from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import shadow_traffic_replay_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ShadowTrafficReplayAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = shadow_traffic_replay_audit.load_json(REPO_ROOT / "config/shadow-traffic-policy.json")
        self.summary = shadow_traffic_replay_audit.load_json(REPO_ROOT / "docs/evidence/sample-summary.json")
        self.telemetry_redaction = shadow_traffic_replay_audit.load_json(
            REPO_ROOT / "docs/evidence/telemetry-redaction-audit.json"
        )
        self.rollout_guard = shadow_traffic_replay_audit.load_json(REPO_ROOT / "docs/evidence/rollout-guard.json")
        self.token_cost = shadow_traffic_replay_audit.load_json(REPO_ROOT / "docs/evidence/token-cost-guard.json")
        self.synthetic_probe = shadow_traffic_replay_audit.load_json(
            REPO_ROOT / "docs/evidence/synthetic-probe-audit.json"
        )
        self.model_release_safety = shadow_traffic_replay_audit.load_json(
            REPO_ROOT / "docs/evidence/model-release-safety-audit.json"
        )

    def build_report(
        self,
        *,
        policy: dict | None = None,
        telemetry_redaction: dict | None = None,
    ) -> dict:
        return shadow_traffic_replay_audit.build_report(
            policy=policy or self.policy,
            summary=self.summary,
            telemetry_redaction=telemetry_redaction or self.telemetry_redaction,
            rollout_guard=self.rollout_guard,
            token_cost=self.token_cost,
            synthetic_probe=self.synthetic_probe,
            model_release_safety=self.model_release_safety,
        )

    def test_current_shadow_traffic_replay_audit_passes(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["replay_count"])
        self.assertEqual(1, report["candidate_replay_count"])
        self.assertEqual(1, report["blocked_shadow_count"])
        self.assertEqual(7, report["detected_fixture_count"])

    def test_detects_candidate_shadow_serving_users(self) -> None:
        policy = copy.deepcopy(self.policy)
        for replay in policy["replays"]:
            if replay["name"] == "candidate_v2_shadow":
                replay["served_to_users"] = True

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["isolation_contract"])

    def test_detects_shadow_percent_too_large(self) -> None:
        policy = copy.deepcopy(self.policy)
        for replay in policy["replays"]:
            if replay["name"] == "candidate_v2_shadow":
                replay["shadow_percent"] = 50

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["isolation_contract"])

    def test_detects_prompt_storage(self) -> None:
        policy = copy.deepcopy(self.policy)
        for replay in policy["replays"]:
            if replay["name"] == "candidate_v2_shadow":
                replay["store_prompt"] = True

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["privacy_contract"])

    def test_detects_redaction_failure(self) -> None:
        telemetry_redaction = copy.deepcopy(self.telemetry_redaction)
        telemetry_redaction["redaction_violation_count"] = 1

        report = self.build_report(telemetry_redaction=telemetry_redaction)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["privacy_contract"])

    def test_detects_wrong_rollout_decision(self) -> None:
        policy = copy.deepcopy(self.policy)
        for replay in policy["replays"]:
            if replay["name"] == "candidate_v2_shadow":
                replay["expected_rollout_decision"] = "promote"

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["candidate_comparison_gate"])

    def test_detects_wrong_probe_linkage(self) -> None:
        policy = copy.deepcopy(self.policy)
        for replay in policy["replays"]:
            if replay["name"] == "candidate_v2_shadow":
                replay["expected_probe"] = "baseline_readiness_probe"

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["rollback_probe_linkage"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = self.build_report()

            shadow_traffic_replay_audit.write_json(report, output_dir)
            shadow_traffic_replay_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "shadow-traffic-replay-audit.json").exists())
            self.assertIn(
                "Shadow Traffic Replay Audit",
                (output_dir / "shadow-traffic-replay-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
