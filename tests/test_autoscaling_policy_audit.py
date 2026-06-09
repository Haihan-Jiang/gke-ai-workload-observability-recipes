from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from demo import autoscaling_policy_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class AutoscalingPolicyAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = autoscaling_policy_audit.load_json(REPO_ROOT / "config/autoscaling-policy.json")
        self.docs = autoscaling_policy_audit.load_manifest_set(
            [REPO_ROOT / path for path in self.policy["target_manifests"]]
        )

    def fixture(self, name: str) -> dict:
        for item in self.policy["fixtures"]:
            if item["name"] == name:
                return item
        raise AssertionError(f"missing fixture {name}")

    def mutated_report(self, fixture_name: str) -> dict:
        docs = autoscaling_policy_audit.mutate_fixture(self.docs, self.policy, self.fixture(fixture_name))
        return autoscaling_policy_audit.evaluate_documents(docs, self.policy)

    def test_current_autoscaling_policy_audit_passes(self) -> None:
        report = autoscaling_policy_audit.build_report(self.docs, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(1, report["hpa_count"])
        self.assertEqual(2, report["metric_count"])
        self.assertEqual(3, report["behavior_policy_count"])
        self.assertEqual(9, report["detected_fixture_count"])

    def test_detects_missing_hpa(self) -> None:
        report = self.mutated_report("missing_hpa")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["hpa_coverage"])

    def test_detects_wrong_scale_target(self) -> None:
        report = self.mutated_report("wrong_scale_target")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["hpa_target_ref"])

    def test_detects_bad_replica_bounds(self) -> None:
        report = self.mutated_report("max_replicas_below_burst_budget")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["replica_bounds"])

    def test_detects_missing_metric(self) -> None:
        report = self.mutated_report("missing_cpu_metric")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["metric_coverage"])

    def test_detects_metric_target_outside_policy(self) -> None:
        report = self.mutated_report("cpu_target_too_high")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["metric_targets"])

    def test_detects_missing_resource_request_for_metric(self) -> None:
        report = self.mutated_report("missing_cpu_request")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["metric_request_alignment"])

    def test_detects_missing_scale_behavior(self) -> None:
        report = self.mutated_report("missing_scale_down_stabilization")
        checks = {item["name"]: item["status"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertEqual("fail", checks["scale_behavior"])

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            report = autoscaling_policy_audit.build_report(self.docs, self.policy)

            autoscaling_policy_audit.write_json(report, output_dir)
            autoscaling_policy_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "autoscaling-policy-audit.json").exists())
            self.assertIn(
                "Autoscaling Policy Audit",
                (output_dir / "autoscaling-policy-audit.md").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
