from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import workload_identity_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class WorkloadIdentityAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = workload_identity_audit.load_json(REPO_ROOT / "config/workload-identity-policy.json")
        self.docs = workload_identity_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = workload_identity_audit.mutate_fixture(
            self.docs,
            self.fixture(fixture_name),
            self.policy["workload_identity_annotation"],
        )
        return workload_identity_audit.evaluate_documents(docs, self.policy)

    def test_current_workload_identity_audit_passes(self) -> None:
        report = workload_identity_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(8, report["check_count"])
        self.assertEqual(2, report["identity_boundary_count"])
        self.assertEqual(9, report["detected_fixture_count"])
        self.assertEqual("https://otel-gateway.example.com:4318", report["upstream_endpoint"])

    def test_detects_missing_workload_identity_annotation(self) -> None:
        report = self.mutated_report("missing_workload_identity_annotation")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["workload_identity_annotation"])

    def test_detects_workload_token_automount_enabled(self) -> None:
        report = self.mutated_report("workload_token_automount_enabled")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["application_token_boundary"])

    def test_detects_static_credential_without_echoing_secret_value(self) -> None:
        report = self.mutated_report("static_gcp_secret_added")
        checks = {item["name"]: item["status"] for item in report["checks"]}
        static_check = next(item for item in report["checks"] if item["name"] == "static_credential_guard")

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["static_credential_guard"])
        self.assertNotIn("redacted@example.com", str(static_check["evidence"]))

    def test_detects_mutating_rbac_verb(self) -> None:
        report = self.mutated_report("collector_rbac_mutating_verb")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["rbac_least_privilege"])

    def test_detects_insecure_upstream_endpoint(self) -> None:
        report = self.mutated_report("insecure_upstream_endpoint")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["secure_exporter_boundary"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = workload_identity_audit.build_report(self.docs, self.policy)

            workload_identity_audit.write_json(report, output_dir)
            workload_identity_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "workload-identity-audit.json").exists())
            self.assertIn(
                "Workload Identity Audit",
                (output_dir / "workload-identity-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
