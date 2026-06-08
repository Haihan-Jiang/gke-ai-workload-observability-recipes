from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import namespace_resource_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class NamespaceResourceAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = namespace_resource_audit.load_json(REPO_ROOT / "config/namespace-resource-policy.json")
        self.docs = namespace_resource_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = namespace_resource_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return namespace_resource_audit.evaluate_documents(docs, self.policy)

    def test_current_namespace_resource_audit_passes(self) -> None:
        report = namespace_resource_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["namespace_count"])
        self.assertEqual(8, report["check_count"])
        self.assertEqual(8, report["detected_fixture_count"])

    def test_detects_missing_resource_quota(self) -> None:
        report = self.mutated_report("missing_telemetry_quota")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["namespace_resource_quota"])

    def test_detects_missing_limit_range(self) -> None:
        report = self.mutated_report("missing_workload_limit_range")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["namespace_limit_range"])

    def test_detects_quota_that_does_not_cover_workloads(self) -> None:
        report = self.mutated_report("workload_memory_quota_too_low")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["quota_covers_workloads"])

    def test_detects_missing_default_request(self) -> None:
        report = self.mutated_report("missing_container_default_request")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["container_defaulting"])

    def test_detects_limit_range_bounds_regression(self) -> None:
        report = self.mutated_report("limit_range_max_below_default")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["limit_range_sane_bounds"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = namespace_resource_audit.build_report(self.docs, self.policy)

            namespace_resource_audit.write_json(report, output_dir)
            namespace_resource_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "namespace-resource-audit.json").exists())
            self.assertIn(
                "Namespace Resource Audit",
                (output_dir / "namespace-resource-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
