import tempfile
import unittest
from pathlib import Path

from demo import private_cluster_admission_boundary_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class PrivateClusterAdmissionBoundaryAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = private_cluster_admission_boundary_audit.load_json(
            REPO_ROOT / "config/private-cluster-admission-boundary-policy.json"
        )

    def report_for_fixture(self, fixture_name: str) -> dict:
        docs = private_cluster_admission_boundary_audit.load_manifest_set(
            REPO_ROOT,
            list(self.policy["target_manifests"]),
        )
        kind_smoke_text = (REPO_ROOT / self.policy["kind_smoke_script"]).read_text(encoding="utf-8")
        doc_texts = {
            marker["path"]: (REPO_ROOT / marker["path"]).read_text(encoding="utf-8")
            for marker in self.policy["private_cluster_doc_markers"]
        }
        fixture = next(item for item in self.policy["fixtures"] if item["name"] == fixture_name)
        mutated_docs, mutated_script, mutated_texts = private_cluster_admission_boundary_audit.apply_fixture(
            docs,
            kind_smoke_text,
            doc_texts,
            fixture,
        )
        checks, _ = private_cluster_admission_boundary_audit.evaluate_documents(
            mutated_docs,
            self.policy,
            mutated_script,
            mutated_texts,
        )
        return {"checks": {item["name"]: item["status"] for item in checks}}

    def test_current_private_cluster_boundary_passes(self) -> None:
        report = private_cluster_admission_boundary_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["webhook_configuration_count"])
        self.assertEqual(0, report["webhook_service_count"])
        self.assertGreaterEqual(report["native_admission_resource_count"], 2)
        self.assertGreaterEqual(report["optional_operator_boundary_count"], 2)
        self.assertEqual(len(self.policy["fixtures"]), report["detected_fixture_count"])

    def test_detects_validating_webhook_configuration(self) -> None:
        report = self.report_for_fixture("adds_validating_webhook_configuration")

        self.assertEqual("fail", report["checks"]["native_admission_boundary"])

    def test_detects_mutating_webhook_configuration(self) -> None:
        report = self.report_for_fixture("adds_mutating_webhook_configuration")

        self.assertEqual("fail", report["checks"]["native_admission_boundary"])

    def test_detects_admission_webhook_service(self) -> None:
        report = self.report_for_fixture("adds_admission_webhook_service")

        self.assertEqual("fail", report["checks"]["webhook_service_boundary"])

    def test_detects_native_admission_client_config(self) -> None:
        report = self.report_for_fixture("adds_native_admission_client_config")

        self.assertEqual("fail", report["checks"]["native_admission_boundary"])

    def test_detects_missing_optional_operator_skip(self) -> None:
        report = self.report_for_fixture("removes_otel_operator_skip")

        self.assertEqual("fail", report["checks"]["optional_operator_boundary"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = private_cluster_admission_boundary_audit.build_report(REPO_ROOT, self.policy)

            private_cluster_admission_boundary_audit.write_json(report, output_dir)
            private_cluster_admission_boundary_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "private-cluster-admission-boundary-audit.json").exists())
            self.assertIn(
                "Private Cluster Admission Boundary Audit",
                (output_dir / "private-cluster-admission-boundary-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
