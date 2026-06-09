from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import pod_security_admission_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class PodSecurityAdmissionAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = pod_security_admission_audit.load_json(REPO_ROOT / "config/pod-security-admission-policy.json")
        self.docs = pod_security_admission_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = pod_security_admission_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return pod_security_admission_audit.evaluate_documents(docs, self.policy)

    def test_current_pod_security_admission_audit_passes(self) -> None:
        report = pod_security_admission_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["namespace_count"])
        self.assertEqual(2, report["workload_count"])
        self.assertEqual(2, report["restricted_namespace_count"])
        self.assertEqual(2, report["restricted_workload_count"])
        self.assertEqual(10, report["detected_fixture_count"])

    def test_detects_missing_enforce_label(self) -> None:
        report = self.mutated_report("telemetry_missing_enforce_label")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["namespace_psa_labels"])

    def test_detects_baseline_enforce_label(self) -> None:
        report = self.mutated_report("workload_enforce_baseline")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["namespace_psa_labels"])

    def test_detects_missing_warn_version(self) -> None:
        report = self.mutated_report("telemetry_missing_warn_version")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["namespace_psa_labels"])

    def test_detects_privileged_container(self) -> None:
        report = self.mutated_report("collector_privileged_container")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["restricted_container_security"])

    def test_detects_privilege_escalation(self) -> None:
        report = self.mutated_report("sample_allows_privilege_escalation")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["restricted_container_security"])

    def test_detects_added_capability(self) -> None:
        report = self.mutated_report("collector_adds_net_raw")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["restricted_container_security"])

    def test_detects_host_network(self) -> None:
        report = self.mutated_report("sample_host_network")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["restricted_pod_security"])

    def test_detects_host_path_volume(self) -> None:
        report = self.mutated_report("collector_host_path_volume")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["restricted_volume_types"])

    def test_detects_missing_seccomp(self) -> None:
        report = self.mutated_report("sample_missing_seccomp")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["restricted_pod_security"])

    def test_detects_root_pod(self) -> None:
        report = self.mutated_report("collector_run_as_root")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["restricted_pod_security"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = pod_security_admission_audit.build_report(self.docs, self.policy)

            pod_security_admission_audit.write_json(report, output_dir)
            pod_security_admission_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "pod-security-admission-audit.json").exists())
            self.assertIn(
                "Pod Security Admission Audit",
                (output_dir / "pod-security-admission-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
