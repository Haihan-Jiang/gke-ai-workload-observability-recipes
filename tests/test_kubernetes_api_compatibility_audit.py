from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import kubernetes_api_compatibility_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class KubernetesApiCompatibilityAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = kubernetes_api_compatibility_audit.load_json(
            REPO_ROOT / "config/kubernetes-api-compatibility-policy.json"
        )
        self.docs = kubernetes_api_compatibility_audit.load_manifest_set(
            REPO_ROOT,
            list(self.policy["target_manifests"]),
        )
        self.kind_smoke = (REPO_ROOT / self.policy["kind_smoke_script"]).read_text(encoding="utf-8")

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def report_for_fixture(self, name: str) -> dict:
        docs, script = kubernetes_api_compatibility_audit.apply_fixture(
            self.docs,
            self.kind_smoke,
            self.fixture(name),
        )
        checks, metrics = kubernetes_api_compatibility_audit.evaluate_documents(docs, self.policy, script)
        return {
            "status": "pass" if all(item["status"] == "pass" for item in checks) else "fail",
            "checks": checks,
            "metrics": metrics,
        }

    def test_current_kubernetes_api_compatibility_passes(self) -> None:
        report = kubernetes_api_compatibility_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(28, report["document_count"])
        self.assertEqual(26, report["stable_resource_count"])
        self.assertEqual(2, report["optional_crd_count"])
        self.assertEqual(8, report["detected_fixture_count"])

    def test_detects_deployment_beta_api(self) -> None:
        report = self.report_for_fixture("deployment_uses_extensions_beta")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["stable_core_api_versions"])

    def test_detects_pdb_beta_api(self) -> None:
        report = self.report_for_fixture("pdb_uses_policy_beta")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["stable_core_api_versions"])

    def test_detects_hpa_legacy_api(self) -> None:
        report = self.report_for_fixture("hpa_uses_legacy_version")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["stable_core_api_versions"])

    def test_detects_admission_beta_api(self) -> None:
        report = self.report_for_fixture("admission_policy_uses_beta")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["admission_policy_api"])

    def test_detects_warn_only_binding(self) -> None:
        report = self.report_for_fixture("admission_binding_warns_only")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["admission_policy_api"])

    def test_detects_missing_optional_crd_skip_text(self) -> None:
        report = self.report_for_fixture("missing_otel_crd_skip")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["optional_crd_boundary"])

    def test_detects_missing_core_apply_step(self) -> None:
        report = self.report_for_fixture("missing_collector_apply_step")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["kind_smoke_contract"])

    def test_writes_json_and_markdown(self) -> None:
        report = kubernetes_api_compatibility_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            kubernetes_api_compatibility_audit.write_json(report, output_dir)
            kubernetes_api_compatibility_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "kubernetes-api-compatibility-audit.json").exists())
            self.assertIn(
                "Kubernetes API Compatibility Audit",
                (output_dir / "kubernetes-api-compatibility-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
