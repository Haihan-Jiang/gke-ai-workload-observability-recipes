from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import scheduling_placement_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class SchedulingPlacementAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = scheduling_placement_audit.load_json(REPO_ROOT / "config/scheduling-placement-policy.json")
        self.docs = scheduling_placement_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = scheduling_placement_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return scheduling_placement_audit.evaluate_documents(docs, self.policy)

    def test_current_scheduling_placement_audit_passes(self) -> None:
        report = scheduling_placement_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["workload_count"])
        self.assertEqual(2, report["priority_class_count"])
        self.assertEqual(4, report["preferred_affinity_count"])
        self.assertEqual(2, report["toleration_count"])
        self.assertEqual(10, report["detected_fixture_count"])

    def test_detects_missing_priority_class(self) -> None:
        report = self.mutated_report("missing_inference_priority_class")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["priority_class_definitions"])

    def test_detects_low_priority_value(self) -> None:
        report = self.mutated_report("low_telemetry_priority_value")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["priority_class_definitions"])

    def test_detects_preempting_priority(self) -> None:
        report = self.mutated_report("preempting_telemetry_priority")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["priority_class_definitions"])

    def test_detects_missing_priority_binding(self) -> None:
        report = self.mutated_report("sample_missing_priority_binding")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["workload_priority_binding"])

    def test_detects_wrong_priority_binding(self) -> None:
        report = self.mutated_report("collector_wrong_priority_binding")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["workload_priority_binding"])

    def test_detects_missing_nodepool_preference(self) -> None:
        report = self.mutated_report("sample_missing_nodepool_preference")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["preferred_node_affinity"])

    def test_detects_hard_node_selector(self) -> None:
        report = self.mutated_report("collector_hard_node_selector")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["portable_scheduling_preferences"])

    def test_detects_missing_toleration(self) -> None:
        report = self.mutated_report("sample_missing_toleration")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["bounded_tolerations"])

    def test_detects_wildcard_toleration(self) -> None:
        report = self.mutated_report("collector_wildcard_toleration")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["bounded_tolerations"])

    def test_detects_missing_owner_label(self) -> None:
        report = self.mutated_report("missing_priority_class_owner_label")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["scheduling_label_governance"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = scheduling_placement_audit.build_report(self.docs, self.policy)

            scheduling_placement_audit.write_json(report, output_dir)
            scheduling_placement_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "scheduling-placement-audit.json").exists())
            self.assertIn(
                "Scheduling Placement Audit",
                (output_dir / "scheduling-placement-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
