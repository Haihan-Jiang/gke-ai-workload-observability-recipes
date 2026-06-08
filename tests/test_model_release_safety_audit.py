from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import model_release_safety_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ModelReleaseSafetyAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = model_release_safety_audit.load_json(REPO_ROOT / "config/model-release-policy.json")
        self.rollout_guard = model_release_safety_audit.load_json(REPO_ROOT / "docs/evidence/rollout-guard.json")
        self.trace_quality = model_release_safety_audit.load_json(REPO_ROOT / "docs/evidence/trace-quality-audit.json")
        self.token_cost = model_release_safety_audit.load_json(REPO_ROOT / "docs/evidence/token-cost-guard.json")
        self.error_budget = model_release_safety_audit.load_json(REPO_ROOT / "docs/evidence/error-budget-ledger.json")
        self.rollback_drill = model_release_safety_audit.load_json(REPO_ROOT / "docs/evidence/rollback-drill.json")
        self.synthetic_probe = model_release_safety_audit.load_json(
            REPO_ROOT / "docs/evidence/synthetic-probe-audit.json"
        )

    def build_report(
        self,
        *,
        policy: dict | None = None,
        rollout_guard: dict | None = None,
        trace_quality: dict | None = None,
    ) -> dict:
        return model_release_safety_audit.build_report(
            policy=policy or self.policy,
            rollout_guard=rollout_guard or self.rollout_guard,
            trace_quality=trace_quality or self.trace_quality,
            token_cost=self.token_cost,
            error_budget=self.error_budget,
            rollback_drill=self.rollback_drill,
            synthetic_probe=self.synthetic_probe,
        )

    def test_current_model_release_safety_audit_passes(self) -> None:
        report = self.build_report()

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["release_count"])
        self.assertEqual(1, report["candidate_count"])
        self.assertEqual(1, report["blocked_candidate_count"])
        self.assertEqual(7, report["detected_fixture_count"])

    def test_detects_unpinned_candidate_artifact(self) -> None:
        policy = copy.deepcopy(self.policy)
        for release in policy["releases"]:
            if release["name"] == "recommender-v2-candidate":
                release["artifact_uri"] = "gs://model-registry/recommender-v2:latest"

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["artifact_inventory"])

    def test_detects_stable_release_eval_failure(self) -> None:
        policy = copy.deepcopy(self.policy)
        for release in policy["releases"]:
            if release["name"] == "recommender-small-stable":
                release["quality_score"] = 0.7

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["eval_schema_gate"])

    def test_detects_candidate_canary_too_large(self) -> None:
        policy = copy.deepcopy(self.policy)
        for release in policy["releases"]:
            if release["name"] == "recommender-v2-candidate":
                release["canary_percent"] = 50

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["canary_rollout_gate"])

    def test_detects_missing_rollback_target(self) -> None:
        policy = copy.deepcopy(self.policy)
        for release in policy["releases"]:
            if release["name"] == "recommender-v2-candidate":
                release["rollback_target"] = None

        report = self.build_report(policy=policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["rollback_contract"])

    def test_detects_missing_service_version_trace_label(self) -> None:
        trace_quality = copy.deepcopy(self.trace_quality)
        trace_quality["cardinality"]["service.version"]["values"] = ["v1"]

        report = self.build_report(trace_quality=trace_quality)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["observability_contract"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = self.build_report()

            model_release_safety_audit.write_json(report, output_dir)
            model_release_safety_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "model-release-safety-audit.json").exists())
            self.assertIn(
                "Model Release Safety Audit",
                (output_dir / "model-release-safety-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
