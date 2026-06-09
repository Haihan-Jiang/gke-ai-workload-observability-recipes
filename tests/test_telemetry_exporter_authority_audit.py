from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import telemetry_exporter_authority_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class TelemetryExporterAuthorityAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = telemetry_exporter_authority_audit.load_json(
            REPO_ROOT / "config/telemetry-exporter-policy.json"
        )
        self.docs = telemetry_exporter_authority_audit.load_manifest_set(
            REPO_ROOT,
            list(self.policy["target_manifests"]),
        )
        self.documentation = telemetry_exporter_authority_audit.load_documentation(
            REPO_ROOT,
            list(self.policy["documentation_files"]),
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def report_for_fixture(self, name: str) -> dict:
        docs, documentation = telemetry_exporter_authority_audit.apply_fixture(
            self.docs,
            self.documentation,
            self.fixture(name),
            self.policy,
        )
        checks, metrics = telemetry_exporter_authority_audit.evaluate(docs, documentation, self.policy)
        return {
            "status": "pass" if all(item["status"] == "pass" for item in checks) else "fail",
            "checks": checks,
            "metrics": metrics,
        }

    def test_current_exporter_authority_passes(self) -> None:
        report = telemetry_exporter_authority_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["exporter_count"])
        self.assertEqual(2, report["authoritative_pipeline_count"])
        self.assertEqual(2, report["local_debug_pipeline_count"])
        self.assertEqual(1, report["queued_exporter_count"])
        self.assertEqual(1, report["retry_enabled_count"])
        self.assertEqual(8, report["detected_fixture_count"])

    def test_detects_missing_authoritative_annotation(self) -> None:
        report = self.report_for_fixture("missing_authoritative_exporter_annotation")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["exporter_authority_annotations"])

    def test_detects_debug_declared_authoritative(self) -> None:
        report = self.report_for_fixture("debug_declared_authoritative")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["exporter_authority_annotations"])

    def test_detects_missing_authoritative_pipeline_exporter(self) -> None:
        report = self.report_for_fixture("traces_missing_authoritative_exporter")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["authoritative_pipeline_path"])

    def test_detects_debug_only_pipeline(self) -> None:
        report = self.report_for_fixture("metrics_debug_only")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["local_debug_boundary"])

    def test_detects_insecure_upstream(self) -> None:
        report = self.report_for_fixture("insecure_http_upstream")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["secure_upstream_endpoint"])

    def test_detects_disabled_queue(self) -> None:
        report = self.report_for_fixture("disabled_upstream_queue")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["queued_delivery_boundary"])

    def test_detects_missing_replacement_docs(self) -> None:
        report = self.report_for_fixture("missing_replacement_docs")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["production_replacement_docs"])

    def test_writes_json_and_markdown(self) -> None:
        report = telemetry_exporter_authority_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            telemetry_exporter_authority_audit.write_json(report, output_dir)
            telemetry_exporter_authority_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "telemetry-exporter-authority-audit.json").exists())
            self.assertIn(
                "Telemetry Exporter Authority Audit",
                (output_dir / "telemetry-exporter-authority-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
