from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import release_control_ownership_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class ReleaseControlOwnershipAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = release_control_ownership_audit.load_json(
            REPO_ROOT / "config/release-control-ownership-policy.json"
        )
        self.release_checks = release_control_ownership_audit.extract_release_checks(
            REPO_ROOT / "demo/release_readiness.py"
        )

    def report_for_policy(self, policy: dict) -> dict:
        checks, metrics = release_control_ownership_audit.evaluate_controls(policy, self.release_checks)
        fixtures = release_control_ownership_audit.evaluate_fixtures(policy, self.release_checks)
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            release_control_ownership_audit.check(
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

    def test_current_release_control_ownership_passes(self) -> None:
        report = release_control_ownership_audit.build_report(
            self.policy,
            REPO_ROOT / "demo/release_readiness.py",
        )

        self.assertEqual("pass", report["status"])
        self.assertEqual(66, report["control_count"])
        self.assertEqual(report["release_check_count"], report["covered_release_check_count"])
        self.assertGreaterEqual(report["tier0_count"], 43)
        self.assertGreaterEqual(report["every_release_count"], 54)
        self.assertEqual(6, report["detected_fixture_count"])

    def test_detects_missing_release_check_owner(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"] = [item for item in policy["controls"] if item["name"] != "evidence_provenance"]

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["control_inventory"])

    def test_detects_unknown_release_check(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"][0]["name"] = "not_a_release_check"

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["control_inventory"])

    def test_detects_missing_owner(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"][0].pop("owner")

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["ownership_metadata"])

    def test_detects_invalid_tier(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"][0]["tier"] = "tier_9_unknown"

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["tier_contract"])

    def test_detects_bad_evidence_path(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["controls"][0]["evidence_path"] = "tmp/reliability-gate.json"

        report = self.report_for_policy(policy)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["evidence_path_contract"])

    def test_writes_json_and_markdown_outputs(self) -> None:
        report = release_control_ownership_audit.build_report(
            self.policy,
            REPO_ROOT / "demo/release_readiness.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            release_control_ownership_audit.write_json(report, output_dir)
            release_control_ownership_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "release-control-ownership-audit.json").exists())
            self.assertIn(
                "Release Control Ownership Audit",
                (output_dir / "release-control-ownership-audit.md").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
