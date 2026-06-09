from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import control_traceability_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ControlTraceabilityAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = control_traceability_audit.load_json(REPO_ROOT / "config/control-traceability-policy.json")
        self.release_checks = control_traceability_audit.extract_release_checks(REPO_ROOT / "demo/release_readiness.py")

    def report_for_policy(self, policy: dict) -> dict:
        checks, metrics = control_traceability_audit.evaluate_controls(
            REPO_ROOT,
            policy,
            self.release_checks,
        )
        fixtures = control_traceability_audit.evaluate_fixtures(REPO_ROOT, policy, self.release_checks)
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            control_traceability_audit.check(
                "negative_fixture_coverage",
                detected_fixture_count >= policy["minimum_detected_fixtures"],
                {"detected_fixture_count": detected_fixture_count},
            )
        )
        failed_count = sum(1 for item in checks if not item["ok"])
        return {
            "status": "pass" if failed_count == 0 else "fail",
            "checks": checks,
            "metrics": metrics,
            "fixtures": fixtures,
        }

    def test_current_control_traceability_passes(self) -> None:
        report = control_traceability_audit.build_report(
            REPO_ROOT,
            self.policy,
            Path("demo/release_readiness.py"),
        )

        self.assertEqual("pass", report["status"])
        self.assertEqual(55, report["control_count"])
        self.assertGreaterEqual(report["release_check_count"], 60)
        self.assertGreaterEqual(report["policy_input_count"], 56)
        self.assertEqual(6, report["detected_fixture_count"])

    def test_detects_missing_control_entry(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"] = [item for item in policy["controls"] if item["name"] != "evidence_provenance"]

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["control_inventory"])

    def test_detects_unknown_release_check(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"][0]["release_readiness_check"] = "not_a_release_check"

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["release_gate_linkage"])

    def test_detects_missing_evidence_file(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"][0]["evidence"].append("docs/evidence/not-real.json")

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["evidence_files"])

    def test_detects_missing_source_input(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"][0]["source_inputs"].append("demo/not_real.py")

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["source_inputs"])

    def test_detects_missing_policy_input(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"][0]["policy_inputs"].append("config/not-real.json")

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["policy_inputs"])

    def test_detects_missing_test_file(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"][0]["tests"].append("tests/test_not_real.py")

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["test_coverage"])

    def test_writes_json_and_markdown_outputs(self) -> None:
        report = control_traceability_audit.build_report(
            REPO_ROOT,
            self.policy,
            Path("demo/release_readiness.py"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            json_output = output_dir / "traceability.json"
            markdown_output = output_dir / "traceability.md"

            control_traceability_audit.write_json(report, json_output)
            control_traceability_audit.write_markdown(report, markdown_output)

            self.assertTrue(json_output.exists())
            self.assertIn("Control Traceability Audit", markdown_output.read_text())


if __name__ == "__main__":
    unittest.main()
