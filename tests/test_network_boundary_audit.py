from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import network_boundary_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class NetworkBoundaryAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = network_boundary_audit.load_json(REPO_ROOT / "config/network-boundary-policy.json")
        self.docs = network_boundary_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = network_boundary_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return network_boundary_audit.evaluate_documents(docs, self.policy)

    def test_current_network_boundary_audit_passes(self) -> None:
        report = network_boundary_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["network_policy_count"])
        self.assertEqual(2, report["egress_rule_count"])
        self.assertEqual(10, report["detected_fixture_count"])

    def test_detects_missing_workload_egress_policy(self) -> None:
        report = self.mutated_report("missing_workload_egress_policy")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["workload_egress_policy"])

    def test_detects_wrong_workload_selector(self) -> None:
        report = self.mutated_report("workload_policy_wrong_selector")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["workload_policy_selector"])

    def test_detects_missing_telemetry_egress(self) -> None:
        report = self.mutated_report("missing_telemetry_egress")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["telemetry_egress"])

    def test_detects_missing_otlp_port(self) -> None:
        report = self.mutated_report("missing_otlp_http_port")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["telemetry_egress"])
        self.assertEqual("fail", checks["telemetry_ports"])

    def test_detects_missing_dns_egress(self) -> None:
        report = self.mutated_report("missing_dns_egress")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["dns_egress"])

    def test_detects_allow_all_egress(self) -> None:
        report = self.mutated_report("allow_all_egress")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["deny_unbounded_egress"])

    def test_detects_collector_ingress_regression(self) -> None:
        report = self.mutated_report("collector_ingress_wrong_namespace_selector")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["collector_ingress_boundary"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = network_boundary_audit.build_report(self.docs, self.policy)

            network_boundary_audit.write_json(report, output_dir)
            network_boundary_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "network-boundary-audit.json").exists())
            self.assertIn(
                "Network Boundary Audit",
                (output_dir / "network-boundary-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
