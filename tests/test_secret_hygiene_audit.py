from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from demo import secret_hygiene_audit


REPO_ROOT = Path(__file__).resolve().parents[1]


class SecretHygieneAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = secret_hygiene_audit.load_json(REPO_ROOT / "config/secret-hygiene-policy.json")
        paths = secret_hygiene_audit.collect_scan_paths(REPO_ROOT, self.policy)
        self.files, self.skipped = secret_hygiene_audit.read_files(REPO_ROOT, paths)

    def report_for_files(self, files: dict[str, str]) -> dict:
        checks, metrics = secret_hygiene_audit.evaluate_files(files, [], self.policy)
        fixtures = secret_hygiene_audit.evaluate_fixtures(files, self.policy)
        detected_fixture_count = sum(1 for item in fixtures if item["detected"])
        checks.append(
            secret_hygiene_audit.check(
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

    def test_current_secret_hygiene_audit_passes(self) -> None:
        report = secret_hygiene_audit.build_report(REPO_ROOT, self.policy)

        self.assertEqual("pass", report["status"])
        self.assertGreaterEqual(report["scanned_file_count"], self.policy["minimum_scanned_files"])
        self.assertGreaterEqual(report["evidence_file_count"], self.policy["minimum_evidence_files"])
        self.assertEqual(6, report["pattern_count"])
        self.assertEqual(0, report["finding_count"])
        self.assertEqual(0, report["skipped_file_count"])
        self.assertEqual(6, report["detected_fixture_count"])

    def test_detects_private_key_header(self) -> None:
        files = copy.deepcopy(self.files)
        files["README.md"] += "\n" + secret_hygiene_audit.synthetic_secret("private_key_header") + "\n"

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["secret_pattern_scan"])

    def test_detects_aws_access_key(self) -> None:
        files = copy.deepcopy(self.files)
        files["README.md"] += "\n" + secret_hygiene_audit.synthetic_secret("aws_access_key_id") + "\n"

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["secret_pattern_scan"])

    def test_detects_github_token(self) -> None:
        files = copy.deepcopy(self.files)
        files["README.md"] += "\n" + secret_hygiene_audit.synthetic_secret("github_token") + "\n"

        report = self.report_for_files(files)
        checks = {item["name"]: item["ok"] for item in report["checks"]}

        self.assertEqual("fail", report["status"])
        self.assertFalse(checks["secret_pattern_scan"])

    def test_detects_skipped_scan_files(self) -> None:
        checks, _ = secret_hygiene_audit.evaluate_files(self.files, [{"path": "bad.bin", "reason": "not_utf8"}], self.policy)
        checks_by_name = {item["name"]: item["ok"] for item in checks}

        self.assertFalse(checks_by_name["scanned_file_inventory"])

    def test_writes_json_and_markdown_outputs(self) -> None:
        report = secret_hygiene_audit.build_report(REPO_ROOT, self.policy)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            secret_hygiene_audit.write_json(report, output_dir)
            secret_hygiene_audit.write_markdown(report, output_dir)

            self.assertTrue((output_dir / "secret-hygiene-audit.json").exists())
            self.assertIn("Secret Hygiene Audit", (output_dir / "secret-hygiene-audit.md").read_text())


if __name__ == "__main__":
    unittest.main()
