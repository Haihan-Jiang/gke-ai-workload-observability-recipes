from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import availability_topology_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class AvailabilityTopologyAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = availability_topology_audit.load_json(REPO_ROOT / "config/availability-topology-policy.json")
        self.docs = availability_topology_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = availability_topology_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return availability_topology_audit.evaluate_documents(docs, self.policy)

    def test_current_availability_topology_audit_passes(self) -> None:
        report = availability_topology_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(2, report["workload_count"])
        self.assertEqual(2, report["pdb_count"])
        self.assertEqual(2, report["topology_spread_count"])
        self.assertEqual(7, report["detected_fixture_count"])

    def test_detects_missing_pdb(self) -> None:
        report = self.mutated_report("missing_sample_pdb")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["pdb_coverage"])

    def test_detects_pdb_that_blocks_multi_replica_disruption(self) -> None:
        report = self.mutated_report("sample_pdb_min_equals_replicas")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["pdb_coverage"])

    def test_detects_missing_topology_spread(self) -> None:
        report = self.mutated_report("missing_sample_zone_spread")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["topology_spread_coverage"])

    def test_detects_spread_selector_mismatch(self) -> None:
        report = self.mutated_report("sample_spread_selector_mismatch")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["spread_selector_matches_pod_labels"])

    def test_detects_missing_owner_label(self) -> None:
        report = self.mutated_report("missing_sample_pdb_owner_label")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["availability_label_governance"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = availability_topology_audit.build_report(self.docs, self.policy)

            availability_topology_audit.write_json(report, output_dir)
            availability_topology_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "availability-topology-audit.json").exists())
            self.assertIn(
                "Availability Topology Audit",
                (output_dir / "availability-topology-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
