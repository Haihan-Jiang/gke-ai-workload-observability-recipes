from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import collector_self_observability_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class CollectorSelfObservabilityAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = collector_self_observability_audit.load_json(
            REPO_ROOT / "config/collector-self-observability-policy.json"
        )
        self.docs = collector_self_observability_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = collector_self_observability_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return collector_self_observability_audit.evaluate_documents(docs, self.policy)

    def test_current_collector_self_observability_audit_passes(self) -> None:
        report = collector_self_observability_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["receiver_count"], 3)
        self.assertEqual(1, report["self_metrics_target_count"])
        self.assertEqual(1, report["scrape_job_count"])
        self.assertEqual(10, report["detected_fixture_count"])

    def test_detects_missing_self_metrics_receiver(self) -> None:
        report = self.mutated_report("missing_self_metrics_receiver")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["self_metrics_receiver_defined"])

    def test_detects_self_metrics_removed_from_pipeline(self) -> None:
        report = self.mutated_report("self_metrics_removed_from_pipeline")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["metrics_pipeline_collects_self_metrics"])

    def test_detects_wrong_scrape_job_name(self) -> None:
        report = self.mutated_report("wrong_scrape_job_name")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["self_metrics_scrape_job"])

    def test_detects_missing_scrape_target(self) -> None:
        report = self.mutated_report("missing_scrape_target")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["self_metrics_loopback_target"])

    def test_detects_non_loopback_scrape_target(self) -> None:
        report = self.mutated_report("non_loopback_scrape_target")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["self_metrics_loopback_target"])

    def test_detects_slow_scrape_interval(self) -> None:
        report = self.mutated_report("slow_scrape_interval")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["self_metrics_scrape_interval"])

    def test_detects_trace_sampling_in_metrics_pipeline(self) -> None:
        report = self.mutated_report("tail_sampling_in_metrics_pipeline")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["metrics_pipeline_excludes_trace_sampling"])

    def test_detects_missing_resource_enrichment(self) -> None:
        report = self.mutated_report("missing_resource_enrichment")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["metrics_pipeline_processor_order"])

    def test_detects_disabled_exporter_queue(self) -> None:
        report = self.mutated_report("disabled_exporter_queue")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["self_metrics_exporter_queue"])

    def test_detects_missing_owner_label(self) -> None:
        report = self.mutated_report("missing_collector_config_owner_label")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["collector_config_label_governance"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = collector_self_observability_audit.build_report(self.docs, self.policy)

            collector_self_observability_audit.write_json(report, output_dir)
            collector_self_observability_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "collector-self-observability-audit.json").exists())
            self.assertIn(
                "Collector Self-Observability Audit",
                (output_dir / "collector-self-observability-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
