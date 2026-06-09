from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import oss_license_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class OssLicenseAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = oss_license_audit.load_json(REPO_ROOT / "config/oss-license-policy.json")
        self.files = oss_license_audit.read_files(REPO_ROOT, oss_license_audit.policy_paths(self.policy))

    def report_for_files(self, files: dict[str, str | None]) -> dict:
        checks, metrics = oss_license_audit.evaluate_files(files, self.policy)
        fixtures = oss_license_audit.evaluate_fixtures(files, self.policy)
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            oss_license_audit.check(
                "negative_fixture_coverage",
                detected_fixture_count >= self.policy["minimum_detected_fixtures"],
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

    def test_current_oss_license_audit_passes(self) -> None:
        report = oss_license_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, report["action_count"])
        self.assertEqual(4, report["image_count"])
        self.assertEqual(9, report["third_party_reference_count"])
        self.assertEqual(6, report["detected_fixture_count"])

    def test_detects_missing_license_file(self) -> None:
        files = copy.deepcopy(self.files)
        files["LICENSE"] = None

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["license_file"])

    def test_detects_missing_notice_file(self) -> None:
        files = copy.deepcopy(self.files)
        files["NOTICE"] = None

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["notice_file"])

    def test_detects_unapproved_action(self) -> None:
        files = copy.deepcopy(self.files)
        files[".github/workflows/ci.yml"] += "\n      - uses: third-party/not-approved@v1\n"

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["approved_actions"])

    def test_detects_unapproved_image(self) -> None:
        files = copy.deepcopy(self.files)
        files["docker-compose.yaml"] += "\n  unapproved:\n    image: example/not-approved:latest\n"

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["approved_images"])

    def test_writes_json_and_markdown_outputs(self) -> None:
        report = oss_license_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            oss_license_audit.write_json(report, output_dir)
            oss_license_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "oss-license-audit.json").exists())
            self.assertIn("OSS License Audit", (output_dir / "oss-license-audit.md").read_text())


if __name__ == "__main__":
    unittest.main()
