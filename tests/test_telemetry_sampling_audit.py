from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import telemetry_sampling_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class TelemetrySamplingAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = telemetry_sampling_audit.load_json(REPO_ROOT / "config/telemetry-sampling-policy.json")
        self.docs = telemetry_sampling_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = telemetry_sampling_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return telemetry_sampling_audit.evaluate_documents(docs, self.policy)

    def test_current_telemetry_sampling_audit_passes(self) -> None:
        report = telemetry_sampling_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["policy_count"])
        self.assertEqual(4, report["critical_policy_count"])
        self.assertEqual(2, report["baseline_sampling_percentage"])
        self.assertEqual(10, report["detected_fixture_count"])

    def test_detects_missing_tail_sampling_processor(self) -> None:
        report = self.mutated_report("missing_tail_sampling_processor")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["sampling_processor_defined"])

    def test_detects_tail_sampling_removed_from_traces(self) -> None:
        report = self.mutated_report("tail_sampling_removed_from_traces")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["trace_pipeline_sampling_order"])

    def test_detects_tail_sampling_after_batch(self) -> None:
        report = self.mutated_report("tail_sampling_after_batch")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["trace_pipeline_sampling_order"])

    def test_detects_metrics_pipeline_sampling(self) -> None:
        report = self.mutated_report("metrics_pipeline_tail_sampling")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["metrics_pipeline_excludes_tail_sampling"])

    def test_detects_unbounded_decision_wait(self) -> None:
        report = self.mutated_report("unbounded_decision_wait")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["sampling_decision_window"])

    def test_detects_undersized_trace_buffer(self) -> None:
        report = self.mutated_report("undersized_trace_buffer")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["sampling_buffer"])

    def test_detects_missing_error_policy(self) -> None:
        report = self.mutated_report("missing_error_policy")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["critical_trace_policy_coverage"])

    def test_detects_wrong_dependency_attribute(self) -> None:
        report = self.mutated_report("wrong_dependency_attribute")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["critical_trace_policy_coverage"])

    def test_detects_excessive_baseline_sampling(self) -> None:
        report = self.mutated_report("excessive_baseline_sampling")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["baseline_sampling_budget"])

    def test_detects_missing_owner_label(self) -> None:
        report = self.mutated_report("missing_collector_config_owner_label")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["collector_config_label_governance"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = telemetry_sampling_audit.build_report(self.docs, self.policy)

            telemetry_sampling_audit.write_json(report, output_dir)
            telemetry_sampling_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "telemetry-sampling-audit.json").exists())
            self.assertIn(
                "Telemetry Sampling Audit",
                (output_dir / "telemetry-sampling-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
