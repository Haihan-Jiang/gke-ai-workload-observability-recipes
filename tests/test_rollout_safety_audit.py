from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import rollout_safety_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class RolloutSafetyAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = rollout_safety_audit.load_json(REPO_ROOT / "config/rollout-safety-policy.json")
        self.docs = rollout_safety_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = rollout_safety_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return rollout_safety_audit.evaluate_documents(docs, self.policy)

    def test_current_rollout_safety_audit_passes(self) -> None:
        report = rollout_safety_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["workload_count"])
        self.assertEqual(1, report["rolling_update_count"])
        self.assertEqual(1, report["recreate_count"])
        self.assertEqual(2, report["timing_guard_count"])
        self.assertEqual(2, report["termination_window_count"])
        self.assertEqual(12, report["detected_fixture_count"])

    def test_detects_disruptive_sample_strategy(self) -> None:
        report = self.mutated_report("sample_strategy_recreate")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["rolling_update_strategy"])

    def test_detects_unavailable_sample_rollout(self) -> None:
        report = self.mutated_report("sample_allows_unavailable_pod")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["rolling_update_availability"])

    def test_detects_missing_surge_capacity(self) -> None:
        report = self.mutated_report("sample_missing_surge_capacity")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["rolling_update_availability"])

    def test_detects_missing_rollout_timing(self) -> None:
        report = self.mutated_report("sample_min_ready_zero")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["rollout_timing"])

    def test_detects_short_progress_deadline(self) -> None:
        report = self.mutated_report("sample_progress_deadline_short")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["rollout_timing"])

    def test_detects_missing_termination_grace(self) -> None:
        report = self.mutated_report("sample_missing_termination_grace")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["termination_drain_window"])

    def test_detects_collector_rolling_update_with_pvc(self) -> None:
        report = self.mutated_report("collector_rolling_update_with_pvc")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["singleton_recreate_strategy"])

    def test_detects_missing_collector_queue_pvc(self) -> None:
        report = self.mutated_report("collector_missing_queue_pvc")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["singleton_queue_alignment"])

    def test_detects_short_collector_termination_grace(self) -> None:
        report = self.mutated_report("collector_short_termination_grace")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["termination_drain_window"])

    def test_detects_deployment_label_drift(self) -> None:
        report = self.mutated_report("missing_deployment_owner_label")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["rollout_label_governance"])

    def test_detects_pdb_blocking_rolling_rollout(self) -> None:
        report = self.mutated_report("sample_pdb_min_equals_replicas")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["pdb_rollout_alignment"])

    def test_detects_singleton_pdb_allowing_eviction(self) -> None:
        report = self.mutated_report("collector_pdb_allows_eviction")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["pdb_rollout_alignment"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = rollout_safety_audit.build_report(self.docs, self.policy)

            rollout_safety_audit.write_json(report, output_dir)
            rollout_safety_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "rollout-safety-audit.json").exists())
            self.assertIn(
                "Rollout Safety Audit",
                (output_dir / "rollout-safety-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
